"""Four-entity archive storage and the lossless v2 version adapter.

Only the standard library is used.  Roots are repository roots (containing
``data``).  Projection is a compatibility view, never a second maintained copy.
Ranges count Unicode code points, as Python string slicing does.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from decimal import Decimal, InvalidOperation
import os
from pathlib import Path
import tempfile

LEGACY_JSONL_TABLES = ("items", "collections", "audio", "confirmations", "attributions")
LEGACY_DOCUMENT_TABLES = ("transcripts", "edited_transcripts", "posts", "articles")
LEGACY_TABLES = LEGACY_JSONL_TABLES + LEGACY_DOCUMENT_TABLES
ENTITIES = ("items", "documents", "assets", "annotations")
SCHEMA_VERSION = 3
_ROOT_KEYS = {
    "items": "schema_version id kind title identifiers urls metadata relations parent_id part_number",
    "collections": "schema_version id kind title identifiers metadata members",
    "audio": "schema_version id kind item_ids availability sha256 size_bytes local_path downloads metadata unavailable_reason",
    "confirmations": "schema_version id kind item_id edited_transcript_ids anchor corrected_text corrected_text_sha256 scope status term_glosses confirmation urls",
    "attributions": "schema_version id kind item_id edited_transcript_id anchor speaker_role viewpoint review status urls",
    "transcripts": "schema_version id kind item_id audio_ids method model language time_unit text segments content_sha256 quality metadata recognition_chunks recognition_chunks_sha256",
    "edited_transcripts": "schema_version id kind item_id transcript_ids model time_unit text paragraphs notes_markdown is_complete quality metadata paragraphs_match_text input_units input_units_from_id derived_from_id confirmation_ids review_document_markdown",
    "posts": "schema_version id kind item_id content article_item_ids text",
    "articles": "schema_version id kind item_id text html text_variant quality",
}
_ROOT_KEYS = {k: set(v.split()) for k, v in _ROOT_KEYS.items()}
_BLOCK_KEYS = set("index start end text chunk_offset_seconds speaker_id input_text input_unit_labels issues".split())
_RELATIONS = {
    "item_id": ("item", False), "item_ids": ("item", True),
    "audio_ids": ("audio", True), "transcript_ids": ("transcript", True),
    "derived_from_id": ("derived_from", False),
    "input_units_from_id": ("input_units_from", False),
    "article_item_ids": ("article_item", True),
}
_METADATA_SYNONYMS = {
    "pubdate": "published_at_unix_seconds", "publish_time": "published_at_unix_seconds",
    "owner_mid": "uploader_id", "upMid": "uploader_id", "owner_name": "uploader_name",
    "description": "desc", "image_url": "image_urls",
}


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def json_sha256(value) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _same(a, b):
    # JSON equality must distinguish booleans, numbers and numeric strings.
    return canonical_json(a) == canonical_json(b)


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f"Nonfinite JSON number: {value}")


def _parse_json(text):
    return json.loads(text, object_pairs_hook=_json_object, parse_constant=_invalid_constant)


def _read(path):
    return _parse_json(Path(path).read_text(encoding="utf-8-sig"))


def _lines(path):
    if not path.exists():
        return
    with path.open(encoding="utf-8-sig") as stream:
        for n, line in enumerate(stream, 1):
            if line.strip():
                try:
                    yield _parse_json(line)
                except ValueError as exc:
                    raise ValueError(f"{path}:{n}: {exc}") from exc


def _safe_id(value):
    if not isinstance(value, str) or not value or any(c in value for c in "/\\:") or value in (".", ".."):
        raise ValueError(f"Invalid record ID: {value!r}")
    return value


def _check_keys(value, allowed, context):
    extra = set(value) - allowed
    if extra:
        raise ValueError(f"{context}: unknown fields: {', '.join(sorted(extra))}")


def is_v3(root) -> bool:
    path = Path(root) / "data" / "schema.json"
    if not path.is_file():
        return False
    version = _read(path).get("schema_version")
    if type(version) is not int or version not in (2, 3):
        raise ValueError(f"Unsupported schema version: {version!r}")
    return version == 3


def iter_native_records(root, entity):
    """Yield (native record, physical Path), ordered by stable ID."""
    if entity not in ENTITIES:
        raise ValueError(f"Unknown entity: {entity}")
    data = Path(root) / "data"
    if entity == "documents":
        for path in sorted((data / entity).glob("*.json")):
            yield _read(path), path
    else:
        path = data / (entity + ".jsonl")
        for row in sorted(_lines(path), key=lambda r: r["id"]):
            yield row, path


def _native_index(root, selected=ENTITIES):
    return {entity: ({row["id"]: row for row, _ in iter_native_records(root, entity)} if entity in selected else {}) for entity in ENTITIES}


def _recipe(table, row):
    _check_keys(row, _ROOT_KEYS[table], f"{table}/{row.get('id')}")
    if row.get("schema_version", 2) != 2:
        raise ValueError(f"{row.get('id')}: expected legacy schema_version 2")
    _safe_id(row["id"])
    return {"table": table, "keys": sorted(row)}


def _metadata_encode(row, recipe):
    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        return
    aliases = {}
    for old, new in _METADATA_SYNONYMS.items():
        if old in metadata and new in metadata and _same(metadata[old], metadata[new]):
            aliases[old] = new
            del metadata[old]
    # Exact scalar observations of a root fact need only a projection recipe.
    for key in ("title", "content_sha256", "language", "model"):
        if key in metadata and key in row and _same(metadata[key], [row[key]]):
            aliases[key] = "$" + key
            del metadata[key]
    if aliases:
        recipe["metadata_aliases"] = aliases


def _metadata_decode(row, recipe):
    metadata = row.get("metadata")
    for old, new in recipe.get("metadata_aliases", {}).items():
        if metadata is None:
            raise ValueError("metadata recipe without metadata")
        metadata[old] = deepcopy([row[new[1:]]]) if new.startswith("$") else deepcopy(metadata[new])


def _timing_issues(segments):
    issues, previous = [], None
    for number, segment in enumerate(segments):
        try:
            start, end = Decimal(str(segment["start"])), Decimal(str(segment["end"]))
            if not start.is_finite() or not end.is_finite():
                raise InvalidOperation
        except (KeyError, InvalidOperation, ValueError):
            issues.append(f"segment {number}: invalid timestamp")
            continue
        if start < 0 or end <= start:
            issues.append(f"segment {number}: expected 0 <= start < end")
        if previous is not None and start < previous:
            issues.append(f"segment {number}: starts must not decrease")
        previous = start
    return issues


def _derive_encode(row, recipe):
    derived = []
    if recipe["table"] == "collections":
        members = row.get("members", [])
        if all(type(m.get("position")) is int and m["position"] == n + 1 for n, m in enumerate(members)):
            for member in members:
                del member["position"]
            derived.append("members.position")
    if "paragraphs_match_text" in row:
        calculated = "\n\n".join(p["text"] for p in row["paragraphs"]).strip() == row["text"].strip()
        if _same(row["paragraphs_match_text"], calculated):
            del row["paragraphs_match_text"]
            derived.append("paragraphs_match_text")
    if recipe["table"] == "transcripts" and isinstance(row.get("quality"), dict):
        quality = row["quality"]
        if "timing_issues" in quality and _same(quality["timing_issues"], _timing_issues(row["segments"])):
            del quality["timing_issues"]
            derived.append("quality.timing_issues")
    if derived:
        recipe["derived"] = derived


def _derive_decode(row, recipe):
    for field in recipe.get("derived", []):
        if field == "members.position":
            for n, member in enumerate(row["members"]):
                member["position"] = n + 1
        elif field == "paragraphs_match_text":
            row[field] = "\n\n".join(p["text"] for p in row["paragraphs"]).strip() == row["text"].strip()
        elif field == "quality.timing_issues":
            row["quality"]["timing_issues"] = _timing_issues(row["segments"])
        else:
            raise ValueError(f"Unknown derived field: {field}")


def _encode_blocks(row, key):
    cursor = 0
    blocks = []
    for index, segment in enumerate(row.pop(key)):
        _check_keys(segment, _BLOCK_KEYS, f"{row['id']}/{key}/{index}")
        block = deepcopy(segment)
        if "index" in block:
            if type(block.pop("index")) is not int or segment["index"] != index:
                raise ValueError(f"{row['id']}: {key} index must equal array position")
        else:
            block["index_absent"] = True
        value = block.pop("text")
        if not isinstance(value, str):
            raise ValueError(f"{row['id']}: block text must be a string")
        start = row["text"].find(value, cursor)
        if start < 0:
            block["literal"] = value
        else:
            block["range"] = [start, start + len(value)]
            cursor = start + len(value)
        blocks.append(block)
    row["blocks"] = blocks


def _block_text(document, block):
    if ("range" in block) == ("literal" in block):
        raise ValueError(f"{document['id']}: exactly one of range/literal is required")
    if "literal" in block:
        if not isinstance(block["literal"], str):
            raise ValueError(f"{document['id']}: literal must be a string")
        return block["literal"]
    bounds = block["range"]
    if not isinstance(bounds, list) or len(bounds) != 2 or any(type(x) is not int for x in bounds):
        raise ValueError(f"{document['id']}: invalid codepoint range")
    start, end = bounds
    if not 0 <= start <= end <= len(document["text"]):
        raise ValueError(f"{document['id']}: range outside text")
    return document["text"][start:end]


def _encode_relations(row):
    inputs = []
    for key, (role, many) in _RELATIONS.items():
        if key in row:
            value = row.pop(key)
            if value is None:
                # A null scalar is a distinct historical value, not an edge.
                continue
            for target in value if many else [value]:
                inputs.append({"role": role, "target_id": target})
    row["inputs"] = inputs


def _artifact(assets, value, kind):
    encoded = value.encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    asset_id = "x-" + digest
    ext = "html" if kind == "html" else "md"
    asset = {"id": asset_id, "kind": kind, "sha256": digest,
             "size_bytes": len(encoded), "local_path": f"data/artifacts/{digest}.{ext}"}
    if asset_id in assets and assets[asset_id]["kind"] != kind:
        asset_id = "x-" + json_sha256([kind, digest])
        asset["id"] = asset_id
    asset["_content"] = value
    assets[asset_id] = asset
    return asset_id


def _source_text(document, source):
    if source == "text":
        return document["text"]
    if source == "input_units":
        return "".join(s["text"] for s in document["input_units"]["base"]["segments"])
    if source in ("segments", "segments_space", "segments_newline"):
        joiner = {"segments": "", "segments_space": " ", "segments_newline": "\n"}[source]
        return joiner.join(_block_text(document, block) for block in document["blocks"])
    raise ValueError(f"Unknown input text source: {source}")


def _transcript_digest(document):
    segments = []
    for n, block in enumerate(document.get("blocks", [])):
        segment = {k: deepcopy(v) for k, v in block.items() if k not in ("range", "literal", "index_absent")}
        segment["text"] = _block_text(document, block)
        if not block.get("index_absent"):
            segment["index"] = n
        segments.append(segment)
    item = next(e["target_id"] for e in document["inputs"] if e["role"] == "item")
    payload = {k: document[k] for k in ("method", "language", "model", "time_unit", "text")}
    payload.update(item_id=item, segments=segments)
    return json_sha256(payload)


def _reference_input_text(documents):
    """Reference exact text only; a snapshot never borrows current timestamps."""
    for document in documents.values():
        if document["_legacy"]["table"] != "edited_transcripts":
            continue
        sources = []
        for edge in document["inputs"]:
            if edge["role"] == "transcript" and edge["target_id"] in documents:
                upstream = documents[edge["target_id"]]
                digest = _transcript_digest(upstream)
                if upstream.get("content_sha256") and upstream["content_sha256"] != digest:
                    raise ValueError(f"{upstream['id']}: legacy content hash mismatch")
                sources.append((upstream, "text", digest))
                sources.append((upstream, "segments", digest))
                sources.append((upstream, "segments_space", digest))
                sources.append((upstream, "segments_newline", digest))
        snapshot_owner = document
        seen = set()
        while "input_units" not in snapshot_owner:
            edge = next((e for e in snapshot_owner["inputs"] if e["role"] == "input_units_from"), None)
            if edge is None or edge["target_id"] in seen or edge["target_id"] not in documents:
                break
            seen.add(edge["target_id"])
            snapshot_owner = documents[edge["target_id"]]
        if isinstance(snapshot_owner.get("input_units"), dict):
            base = snapshot_owner["input_units"].get("base", {})
            if isinstance(base.get("segments"), list):
                sources.append((snapshot_owner, "input_units", json_sha256(base)))
        sources = [(upstream, source, digest, _source_text(upstream, source)) for upstream, source, digest in sources]
        for block in document.get("blocks", []):
            value = block.get("input_text")
            if not isinstance(value, str) or not value:
                continue
            matches = {}
            for upstream, source, digest, text in sources:
                start = text.find(value)
                if start < 0 or text.find(value, start + 1) >= 0:
                    continue
                # Multiple serialization views of one immutable source are not
                # independent evidence; prefer its canonical text view.
                matches.setdefault(upstream["id"], {"target_id": upstream["id"], "content_sha256": digest,
                                                    "source": source, "range": [start, start + len(value)]})
            if len(matches) == 1:
                block["input_text_ref"] = next(iter(matches.values()))
                del block["input_text"]


def _encode_dataset(tables):
    entities = {name: {} for name in ENTITIES}
    document_confirmations = {}
    for table in LEGACY_TABLES:
        for entry in tables.get(table, ()):
            original = entry[0] if isinstance(entry, tuple) else entry
            row = deepcopy(original)
            recipe = _recipe(table, row)
            row.pop("schema_version", None)
            row["_legacy"] = recipe
            _derive_encode(row, recipe)
            if table in ("items", "collections"):
                entity = "items"
            elif table == "audio":
                entity = "assets"
                _encode_relations(row)
                for download in row.get("downloads", []):
                    _check_keys(download, {"archive", "member_path", "release_tag"}, "audio download")
                    archive = download.pop("archive")
                    _check_keys(archive, {"name", "size_bytes", "sha256", "url"}, "archive")
                    aid = "z-" + json_sha256(archive)
                    entities["assets"][aid] = {"id": aid, "kind": "archive", **archive}
                    download["archive_id"] = aid
            elif table in LEGACY_DOCUMENT_TABLES:
                entity = "documents"
                _encode_relations(row)
                key = "segments" if table == "transcripts" else "paragraphs"
                if key in row:
                    _encode_blocks(row, key)
                if "confirmation_ids" in row:
                    document_confirmations[row["id"]] = row.pop("confirmation_ids")
                for field in ("review_document_markdown", "html"):
                    if field in row:
                        value = row.pop(field)
                        if value is None:
                            recipe.setdefault("null_fields", []).append(field)
                        else:
                            asset_id = _artifact(entities["assets"], value, "html" if field == "html" else "review_document")
                            row["inputs"].append({"role": field, "target_id": asset_id})
            else:
                entity = "annotations"
                targets = []
                if "item_id" in row:
                    targets.append({"role": "item", "target_id": row.pop("item_id")})
                if "edited_transcript_ids" in row:
                    targets.extend({"role": "applies_to", "target_id": target} for target in row.pop("edited_transcript_ids"))
                if "edited_transcript_id" in row:
                    targets.append({"role": "applies_to", "target_id": row.pop("edited_transcript_id")})
                row["targets"] = targets
            _metadata_encode(row, recipe)
            if row["id"] in entities[entity]:
                raise ValueError(f"Duplicate {entity} ID: {row['id']}")
            entities[entity][row["id"]] = row
    for document_id, ids in document_confirmations.items():
        for index, annotation_id in enumerate(ids):
            annotation = entities["annotations"].get(annotation_id)
            if annotation is None or annotation["_legacy"]["table"] != "confirmations":
                raise ValueError(f"{document_id}: missing confirmation {annotation_id}")
            edge = next((e for e in annotation["targets"] if e["target_id"] == document_id), None)
            if edge is None:
                raise ValueError(f"{document_id}: confirmation {annotation_id} does not apply")
            if "confirmation_index" in edge:
                raise ValueError(f"{document_id}: duplicate confirmation {annotation_id}")
            edge["confirmation_index"] = index
            if any(e["role"] == "derived_from" for e in entities["documents"][document_id]["inputs"]):
                edge["role"] = "revision"
    _reference_input_text(entities["documents"])
    return entities


def _resolve_input_text(ref, entities):
    _check_keys(ref, {"target_id", "content_sha256", "source", "range"}, "input_text_ref")
    document = entities["documents"][ref["target_id"]]
    source = ref["source"]
    cache = entities.setdefault("_text_cache", {})
    cache_key = (ref["target_id"], source)
    if cache_key not in cache:
        digest = json_sha256(document["input_units"]["base"]) if source == "input_units" else _transcript_digest(document)
        if source != "input_units" and document.get("content_sha256") and document["content_sha256"] != digest:
            raise ValueError(f"{document['id']}: legacy content hash mismatch")
        cache[cache_key] = (digest, _source_text(document, source))
    digest, text = cache[cache_key]
    if digest != ref["content_sha256"]:
        raise ValueError(f"{ref['target_id']}: input text content hash mismatch")
    bounds = ref["range"]
    if not isinstance(bounds, list) or len(bounds) != 2 or any(type(n) is not int for n in bounds) or not 0 <= bounds[0] <= bounds[1] <= len(text):
        raise ValueError("Invalid input_text_ref range")
    return text[bounds[0]:bounds[1]]


def _project(native, entities, root):
    row = deepcopy(native)
    recipe = row.pop("_legacy")
    keys = set(recipe["keys"])
    table = recipe["table"]
    row["schema_version"] = 2
    if "inputs" in row:
        inputs = row.pop("inputs")
        for key, (role, many) in _RELATIONS.items():
            if key in keys:
                targets = [e["target_id"] for e in inputs if e["role"] == role]
                row[key] = targets if many else (targets[0] if targets else None)
        for field in ("review_document_markdown", "html"):
            if field in keys:
                if field in recipe.get("null_fields", []):
                    row[field] = None
                else:
                    edge = next(e for e in inputs if e["role"] == field)
                    asset = entities["assets"][edge["target_id"]]
                    row[field] = asset.get("_content") if "_content" in asset else _artifact_text(root, asset)
    if "blocks" in row:
        blocks = row.pop("blocks")
        segments = []
        for index, block in enumerate(blocks):
            text = _block_text(row, block)
            segment = {k: deepcopy(v) for k, v in block.items() if k not in {"range", "literal", "index_absent", "input_text_ref"}}
            segment["text"] = text
            if not block.get("index_absent"):
                segment["index"] = index
            if "input_text_ref" in block:
                segment["input_text"] = _resolve_input_text(block["input_text_ref"], entities)
            segments.append(segment)
        row["segments" if table == "transcripts" else "paragraphs"] = segments
    if "confirmation_ids" in keys:
        edges = [(e["confirmation_index"], a["id"]) for a in entities["annotations"].values() for e in a.get("targets", [])
                 if e["target_id"] == row["id"] and "confirmation_index" in e]
        row["confirmation_ids"] = [aid for _, aid in sorted(edges)]
    if "targets" in row:
        targets = row.pop("targets")
        if "item_id" in keys:
            row["item_id"] = next(e["target_id"] for e in targets if e["role"] == "item")
        applicable = [e["target_id"] for e in targets if e["role"] in ("applies_to", "revision")]
        if "edited_transcript_ids" in keys:
            row["edited_transcript_ids"] = applicable
        if "edited_transcript_id" in keys:
            row["edited_transcript_id"] = applicable[0]
    if table == "audio":
        for download in row.get("downloads", []):
            archive = entities["assets"][download.pop("archive_id")]
            download["archive"] = {k: deepcopy(v) for k, v in archive.items() if k not in {"schema_version", "id", "kind"}}
    _derive_decode(row, recipe)
    _metadata_decode(row, recipe)
    missing = keys - set(row)
    if missing:
        raise ValueError(f"{row['id']}: legacy projection missing fields {sorted(missing)}")
    return {k: row[k] for k in recipe["keys"]}


def _artifact_text(root, asset):
    path = _artifact_path(root, asset["local_path"])
    payload = path.read_bytes()
    if len(payload) != asset["size_bytes"] or hashlib.sha256(payload).hexdigest() != asset["sha256"]:
        raise ValueError(f"{asset['id']}: artifact byte hash mismatch")
    return payload.decode("utf-8")


def _artifact_path(root, relative):
    if not isinstance(relative, str) or "\\" in relative or ":" in relative:
        raise ValueError(f"Invalid artifact path: {relative!r}")
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root / "data" / "artifacts"):
        raise ValueError(f"Artifact escapes data/artifacts: {relative}")
    return path


def iter_legacy_records(root, table):
    """Yield exact old JSON values with the actual native physical record path."""
    if table not in LEGACY_TABLES:
        raise ValueError(f"Unknown table: {table}")
    root = Path(root)
    if not is_v3(root):
        if table in LEGACY_JSONL_TABLES:
            path = root / "data" / (table + ".jsonl")
            for row in _lines(path):
                yield row, path
        else:
            for path in sorted((root / "data" / table).glob("*.json")):
                yield _read(path), path
        return
    entity = "items" if table in ("items", "collections") else "assets" if table == "audio" else "documents" if table in LEGACY_DOCUMENT_TABLES else "annotations"
    selected = (entity,) if entity in ("items", "assets", "annotations") else ("documents", "assets", "annotations")
    entities = _native_index(root, selected)
    for row in sorted(entities[entity].values(), key=lambda r: r["id"]):
        if row.get("_legacy", {}).get("table") == table:
            path = root / "data" / (f"documents/{row['id']}.json" if entity == "documents" else entity + ".jsonl")
            yield _project(row, entities, root), path


def load_legacy_record(root, record_id) -> dict:
    """Load one document and only the dependencies needed by its projection."""
    root = Path(root)
    record_id = _safe_id(record_id)
    if not is_v3(root):
        raise ValueError("load_legacy_record requires schema v3")
    path = root / "data" / "documents" / (record_id + ".json")
    row = _read(path)
    entities = {name: {} for name in ENTITIES}
    entities["documents"][record_id] = row
    needs_assets = any(e["role"] in ("html", "review_document_markdown") for e in row.get("inputs", []))
    if needs_assets:
        entities["assets"] = {r["id"]: r for r, _ in iter_native_records(root, "assets")}
    if "confirmation_ids" in row["_legacy"]["keys"]:
        entities["annotations"] = {r["id"]: r for r, _ in iter_native_records(root, "annotations")}
    for block in row.get("blocks", []):
        ref = block.get("input_text_ref")
        if ref and ref["target_id"] not in entities["documents"]:
            target = _safe_id(ref["target_id"])
            entities["documents"][target] = _read(root / "data" / "documents" / (target + ".json"))
    return _project(row, entities, root)


def _atomic_bytes(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == payload:
        return False
    fd, temp = tempfile.mkstemp(prefix=".schema-v3-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
        os.replace(temp, path)  # Detaches hardlinked candidate files.
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return True


def _write_entities(root, entities):
    root = Path(root)
    changed = []
    wanted = set()
    old_artifacts = []
    for asset in _lines(root / "data" / "assets.jsonl"):
        if asset.get("kind") in ("review_document", "html") and "local_path" in asset:
            old_artifacts.append(_artifact_path(root, asset["local_path"]))
    (root / "data" / "documents").mkdir(parents=True, exist_ok=True)
    for entity in ENTITIES:
        rows = sorted(entities[entity].values(), key=lambda r: r["id"])
        for row in rows:
            if "_content" in row:
                path = _artifact_path(root, row["local_path"])
                wanted.add(path)
                if _atomic_bytes(path, row.pop("_content").encode("utf-8")):
                    changed.append(path.relative_to(root.resolve()))
        if entity == "documents":
            for row in rows:
                path = root / "data" / "documents" / (row["id"] + ".json")
                wanted.add(path.resolve())
                if path.exists() and _same(_read(path), row):
                    continue
                if _atomic_bytes(path, (json.dumps(row, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")):
                    changed.append(path.relative_to(root))
        else:
            path = root / "data" / (entity + ".jsonl")
            wanted.add(path.resolve())
            payload = "".join(canonical_json(row) + "\n" for row in rows).encode("utf-8")
            if _atomic_bytes(path, payload):
                changed.append(path.relative_to(root))
    # Remove only known native record/artifact paths, never arbitrary user files.
    stale_candidates = list((root / "data" / "documents").glob("*.json")) + old_artifacts
    for path in stale_candidates:
        if path.is_file() and path.resolve() not in wanted:
            path.unlink()
            changed.append(path.resolve().relative_to(root.resolve()))
    schema = {"schema_version": 3, "entities": list(ENTITIES), "range_unit": "unicode_codepoint", "range_end": "exclusive"}
    path = root / "data" / "schema.json"
    if _atomic_bytes(path, (json.dumps(schema, ensure_ascii=False, indent=2) + "\n").encode("utf-8")):
        changed.append(path.relative_to(root))
    return changed


def write_legacy_dataset(root, tables) -> dict:
    """Encode a complete legacy-value dataset; unknown fields fail before writes."""
    root = Path(root)
    unknown = set(tables) - set(LEGACY_TABLES)
    if unknown:
        raise ValueError(f"Unknown tables: {sorted(unknown)}")
    # Refuse legacy files in destination: the native write must never dual-write.
    old = [root / "data" / (t + ".jsonl") for t in LEGACY_JSONL_TABLES if t != "items"]
    old += [root / "data" / t for t in LEGACY_DOCUMENT_TABLES]
    if any(p.exists() for p in old):
        raise ValueError("Destination contains legacy table files")
    entities = _encode_dataset(tables)
    counts = {name: len(rows) for name, rows in entities.items()}
    legacy_counts = dict(Counter(row["_legacy"]["table"] for rows in entities.values() for row in rows.values() if "_legacy" in row))
    artifacts = [{k: v for k, v in row.items() if k != "_content"} for row in entities["assets"].values() if "_content" in row]
    changed = _write_entities(root, entities)
    return {"schema_version": 3, "counts": counts, "legacy_counts": legacy_counts,
            "artifacts": artifacts, "changed_paths": [p.as_posix() for p in changed]}


def _all_legacy(root):
    errors = validate_native(root)
    if errors:
        raise ValueError("Invalid native dataset: " + "; ".join(errors))
    entities = _native_index(root)
    # Projection writers must fail closed on standalone native facts that have
    # no lossless legacy representation, rather than silently discarding them.
    referenced_assets = {e["target_id"] for row in entities["documents"].values() for e in row.get("inputs", []) if e["role"] in ("html", "review_document_markdown")}
    referenced_assets.update(d["archive_id"] for row in entities["assets"].values() for d in row.get("downloads", []))
    for asset in entities["assets"].values():
        if "_legacy" not in asset and asset["id"] not in referenced_assets:
            raise ValueError(f"{asset['id']}: standalone native asset requires a native writer")
    tables = {table: [] for table in LEGACY_TABLES}
    for entity in ENTITIES:
        for row in entities[entity].values():
            if "_legacy" in row:
                tables[row["_legacy"]["table"]].append(_project(row, entities, root))
    # Prove that the adapter can carry every native fact before any write.
    # Cardinality checks cover known graph mistakes; this final comparison
    # also seals future projection seams and noncanonical native provenance.
    reconstructed = _encode_dataset(tables)
    for entity in ENTITIES:
        if set(entities[entity]) != set(reconstructed[entity]):
            raise ValueError(f"{entity}: native facts have no lossless legacy projection")
        for rid, original in entities[entity].items():
            projected = reconstructed[entity][rid]
            if "_content" in projected:
                projected = {key: value for key, value in projected.items() if key != "_content"}
            if not _same(original, projected):
                raise ValueError(f"{rid}: native facts have no lossless legacy projection")
    return tables


def replace_legacy_records(root, table, rows) -> dict:
    if table not in LEGACY_TABLES:
        raise ValueError(f"Unknown table: {table}")
    if not is_v3(root):
        raise ValueError("replace_legacy_records requires schema v3")
    tables = _all_legacy(root)
    tables[table] = list(rows)
    return write_legacy_dataset(root, tables)


def write_legacy_updates(root, updates) -> list[Path]:
    """Upsert legacy-value records in one batch; return changed relative paths."""
    if not is_v3(root):
        raise ValueError("write_legacy_updates requires schema v3")
    if set(updates) - set(LEGACY_TABLES):
        raise ValueError("Unknown update table")
    tables = _all_legacy(root)
    for table, rows in updates.items():
        index = {r["id"]: r for r in tables[table]}
        for entry in rows:
            row = entry[0] if isinstance(entry, tuple) else entry
            index[row["id"]] = row
        tables[table] = list(index.values())
    return [Path(p) for p in write_legacy_dataset(root, tables)["changed_paths"]]


def migrate_v2(source_root, destination_root) -> dict:
    source_root, destination_root = Path(source_root), Path(destination_root)
    if is_v3(source_root):
        raise ValueError("Source already uses schema v3")
    if (destination_root / "data").exists():
        raise ValueError("Migration destination data must not exist")
    tables = {table: [row for row, _ in iter_legacy_records(source_root, table)] for table in LEGACY_TABLES}
    return write_legacy_dataset(destination_root, tables)


def validate_native(root) -> list[str]:
    """Check native structure, reference integrity, hashes and projection recipes."""
    errors = []
    root = Path(root)
    try:
        if not is_v3(root):
            return ["data/schema.json must declare schema_version 3"]
        schema = _read(root / "data" / "schema.json")
        _check_keys(schema, {"schema_version", "entities", "range_unit", "range_end"}, "data/schema.json")
        if schema.get("entities") != list(ENTITIES) or schema.get("range_unit") != "unicode_codepoint" or schema.get("range_end") != "exclusive":
            errors.append("data/schema.json has invalid entities or range contract")
    except (ValueError, OSError) as exc:
        return [str(exc)]
    for entity in ENTITIES:
        path = root / "data" / ("documents" if entity == "documents" else entity + ".jsonl")
        if not (path.is_dir() if entity == "documents" else path.is_file()):
            errors.append(f"Missing native storage: {path}")
    entities = {name: {} for name in ENTITIES}
    for entity in ENTITIES:
        try:
            for row, path in iter_native_records(root, entity):
                rid = _safe_id(row["id"])
                if rid in entities[entity]:
                    raise ValueError(f"Duplicate {entity} ID: {rid}")
                entities[entity][rid] = row
                if "schema_version" in row:
                    raise ValueError(f"{rid}: schema_version belongs in data/schema.json")
                if entity == "documents" and path.stem != rid:
                    raise ValueError(f"{rid}: document filename mismatch")
        except (ValueError, KeyError, TypeError, OSError) as exc:
            errors.append(str(exc))
    for entity in ENTITIES:
        for row in entities[entity].values():
            rid = row["id"]
            try:
                recipe = row.get("_legacy")
                if recipe:
                    _check_keys(recipe, {"table", "keys", "metadata_aliases", "null_fields", "derived"}, rid + " recipe")
                    table = recipe["table"]
                    keys = recipe["keys"]
                    if not isinstance(keys, list) or any(not isinstance(key, str) for key in keys) or len(set(keys)) != len(keys):
                        raise ValueError(f"{rid}: invalid legacy projection keys")
                    if table not in LEGACY_TABLES or set(keys) - _ROOT_KEYS[table]:
                        raise ValueError(f"{rid}: invalid legacy projection keys")
                    for helper, eligible in (("inputs", table == "audio" or table in LEGACY_DOCUMENT_TABLES),
                                             ("targets", table in ("confirmations", "attributions")),
                                             ("blocks", "segments" in keys or "paragraphs" in keys)):
                        if helper in row and (not eligible or not isinstance(row[helper], list)):
                            raise ValueError(f"{rid}: {helper} has no legacy projection structure")
                    for field in recipe.get("null_fields", []):
                        if field not in ("review_document_markdown", "html") or field not in keys:
                            raise ValueError(f"{rid}: invalid null projection field: {field}")
                    expected_entity = "items" if table in ("items", "collections") else "assets" if table == "audio" else "documents" if table in LEGACY_DOCUMENT_TABLES else "annotations"
                    kinds = {"transcripts": {"transcript"}, "edited_transcripts": {"edited_transcript"}, "posts": {"post"}, "articles": {"article"}, "audio": {"audio"}, "confirmations": {"confirmation"}, "attributions": {"segment_attribution"}, "collections": {"article_collection", "video_collection", "video_series"}, "items": {"video", "video_part", "audio_recording", "post", "article", "person"}}
                    if entity != expected_entity or row.get("kind") not in kinds[table]:
                        raise ValueError(f"{rid}: projection table/entity/kind mismatch")
                    allowed = (set(recipe["keys"]) - set(_RELATIONS) - {"segments", "paragraphs", "confirmation_ids", "review_document_markdown", "html", "edited_transcript_ids", "edited_transcript_id"}) | {"_legacy", "inputs", "targets", "blocks"}
                    _check_keys(row, allowed, rid)
                elif entity == "assets":
                    if row["kind"] in ("review_document", "html"):
                        allowed = {"id", "kind", "size_bytes", "sha256", "local_path"}
                        _check_keys(row, allowed, rid)
                        _artifact_text(root, row)
                    elif row["kind"] == "archive":
                        allowed = {"id", "kind", "name", "size_bytes", "sha256", "url"}
                        _check_keys(row, allowed, rid)
                    else:
                        raise ValueError(f"{rid}: unknown asset kind")
                else:
                    raise ValueError(f"{rid}: missing projection recipe")
                if entity == "items":
                    item_targets = []
                    if row.get("parent_id") is not None:
                        item_targets.append(("parent_id", row["parent_id"]))
                    for field, target_key in (("members", "item_id"), ("relations", "target_item_id")):
                        if field not in row:
                            continue
                        if not isinstance(row[field], list):
                            raise ValueError(f"{rid}: {field} must be an array")
                        for index, member in enumerate(row[field]):
                            if not isinstance(member, dict) or target_key not in member:
                                raise ValueError(f"{rid}: {field}/{index} requires {target_key}")
                            item_targets.append((f"{field}/{index}/{target_key}", member[target_key]))
                    for field, target in item_targets:
                        if not isinstance(target, str) or target not in entities["items"]:
                            raise ValueError(f"{rid}: missing item target at {field}: {target!r}")
                input_counts = Counter(edge["role"] for edge in row.get("inputs", []))
                if recipe:
                    for key, (role, many) in _RELATIONS.items():
                        if key in recipe["keys"] and not many and input_counts[role] > 1:
                            raise ValueError(f"{rid}: scalar input role {role} has multiple targets")
                    for field in ("review_document_markdown", "html"):
                        if field in recipe["keys"]:
                            expected = 0 if field in recipe.get("null_fields", []) else 1
                            if input_counts[field] != expected:
                                raise ValueError(f"{rid}: artifact input role {field} must have {expected} target(s)")
                for edge in row.get("inputs", []):
                    _check_keys(edge, {"role", "target_id"}, rid + " input")
                    role = edge["role"]
                    if recipe:
                        projected_roles = {value[0] for key, value in _RELATIONS.items() if key in recipe["keys"]}
                        projected_roles.update(field for field in ("html", "review_document_markdown") if field in recipe["keys"])
                        if role not in projected_roles:
                            raise ValueError(f"{rid}: input has no legacy projection key: {role}")
                    target_entity = "items" if role in ("item", "article_item") else "assets" if role in ("audio", "html", "review_document_markdown") else "documents"
                    if role not in {r[0] for r in _RELATIONS.values()} | {"html", "review_document_markdown"}:
                        raise ValueError(f"{rid}: unknown input role {role}")
                    if edge["target_id"] not in entities[target_entity]:
                        raise ValueError(f"{rid}: missing {role} target {edge['target_id']}")
                previous = 0
                for block in row.get("blocks", []):
                    _check_keys(block, (_BLOCK_KEYS - {"index", "text"}) | {"range", "literal", "index_absent", "input_text_ref"}, rid + " block")
                    _block_text(row, block)
                    if "range" in block:
                        if block["range"][0] < previous:
                            raise ValueError(f"{rid}: block ranges out of order")
                        previous = block["range"][1]
                    if "input_text_ref" in block:
                        if "input_text" in block:
                            raise ValueError(f"{rid}: duplicate input text representation")
                        _resolve_input_text(block["input_text_ref"], entities)
                if recipe and "targets" in row:
                    item_count = sum(edge["role"] == "item" for edge in row["targets"])
                    applicable_count = sum(edge["role"] in ("applies_to", "revision") for edge in row["targets"])
                    if item_count != (1 if "item_id" in recipe["keys"] else 0):
                        raise ValueError(f"{rid}: scalar annotation item target must have exactly one value")
                    if "edited_transcript_id" in recipe["keys"] and applicable_count != 1:
                        raise ValueError(f"{rid}: scalar annotation applies_to target must have exactly one value")
                    if not {"edited_transcript_id", "edited_transcript_ids"}.intersection(recipe["keys"]) and applicable_count:
                        raise ValueError(f"{rid}: annotation target has no legacy projection key")
                for edge in row.get("targets", []):
                    _check_keys(edge, {"role", "target_id", "confirmation_index"}, rid + " target")
                    if edge["role"] not in ("item", "applies_to", "revision"):
                        raise ValueError(f"{rid}: unknown annotation role")
                    target_entity = "items" if edge["role"] == "item" else "documents"
                    if edge["target_id"] not in entities[target_entity]:
                        raise ValueError(f"{rid}: missing annotation target {edge['target_id']}")
                    if edge["role"] != "item":
                        target = entities["documents"][edge["target_id"]]
                        owner = next((e["target_id"] for e in row["targets"] if e["role"] == "item"), None)
                        target_owner = next((e["target_id"] for e in target.get("inputs", []) if e["role"] == "item"), None)
                        if owner != target_owner:
                            raise ValueError(f"{rid}: annotation targets a different item")
                        if edge["role"] == "revision" and not any(e["role"] == "derived_from" for e in target.get("inputs", [])):
                            raise ValueError(f"{rid}: revision target has no derivation")
                    if "confirmation_index" in edge:
                        if type(edge["confirmation_index"]) is not int or edge["confirmation_index"] < 0 or row.get("kind") != "confirmation" or edge["role"] == "item":
                            raise ValueError(f"{rid}: invalid confirmation projection index")
                        if "confirmation_ids" not in entities["documents"][edge["target_id"]]["_legacy"]["keys"]:
                            raise ValueError(f"{rid}: confirmation index has no target projection key")
                if recipe:
                    legacy = _project(row, entities, root)
                    if recipe["table"] == "transcripts" and all(k in legacy for k in ("item_id", "method", "language", "model", "time_unit", "text", "segments", "content_sha256")):
                        payload = {k: legacy[k] for k in ("item_id", "method", "language", "model", "time_unit", "text", "segments")}
                        if json_sha256(payload) != legacy["content_sha256"]:
                            raise ValueError(f"{rid}: legacy content_sha256 mismatch")
                    if "recognition_chunks_sha256" in legacy and json_sha256(legacy.get("recognition_chunks")) != legacy["recognition_chunks_sha256"]:
                        raise ValueError(f"{rid}: recognition chunks hash mismatch")
                    if recipe["table"] == "audio":
                        for download in row.get("downloads", []):
                            if download["archive_id"] not in entities["assets"]:
                                raise ValueError(f"{rid}: missing archive asset")
            except (ValueError, KeyError, TypeError, IndexError, StopIteration, OSError) as exc:
                errors.append(f"{rid}: {exc}")
    confirmation_indices = {}
    for annotation in entities["annotations"].values():
        for target in annotation.get("targets", []):
            if isinstance(target, dict) and "confirmation_index" in target:
                confirmation_indices.setdefault(target.get("target_id"), []).append(target["confirmation_index"])
    for target_id, indices in confirmation_indices.items():
        if any(type(index) is not int for index in indices) or sorted(indices) != list(range(len(indices))):
            errors.append(f"{target_id}: confirmation projection indices must be unique and contiguous from zero")
    for table in LEGACY_JSONL_TABLES:
        if table != "items" and (root / "data" / (table + ".jsonl")).exists():
            errors.append(f"Legacy table remains: {table}")
    for table in LEGACY_DOCUMENT_TABLES:
        if (root / "data" / table).exists():
            errors.append(f"Legacy directory remains: {table}")
    return errors
