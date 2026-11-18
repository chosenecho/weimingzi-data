"""Native four-entity schema: structure, provenance and exact evidence validation.

Kinds select domain rules directly. No projected rows or reconstruction recipes
participate in reads, writes, hashes or validation.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
from pathlib import Path
import re

from .records import (
    ENTITIES, RECORD_ID_PATTERN, SHA256_PATTERN,
    _read_entities, block_text, canonical_json, document_hash_input,
    input_ids, json_sha256, resolve_repository_path,
    validate_relative_path,
)

SCHEMA_VERSION = 3
ITEM_KINDS = frozenset(("video", "video_part", "audio_recording", "post", "article", "person", "video_collection", "video_series", "article_collection"))
DOCUMENT_KINDS = frozenset(("transcript", "edited_transcript", "post", "article"))
ASSET_KINDS = frozenset(("audio", "html", "review_document", "archive"))
ANNOTATION_KINDS = frozenset(("confirmation", "segment_attribution"))
_COMMON = {"id", "kind", "metadata"}
_ITEM_KEYS = _COMMON | {"title", "identifiers", "urls", "relations", "parent_id", "part_number", "members"}
_DOCUMENT_KEYS = {
    "transcript": _COMMON | {"inputs", "method", "language", "model", "time_unit", "text", "blocks", "content_sha256", "quality", "recognition_chunks", "recognition_chunks_sha256"},
    "edited_transcript": _COMMON | {"inputs", "language", "model", "time_unit", "text", "blocks", "quality", "notes_markdown", "is_complete", "input_units"},
    "post": _COMMON | {"inputs", "content", "text"},
    "article": _COMMON | {"inputs", "text", "text_variant", "quality"},
}
_ASSET_KEYS = {
    "audio": _COMMON | {"inputs", "availability", "sha256", "size_bytes", "local_path", "downloads", "unavailable_reason"},
    "html": _COMMON | {"sha256", "size_bytes", "local_path"},
    "review_document": _COMMON | {"sha256", "size_bytes", "local_path"},
    "archive": _COMMON | {"name", "sha256", "size_bytes", "url"},
}
_ANNOTATION_KEYS = {
    "confirmation": _COMMON | {"targets", "anchor", "corrected_text", "corrected_text_sha256", "scope", "status", "term_glosses", "confirmation", "urls"},
    "segment_attribution": _COMMON | {"targets", "anchor", "speaker_role", "viewpoint", "review", "status", "urls"},
}
_BLOCK_KEYS = {"range", "literal", "start", "end", "chunk_offset_seconds", "speaker_id", "input_text", "input_text_ref", "input_unit_labels", "issues"}
_DOCUMENT_ROLES = {
    "transcript": {"item", "audio"},
    "edited_transcript": {"item", "transcript", "derived_from", "input_units_from", "review_document_markdown"},
    "post": {"item", "article_item"},
    "article": {"item", "html"},
}
_ROLE_TARGETS = {
    "item": ("items", ITEM_KINDS),
    "article_item": ("items", {"article"}),
    "audio": ("assets", {"audio"}),
    "html": ("assets", {"html"}),
    "review_document_markdown": ("assets", {"review_document"}),
    "transcript": ("documents", {"transcript"}),
    "derived_from": ("documents", {"edited_transcript"}),
    "input_units_from": ("documents", {"edited_transcript"}),
}
_ATTRIBUTION_ANCHOR_KEYS = {"paragraph_index", "paragraph_text_sha256", "excerpt", "start", "end", "time_unit"}
_REVIEW_REQUIRED = {"basis", "reviewer_label", "reviewed_on", "review_timezone", "reviewer_reported_watched_original_video", "assistant_listened_to_audio"}


def _keys(value, allowed, context):
    if not isinstance(value, dict):
        raise ValueError(f"{context}: expected object")
    extra = set(value) - allowed
    if extra:
        raise ValueError(f"{context}: unknown fields {sorted(extra)}")


def _text(value, context, *, nonempty=False):
    if not isinstance(value, str) or nonempty and not value.strip():
        raise ValueError(f"{context}: expected {'non-empty ' if nonempty else ''}text")


def _array(value, context):
    if not isinstance(value, list):
        raise ValueError(f"{context}: expected array")
    return value


def _digest(value, context):
    if not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value):
        raise ValueError(f"{context}: invalid SHA-256")


def _size(value, context):
    if type(value) is not int or value < 0:
        raise ValueError(f"{context}: expected nonnegative integer")


def _https(value, context):
    if not isinstance(value, str) or not value.startswith("https://"):
        raise ValueError(f"{context}: expected HTTPS URL")


def _owner(row):
    owners = input_ids(row, "item")
    return owners[0] if len(owners) == 1 else None


def _edges(row, field, allowed, entities):
    edges = _array(row.get(field), row["id"] + "/" + field)
    seen = set()
    for edge in edges:
        _keys(edge, {"role", "target_id", "order"} if field == "targets" else {"role", "target_id"}, row["id"] + " edge")
        role, target = edge.get("role"), edge.get("target_id")
        if role not in allowed:
            raise ValueError(f"{row['id']}: invalid {field} role {role!r}")
        if not isinstance(target, str) or not RECORD_ID_PATTERN.fullmatch(target):
            raise ValueError(f"{row['id']}: invalid target ID")
        key = (role, target)
        if key in seen:
            raise ValueError(f"{row['id']}: duplicate {role} target {target}")
        seen.add(key)
        entity, kinds = _ROLE_TARGETS[role] if field == "inputs" else ("items", ITEM_KINDS) if role == "item" else ("documents", {"edited_transcript"})
        if target not in entities[entity] or entities[entity][target].get("kind") not in kinds:
            raise ValueError(f"{row['id']}: unresolved or wrong-kind {role} target {target}")
    return Counter(edge["role"] for edge in edges)


def _quality(row):
    if "quality" in row:
        quality = row["quality"]
        if not isinstance(quality, dict):
            raise ValueError(f"{row['id']}: quality must be an object")
        for name in ("is_fully_human_reviewed", "requires_review", "is_subtitle_export_enabled"):
            if name in quality and quality[name] is not None and type(quality[name]) is not bool:
                raise ValueError(f"{row['id']}: {name} must be boolean or null")
    model = row.get("model")
    if model is not None and (not isinstance(model, dict) or not isinstance(model.get("name"), str)):
        raise ValueError(f"{row['id']}: model must be an object with name or null")


def _recognition_issues(value, context):
    if isinstance(value, list):
        for nested in value:
            _recognition_issues(nested, context)
    elif isinstance(value, dict):
        for key, nested in value.items():
            if key == "recognition_issue_intervals":
                pending = list(nested) if isinstance(nested, list) else [nested]
                while pending:
                    interval = pending.pop()
                    if isinstance(interval, list):
                        pending.extend(interval)
                        continue
                    if not isinstance(interval, dict):
                        raise ValueError(f"{context}: expected recognition issue object")
                    start, end = interval.get("start_seconds"), interval.get("end_seconds")
                    if any(isinstance(n, bool) or not isinstance(n, (int, float)) or not Decimal(str(n)).is_finite() for n in (start, end)) or not 0 <= start < end:
                        raise ValueError(f"{context}: recognition issue requires explicit seconds")
            _recognition_issues(nested, context)


def _document_digest(row, cache):
    key = ("digest", row["id"])
    if key not in cache:
        cache[key] = json_sha256(document_hash_input(row))
    return cache[key]


def _blocks(row, entities, text_cache):
    blocks = _array(row.get("blocks"), row["id"] + "/blocks")
    previous = 0
    for index, block in enumerate(blocks):
        context = f"{row['id']}/blocks/{index}"
        _keys(block, _BLOCK_KEYS, context)
        block_text(row, block)
        if "range" in block:
            if block["range"][0] < previous:
                raise ValueError(f"{context}: block ranges overlap or decrease")
            previous = block["range"][1]
        for key in ("start", "end", "chunk_offset_seconds"):
            if key in block and block[key] is not None:
                value = block[key]
                if type(value) not in (int, float) or not Decimal(str(value)).is_finite():
                    raise ValueError(f"{context}: {key} must be a finite number or null")
        if "input_unit_labels" in block:
            labels = _array(block["input_unit_labels"], context + "/input_unit_labels")
            if any(not isinstance(label, str) for label in labels) or len(set(labels)) != len(labels):
                raise ValueError(f"{context}: invalid input unit labels")
        for issue in _array(block.get("issues", []), context + "/issues"):
            if not isinstance(issue, dict) or not isinstance(issue.get("note"), str):
                raise ValueError(f"{context}: issue requires a note")
            if "candidate" in issue and issue["candidate"] is not None and not isinstance(issue["candidate"], str):
                raise ValueError(f"{context}: issue candidate must be text or null")
            if "evidence_labels" in issue and (not isinstance(issue["evidence_labels"], list) or any(not isinstance(label, str) for label in issue["evidence_labels"])):
                raise ValueError(f"{context}: issue evidence_labels must be text labels")
        if "input_text_ref" in block:
            if "input_text" in block:
                raise ValueError(f"{context}: duplicate input text representation")
            ref = block["input_text_ref"]
            _keys(ref, {"target_id", "content_sha256", "source", "range"}, context + " input_text_ref")
            if set(ref) != {"target_id", "content_sha256", "source", "range"}:
                raise ValueError(f"{context}: incomplete input_text_ref")
            target_id, source = ref["target_id"], ref["source"]
            if target_id not in input_ids(row, "transcript") or target_id not in entities["documents"]:
                raise ValueError(f"{context}: input_text_ref must refer to a transcript input")
            target = entities["documents"][target_id]
            if target.get("kind") != "transcript":
                raise ValueError(f"{context}: input_text_ref target must be a transcript")
            if source not in ("text", "blocks"):
                raise ValueError(f"{context}: invalid input text source {source!r}")
            if _document_digest(target, text_cache) != ref["content_sha256"]:
                raise ValueError(f"{context}: input text content hash mismatch")
            cache_key = (target_id, source)
            if cache_key not in text_cache:
                text_cache[cache_key] = target["text"] if source == "text" else "".join(block_text(target, value) for value in target["blocks"])
            from .records import _slice
            _slice(text_cache[cache_key], ref["range"], context + " input_text_ref")
        elif "input_text" in block and block["input_text"] is not None and not isinstance(block["input_text"], str):
            raise ValueError(f"{context}: input_text must be text or null")
        if row["kind"] == "transcript" and any(key in block for key in ("input_text", "input_text_ref", "input_unit_labels")):
            raise ValueError(f"{context}: transcript blocks cannot carry edited input evidence")


def _snapshot(row):
    if "input_units" not in row:
        return
    value = row["input_units"]
    if not isinstance(value, dict) or not isinstance(value.get("base"), dict):
        raise ValueError(f"{row['id']}: input_units requires a historical base snapshot")
    labels = []
    for unit in _array(value["base"].get("segments"), row["id"] + " input_units/base/segments"):
        if not isinstance(unit, dict) or not isinstance(unit.get("text"), str):
            raise ValueError(f"{row['id']}: invalid input unit snapshot")
        if "label" in unit:
            _text(unit["label"], "input unit label", nonempty=True)
            labels.append(unit["label"])
    if len(set(labels)) != len(labels):
        raise ValueError(f"{row['id']}: duplicate snapshot input unit label")
    # base.content_sha256 and upstream IDs are observations, not live edges.


def _item(row, entities):
    rid = row["id"]
    _text(row.get("title"), rid + "/title")
    if not isinstance(row.get("identifiers"), dict):
        raise ValueError(f"{rid}: identifiers must be an object")
    if row["kind"] in {"video_collection", "video_series", "article_collection"}:
        for member in _array(row.get("members"), rid + "/members"):
            _keys(member, {"item_id", "part_number", "title", "metadata"}, rid + " member")
            if member.get("item_id") not in entities["items"]:
                raise ValueError(f"{rid}: unresolved member item")
    elif "members" in row:
        raise ValueError(f"{rid}: members require a collection kind")
    parent = row.get("parent_id")
    if parent is not None:
        if parent not in entities["items"]:
            raise ValueError(f"{rid}: unresolved parent item")
        if row["kind"] != "video_part" or entities["items"][parent]["kind"] != "video":
            raise ValueError(f"{rid}: video_part parent must be a video")
    if row["kind"] == "video_part":
        if parent is None or type(row.get("part_number")) is not int or row["part_number"] < 1:
            raise ValueError(f"{rid}: video_part requires parent and positive part_number")
    for relation in _array(row.get("relations", []), rid + "/relations"):
        if not isinstance(relation, dict) or relation.get("target_item_id") not in entities["items"]:
            raise ValueError(f"{rid}: unresolved item relation")


def _document(row, entities, text_cache):
    rid, kind = row["id"], row["kind"]
    counts = _edges(row, "inputs", _DOCUMENT_ROLES[kind], entities)
    if counts["item"] != 1:
        raise ValueError(f"{rid}: document requires exactly one item input")
    for role in ("derived_from", "input_units_from", "html", "review_document_markdown"):
        if counts[role] > 1:
            raise ValueError(f"{rid}: {role} allows at most one target")
    owner = _owner(row)
    owner_kind = entities["items"][owner]["kind"]
    expected = {"post": {"post"}, "article": {"article"}, "transcript": {"video", "video_part", "audio_recording"}, "edited_transcript": {"video", "video_part", "audio_recording"}}[kind]
    if owner_kind not in expected:
        raise ValueError(f"{rid}: {kind} has wrong-kind item owner {owner_kind}")
    for edge in row["inputs"]:
        if edge["role"] in ("transcript", "derived_from", "input_units_from"):
            if _owner(entities["documents"][edge["target_id"]]) != owner:
                raise ValueError(f"{rid}: {edge['role']} input belongs to a different item")
        elif edge["role"] == "audio":
            if owner not in input_ids(entities["assets"][edge["target_id"]], "item"):
                raise ValueError(f"{rid}: audio input belongs to a different item")
    if kind != "post" or "text" in row:
        _text(row.get("text"), rid + "/text")
    if kind == "post":
        if not isinstance(row.get("content"), dict):
            raise ValueError(f"{rid}: post content must be an object")
    if kind in ("transcript", "edited_transcript"):
        if row.get("time_unit") not in (("ms", "s") if kind == "transcript" else ("ms", "s", None)):
            raise ValueError(f"{rid}: invalid time_unit")
        _blocks(row, entities, text_cache)
    _quality(row)
    if kind == "transcript":
        _text(row.get("method"), rid + "/method", nonempty=True)
        if _document_digest(row, text_cache) != row.get("content_sha256"):
            raise ValueError(f"{rid}: transcript content SHA-256 mismatch")
        if "recognition_chunks" in row or "recognition_chunks_sha256" in row:
            chunks = _array(row.get("recognition_chunks"), rid + "/recognition_chunks")
            if json_sha256(chunks) != row.get("recognition_chunks_sha256"):
                raise ValueError(f"{rid}: recognition chunks SHA-256 mismatch")
            ids = []
            for chunk in chunks:
                if not isinstance(chunk, dict) or not isinstance(chunk.get("id"), str) or chunk.get("time_unit") != "ms" or not isinstance(chunk.get("sentences"), list):
                    raise ValueError(f"{rid}: invalid recognition chunk")
                ids.append(chunk["id"])
            if len(set(ids)) != len(ids):
                raise ValueError(f"{rid}: duplicate recognition chunk id")
    elif kind == "edited_transcript":
        if type(row.get("is_complete")) is not bool:
            raise ValueError(f"{rid}: is_complete must be boolean")
        if "notes_markdown" in row and row["notes_markdown"] is not None:
            _text(row["notes_markdown"], rid + "/notes_markdown")
        if "input_units" in row and counts["input_units_from"]:
            raise ValueError(f"{rid}: inline input_units and input_units_from are mutually exclusive")
        _snapshot(row)


def _asset(row, root, entities, state):
    rid, kind = row["id"], row["kind"]
    _digest(row.get("sha256"), rid)
    if kind == "archive":
        _size(row.get("size_bytes"), rid)
        validate_relative_path(row.get("name"))
        _https(row.get("url"), rid)
        return
    if kind in ("html", "review_document"):
        _size(row.get("size_bytes"), rid)
        path = resolve_repository_path(root, row.get("local_path"))
        if not path.is_relative_to((root / "data/artifacts").resolve()):
            raise ValueError(f"{rid}: artifact must be under data/artifacts")
        data = path.read_bytes()
        if len(data) != row["size_bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise ValueError(f"{rid}: artifact byte hash mismatch")
        return
    counts = _edges(row, "inputs", {"item"}, entities)
    if not counts["item"]:
        raise ValueError(f"{rid}: audio requires at least one item input")
    if row["sha256"] in state["audio_hashes"]:
        raise ValueError(f"{rid}: duplicate audio SHA-256")
    state["audio_hashes"].add(row["sha256"])
    if row.get("availability") not in ("available", "unavailable"):
        raise ValueError(f"{rid}: invalid audio availability")
    if "size_bytes" in row and row["size_bytes"] is not None:
        _size(row["size_bytes"], rid)
    if "local_path" in row and row["local_path"] is not None:
        relative = validate_relative_path(row["local_path"]).as_posix()
        resolve_repository_path(root, relative)
        if relative in state["restore_paths"]:
            raise ValueError(f"{rid}: duplicate audio restore path")
        state["restore_paths"].add(relative)
    downloads = _array(row.get("downloads", []), rid + "/downloads")
    if row["availability"] == "available":
        if not downloads or row.get("local_path") is None or row.get("size_bytes") is None:
            raise ValueError(f"{rid}: incomplete audio restore locator")
    for download in downloads:
        _keys(download, {"archive_id", "release_tag", "member_path"}, rid + " download")
        archive = entities["assets"].get(download.get("archive_id"))
        if archive is None or archive.get("kind") != "archive":
            raise ValueError(f"{rid}: unresolved or wrong-kind archive target")
        validate_relative_path(download.get("release_tag"))
        validate_relative_path(download.get("member_path"))
        key = (download["release_tag"], archive.get("name"))
        observed = {name: archive.get(name) for name in ("name", "sha256", "size_bytes", "url")}
        if key in state["archives"] and state["archives"][key] != observed:
            raise ValueError(f"{rid}: conflicting archive locator metadata")
        state["archives"][key] = observed
        member = (*key, download["member_path"])
        if member in state["archive_members"]:
            raise ValueError(f"{rid}: duplicate archive member")
        state["archive_members"].add(member)


def _review(value, context, *, attribution=False):
    if not isinstance(value, dict):
        raise ValueError(f"{context}: review evidence must be an object")
    required = _REVIEW_REQUIRED if attribution else {"reviewer_label", "reviewed_on", "review_timezone", "assistant_listened_to_audio"}
    if required - set(value):
        raise ValueError(f"{context}: missing review evidence {sorted(required - set(value))}")
    if attribution:
        _keys(value, _REVIEW_REQUIRED | {"source_url"}, context)
        _text(value["basis"], context + " basis", nonempty=True)
    _text(value["reviewer_label"], context + " reviewer_label", nonempty=True)
    reviewed_on = value["reviewed_on"]
    if not isinstance(reviewed_on, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", reviewed_on):
        raise ValueError(f"{context}: reviewed_on must be YYYY-MM-DD")
    date.fromisoformat(reviewed_on)
    # This is an observed label; validation performs no timezone conversion.
    _text(value["review_timezone"], context + " review_timezone", nonempty=True)
    for key in ("assistant_listened_to_audio", "reviewer_reported_watched_original_video", "user_reported_reviewed_original_video"):
        if key in value and type(value[key]) is not bool:
            raise ValueError(f"{context}: review {key} must be boolean")
    if "source_url" in value:
        _https(value["source_url"], context)


def _attribution_anchor(row, document):
    anchor, rid = row["anchor"], row["id"]
    _keys(anchor, _ATTRIBUTION_ANCHOR_KEYS, rid + " anchor")
    if set(anchor) != _ATTRIBUTION_ANCHOR_KEYS:
        raise ValueError(f"{rid}: attribution anchor requires exact fields")
    index = anchor["paragraph_index"]
    if type(index) is not int or not 0 <= index < len(document["blocks"]):
        raise ValueError(f"{rid}: paragraph_index out of range")
    block = document["blocks"][index]
    text = block_text(document, block)
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != anchor["paragraph_text_sha256"]:
        raise ValueError(f"{rid}: attribution paragraph text hash mismatch")
    excerpt = anchor["excerpt"]
    if excerpt is not None and (not isinstance(excerpt, str) or not excerpt or excerpt not in text):
        raise ValueError(f"{rid}: attribution excerpt not found in block")
    expected = [block.get("start"), block.get("end"), document.get("time_unit")]
    if canonical_json([anchor["start"], anchor["end"], anchor["time_unit"]]) != canonical_json(expected):
        raise ValueError(f"{rid}: attribution start/end/time_unit differ from the block")


def _confirmation_anchor(row, document, role):
    anchor, rid = row["anchor"], row["id"]
    _keys(anchor, {"original_text", "original_text_sha256", "input_unit_label", "paragraph_index"}, rid + " anchor")
    original = anchor.get("original_text")
    _text(original, rid + " original_text", nonempty=True)
    if hashlib.sha256(original.encode("utf-8")).hexdigest() != anchor.get("original_text_sha256"):
        raise ValueError(f"{rid}: confirmation anchor hash mismatch")
    _text(anchor.get("input_unit_label"), rid + " input_unit_label", nonempty=True)
    corrected = row.get("corrected_text")
    _text(corrected, rid + " corrected_text", nonempty=True)
    if hashlib.sha256(corrected.encode("utf-8")).hexdigest() != row.get("corrected_text_sha256"):
        raise ValueError(f"{rid}: corrected text hash mismatch")
    blocks = document["blocks"]
    if "paragraph_index" in anchor:
        index = anchor["paragraph_index"]
        if type(index) is not int or not 0 <= index < len(blocks):
            raise ValueError(f"{rid}: confirmation paragraph_index out of range")
        texts = [block_text(document, blocks[index])]
    else:
        texts = [block_text(document, block) for block in blocks]
    allowed = (corrected,) if role == "revision" else (original, corrected)
    if not any(text in allowed for text in texts):
        raise ValueError(f"{rid}: confirmation text not located in target {document['id']}")
    if role == "revision":
        parents = input_ids(document, "derived_from")
        if len(parents) != 1:
            raise ValueError(f"{rid}: revision target requires a derived_from input")


def _annotation(row, entities, state):
    rid, kind = row["id"], row["kind"]
    counts = _edges(row, "targets", {"item", "applies_to", "revision"} if kind == "confirmation" else {"item", "applies_to"}, entities)
    if counts["item"] != 1 or not counts["applies_to"] + counts["revision"]:
        raise ValueError(f"{rid}: annotation requires one item and applicable document targets")
    if kind == "segment_attribution" and counts["applies_to"] != 1:
        raise ValueError(f"{rid}: attribution requires exactly one applies_to target")
    owner = next(edge["target_id"] for edge in row["targets"] if edge["role"] == "item")
    target_roles = defaultdict(set)
    for edge in row["targets"]:
        role, target_id = edge["role"], edge["target_id"]
        if role != "revision" and "order" in edge:
            raise ValueError(f"{rid}: only revision targets may carry order")
        if role == "item":
            continue
        target_roles[target_id].add(role)
        if len(target_roles[target_id]) > 1:
            raise ValueError(f"{rid}: same document has conflicting applicability/adoption roles")
        document = entities["documents"][target_id]
        if _owner(document) != owner:
            raise ValueError(f"{rid}: annotation targets a different item")
        if kind == "confirmation":
            _confirmation_anchor(row, document, role)
        else:
            _attribution_anchor(row, document)
            key = (target_id, row["anchor"]["paragraph_index"], row["anchor"]["excerpt"])
            if key in state["attributions"]:
                raise ValueError(f"{rid}: duplicate attribution for the same paragraph range")
            state["attributions"].add(key)
        if role == "revision":
            if type(edge.get("order")) is not int or edge["order"] < 0:
                raise ValueError(f"{rid}: revision requires a nonnegative order")
            state["revision_orders"][target_id].append(edge["order"])
    if kind == "confirmation":
        if row.get("scope") != "local_text_or_term" or row.get("status") != "user_confirmed":
            raise ValueError(f"{rid}: confirmation requires local_text_or_term/user_confirmed")
        if not isinstance(row.get("term_glosses"), dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in row["term_glosses"].items()):
            raise ValueError(f"{rid}: invalid term_glosses")
        _review(row.get("confirmation"), rid)
    else:
        if not rid.startswith("s-"):
            raise ValueError(f"{rid}: attribution ID must use s- prefix")
        if row.get("speaker_role") not in ("primary_speaker", "other_speaker", "unknown"):
            raise ValueError(f"{rid}: invalid speaker_role")
        if row.get("viewpoint") not in ("own_view", "quoted_or_read_aloud", "explained_or_paraphrased", "unknown"):
            raise ValueError(f"{rid}: invalid viewpoint")
        if row.get("status") != "human_confirmed":
            raise ValueError(f"{rid}: attribution status must be human_confirmed")
        _review(row.get("review"), rid, attribution=True)


def _cycles(graph, context):
    """Iterative tri-colour walk supports long chains without recursion limits."""
    done = set()
    for start in graph:
        if start in done:
            continue
        active = set()
        stack = [(start, False)]
        while stack:
            node, exiting = stack.pop()
            if exiting:
                active.remove(node)
                done.add(node)
                continue
            if node in active:
                raise ValueError(f"{context}: cycle at {node}")
            if node in done:
                continue
            active.add(node)
            stack.append((node, True))
            for target in reversed(graph.get(node, [])):
                if target in active:
                    raise ValueError(f"{context}: cycle at {target}")
                if target not in done:
                    stack.append((target, False))


def _evidence(value, row, entities):
    if isinstance(value, list):
        for nested in value:
            _evidence(nested, row, entities)
    elif isinstance(value, dict):
        if "transcript_id" in value and "recognition_chunk_ids" in value:
            transcript = entities["documents"].get(value["transcript_id"])
            if transcript is None or transcript.get("kind") != "transcript" or _owner(transcript) != _owner(row):
                raise ValueError(f"{row['id']}: unresolved transcript evidence")
            ids = value["recognition_chunk_ids"]
            known = {chunk["id"] for chunk in transcript.get("recognition_chunks", [])}
            if not isinstance(ids, list) or not ids or any(not isinstance(key, str) or key not in known for key in ids):
                raise ValueError(f"{row['id']}: unresolved recognition chunk evidence")
        for nested in value.values():
            _evidence(nested, row, entities)


def validate_entities(root: Path, entities: dict) -> list[str]:
    """Validate a complete in-memory candidate graph against root artifact bytes."""
    errors, all_ids, text_cache = [], set(), {}
    root = Path(root).resolve()
    state = {"audio_hashes": set(), "restore_paths": set(), "archives": {}, "archive_members": set(), "attributions": set(), "revision_orders": defaultdict(list)}
    kinds_by_entity = dict(zip(ENTITIES, (ITEM_KINDS, DOCUMENT_KINDS, ASSET_KINDS, ANNOTATION_KINDS)))
    for entity in ENTITIES:
        if not isinstance(entities.get(entity), dict):
            errors.append(f"{entity}: expected ID index")
            continue
        for rid, row in entities[entity].items():
            try:
                if not isinstance(row, dict) or row.get("id") != rid or not isinstance(rid, str) or not RECORD_ID_PATTERN.fullmatch(rid):
                    raise ValueError(f"{entity}: invalid record ID {rid!r}")
                if rid in all_ids:
                    raise ValueError(f"Duplicate record ID: {rid}")
                all_ids.add(rid)
                kind = row.get("kind")
                if kind not in kinds_by_entity[entity]:
                    raise ValueError(f"{rid}: unexpected {entity} kind {kind!r}")
                allowed = _ITEM_KEYS if entity == "items" else _DOCUMENT_KEYS[kind] if entity == "documents" else _ASSET_KEYS[kind] if entity == "assets" else _ANNOTATION_KEYS[kind]
                _keys(row, allowed, rid)
                canonical_json(row)  # Reject NaN, infinities and non-JSON values.
                if "metadata" in row and not isinstance(row["metadata"], dict):
                    raise ValueError(f"{rid}: metadata must be an object")
                for url in _array(row.get("urls", []), rid + "/urls"):
                    _https(url, rid)
                for name in ("quality", "metadata"):
                    _recognition_issues(row.get(name), rid)
                    _evidence(row.get(name), row, entities)
                if entity == "items":
                    _item(row, entities)
                elif entity == "documents":
                    _document(row, entities, text_cache)
                elif entity == "assets":
                    _asset(row, root, entities, state)
                else:
                    _annotation(row, entities, state)
            except (ValueError, KeyError, TypeError, IndexError, StopIteration, OSError, InvalidOperation) as exc:
                errors.append(f"{rid}: {exc}")
    for target_id, orders in state["revision_orders"].items():
        if sorted(orders) != list(range(len(orders))):
            errors.append(f"{target_id}: revision orders must be unique and contiguous from zero")
    try:
        _cycles({rid: [row["parent_id"]] if row.get("parent_id") else [] for rid, row in entities["items"].items()}, "item parent")
        documents = entities["documents"]
        for roles in (("derived_from",), ("input_units_from",), ("derived_from", "input_units_from")):
            _cycles({rid: [edge["target_id"] for edge in row.get("inputs", []) if edge.get("role") in roles] for rid, row in documents.items()}, "/".join(roles))
    except (ValueError, KeyError, TypeError) as exc:
        errors.append(str(exc))
    return errors


def validate_native(root: Path) -> list[str]:
    """Return native validation errors without changing records or artifact bytes."""
    try:
        root = Path(root)
        for entity in ENTITIES:
            storage = root / "data" / ("documents" if entity == "documents" else entity + ".jsonl")
            if not (storage.is_dir() if entity == "documents" else storage.is_file()):
                raise ValueError(f"Missing native storage: {storage}")
        return validate_entities(root, _read_entities(root))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        return [str(exc)]
