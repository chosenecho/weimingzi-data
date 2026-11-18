"""Native insert/replace guards, identity checks, and source-to-graph binding."""

from __future__ import annotations

import copy

from ..records import canonical_json, input_ids, json_sha256
from .errors import IngestError, require
from .manifest import NAMESPACES, array, bili_url, integer, validate_media
from .policy import POLICY


def append_only(old, new, label):
    require(isinstance(old, list) and isinstance(new, list)
            and canonical_json(new[:len(old)]) == canonical_json(old),
            f"Replacement loses or reorders {label}", "RECORD_CONFLICT", 3)


def validate_write(entity, row, old, producer_run_id):
    """Automatic collection has no permission to create human evidence facts.

    A complete replacement is still constrained by the meaning of the record:
    existing results, snapshots, quality and provenance remain immutable. There
    is no partial-payload merge, fallback schema, or inferred human authority.
    """
    require(entity != "annotations", "Automatic producer cannot write annotations", "WRITE_PERMISSION_DENIED", 3)
    if old is None:
        require(row.get("kind") in POLICY["insert_kinds"][entity],
                "Record kind requires human maintenance", "WRITE_PERMISSION_DENIED", 3)
        quality = row.get("quality", {})
        require(isinstance(quality, dict)
                and quality.keys() <= {"is_fully_human_reviewed", "requires_review", "is_subtitle_export_enabled", "timing_issues"}
                and quality.get("is_fully_human_reviewed") is not True,
                "Automatic producer cannot grant human review or confirmed silence", "WRITE_PERMISSION_DENIED", 3)
        if entity == "documents" and row["kind"] == "transcript":
            require(isinstance(row.get("model"), dict) and row["model"].get("name")
                    and isinstance(row.get("method"), str) and row["method"].startswith(("asr", "subtitle")),
                    "Automatic transcript needs machine/source provenance", "WRITE_PERMISSION_DENIED", 3)
        if entity == "documents" and row["kind"] == "edited_transcript":
            require(row.get("quality", {}).get("requires_review") is True
                    and isinstance(row.get("model"), dict) and row["model"].get("name")
                    and not input_ids(row, "derived_from") and not input_ids(row, "input_units_from"),
                    "Automatic edited transcript must retain model provenance and require review",
                    "WRITE_PERMISSION_DENIED", 3)
    fields = set(POLICY["append_fields"][entity])
    before_metadata = (old or {}).get("metadata", {})
    metadata = row.get("metadata", {})
    require(isinstance(before_metadata, dict) and isinstance(metadata, dict), "Invalid observation metadata")
    require(before_metadata.keys() <= metadata.keys(), "Replacement drops observation metadata", "RECORD_CONFLICT", 3)
    for key, observations in metadata.items():
        if key in before_metadata and canonical_json(observations) == canonical_json(before_metadata[key]):
            continue
        previous = before_metadata.get(key, [])
        array(observations, maximum=100000)
        append_only(previous, observations, f"metadata.{key}")
        added = observations[len(previous):]
        if added:
            require(key in POLICY["observation_fields"][entity],
                    "Observation field is outside producer permissions", "WRITE_PERMISSION_DENIED", 3)
        if key == "media_assets":
            for asset in added:
                validate_media(asset)
                require(asset["verification"]["producer_run_id"] == producer_run_id,
                        "Media readback belongs to a different producer run", "MEDIA_UNVERIFIED")
    if entity == "items":
        for url in row.get("urls", []):
            bili_url(url)
        for relation in row.get("relations", []):
            require(isinstance(relation, dict)
                    and relation.get("kind") in ("has_full_text", "references_video", "references")
                    and isinstance(relation.get("evidence"), str) and relation["evidence"],
                    "Item relationship requires explicit reference evidence", "SOURCE_SCOPE_VIOLATION")
    if old is None:
        return
    # Missing keys and explicit null are distinct native facts.
    mutable = {"metadata", *fields}
    distribution = entity == "assets" and old.get("kind") == "audio" and old.get("availability") == "unavailable" and row.get("availability") == "available"
    if distribution:
        mutable.update(("availability", "local_path", "downloads", "size_bytes", "unavailable_reason"))
        require(row.get("downloads") and isinstance(row.get("local_path"), str)
                and integer(row.get("size_bytes"), 1) and "unavailable_reason" not in row,
                "Restored audio needs its verified distribution facts", "MEDIA_UNVERIFIED")
        if "size_bytes" in old:
            require(canonical_json(row.get("size_bytes")) == canonical_json(old["size_bytes"]), "Audio byte size changed", "RECORD_CONFLICT", 3)
        if "local_path" in old:
            require(row.get("local_path") == old["local_path"], "Audio restore path changed", "RECORD_CONFLICT", 3)
    require(canonical_json({k: v for k, v in old.items() if k not in mutable})
            == canonical_json({k: v for k, v in row.items() if k not in mutable}),
            "Replacement changes immutable native facts; create a distinct result instead", "RECORD_CONFLICT", 3)
    for field in fields:
        append_only(old.get(field, []), row.get(field, []), field)


def merge_record(op, payload, old, producer_run_id):
    # The desired complete post-state already exists: do not evaluate a stale CAS.
    if old is not None and canonical_json(old) == canonical_json(payload):
        return old, "unchanged"
    if op["op"] == "insert":
        require(old is None, "Existing ID has different content", "RECORD_CONFLICT", 3)
    else:
        require(old is not None, "Replacement target is missing", "RECORD_CONFLICT", 3)
        require(json_sha256(old) == op["expected_record_sha256"], "Record precondition is stale", "PRECONDITION_FAILED", 4)
    validate_write(op["entity"], payload, old, producer_run_id)
    return copy.deepcopy(payload), "inserted" if old is None else "replaced"


def identity_keys(entity, row):
    if entity == "items":
        for namespace, values in row.get("identifiers", {}).items():
            if row.get("kind") == "video_part" and namespace != "bilibili_part":
                continue
            for value in values if isinstance(values, list) else [values]:
                yield ("external", row.get("kind"), namespace, canonical_json(value))
        if row.get("kind") == "video_part":
            yield ("parent_part", row.get("parent_id"), row.get("part_number"))
            for cid in row.get("metadata", {}).get("cid", []):
                yield ("cid", str(cid))
    elif entity == "assets" and row.get("kind") == "audio":
        if row.get("sha256"):
            yield ("audio_sha256", row["sha256"])
    elif entity == "documents":
        if row.get("kind") == "transcript":
            yield ("transcript_sha256", row.get("content_sha256"))
        elif row.get("kind") == "edited_transcript" and not input_ids(row, "derived_from"):
            for revision in row.get("metadata", {}).get("upstream_revision_id", []):
                yield ("ai_revision", tuple(input_ids(row, "item")), canonical_json(revision))


class IdentityIndex:
    def __init__(self, entities):
        self.keys, self.ids = {}, {}
        for entity, rows in entities.items():
            for rid, row in rows.items():
                require(rid not in self.ids, "Baseline ID occurs in multiple entities", "IDENTITY_AMBIGUOUS", 3)
                self.ids[rid] = entity
                for key in identity_keys(entity, row):
                    self.keys.setdefault(key, set()).add(rid)

    def add(self, entity, row, existing=False):
        rid = row["id"]
        require(rid not in self.ids or (existing and self.ids[rid] == entity),
                "Record ID already belongs to another entity", "IDENTITY_AMBIGUOUS", 3)
        for key in identity_keys(entity, row):
            require(not self.keys.get(key, set()) - {rid}, "External/content identity already has a different ID", "IDENTITY_AMBIGUOUS", 3)
        self.ids[rid] = entity
        for key in identity_keys(entity, row):
            self.keys.setdefault(key, set()).add(rid)


def item_matches(item, source):
    identifiers = item.get("identifiers", {})
    if source["external_id"] not in identifiers.get(source["namespace"], []):
        return False
    allowed = {"bilibili_bvid": ("video", "video_part"), "bilibili_cvid": ("article",),
               "bilibili_dynamic": ("post", "article"), "bilibili_opus": ("post", "article")}
    if item.get("kind") not in allowed[source["namespace"]]:
        return False
    if item["kind"] == "video_part":
        if source.get("part_number") != item.get("part_number"):
            return False
        require("cid" in source, "A part-bound source needs CID", "SOURCE_SCOPE_VIOLATION")
        cids = item.get("metadata", {}).get("cid", [])
        require(len(cids) == 1 and type(cids[0]) in (str, int) and str(cids[0]) == source["cid"],
                "BV/part CID changed or is ambiguous", "CID_CHANGED", 3)
        require(identifiers.get("bilibili_part") == [f"{source['external_id']}:P{item['part_number']}"],
                "Part identity disagrees with BV and part number", "IDENTITY_AMBIGUOUS", 3)
    owners = item.get("metadata", {}).get("uploader_id", [])
    require(not owners or source["publisher_uid"] is None or all(type(v) in (str, int) and str(v) == source["publisher_uid"] for v in owners),
            "Source publisher disagrees with item owner", "SOURCE_SCOPE_VIOLATION")
    return True


def record_items(entity, row, entities):
    if entity == "items":
        if row.get("kind") in ("video_collection", "video_series"):
            return {m["item_id"] for m in row.get("members", [])}
        return {row["id"]}
    if entity == "assets" and row.get("kind") == "archive":
        return {iid for asset in entities["assets"].values()
                if any(d.get("archive_id") == row["id"] for d in asset.get("downloads", []))
                for iid in input_ids(asset, "item")}
    return set(input_ids(row, "item")) | set(input_ids(row, "article_item"))


def validate_scope(batch, entities, baseline):
    """Bind every operation to its actual native item and reference graph."""
    sources = {s["source_id"]: s for s in batch.manifest["sources"]}
    items, documents, assets = (entities[e] for e in ("items", "documents", "assets"))
    bound = {sid: {rid for rid, item in items.items() if item_matches(item, source)} for sid, source in sources.items()}
    for sid, source in sources.items():
        require(bound[sid], "Source has no matching item", "SOURCE_SCOPE_VIOLATION")
        for referring in source["referenced_by"]:
            targets = {r.get("target_item_id") for iid in bound[referring] for r in items[iid].get("relations", [])}
            targets.update(a for doc in documents.values() if set(input_ids(doc, "item")) & bound[referring] for a in input_ids(doc, "article_item"))
            require(targets & bound[sid], "Referenced source lacks an actual item relationship", "SOURCE_SCOPE_VIOLATION")
    for op in batch.manifest["operations"]:
        entity, rid = op["entity"], op["record_id"]
        row = entities[entity][rid]
        affected = record_items(entity, row, entities)
        require(affected, "Operation needs associated source items", "SOURCE_SCOPE_VIOLATION")
        old = baseline[entity].get(rid, {})
        if entity == "items":
            for namespace in NAMESPACES:
                for external_id in row.get("identifiers", {}).get(namespace, []):
                    require(any(s["namespace"] == namespace and s["external_id"] == external_id for s in sources.values()),
                            "Item contains an undeclared Bilibili identity", "SOURCE_SCOPE_VIOLATION")
            if row.get("kind") == "video_part":
                parent = items.get(row.get("parent_id"), {})
                require(parent.get("kind") == "video" and parent.get("identifiers", {}).get("bilibili_bvid") == row["identifiers"].get("bilibili_bvid"),
                        "Part and parent video identities disagree", "IDENTITY_AMBIGUOUS", 3)
            old_relations = {canonical_json(r) for r in old.get("relations", [])}
            affected.update(r["target_item_id"] for r in row.get("relations", [])
                            if canonical_json(r) not in old_relations)
        covered = set().union(*(bound[ref] for ref in op["source_refs"]))
        require(affected <= covered and all(bound[ref] & affected for ref in op["source_refs"]),
                "Source references do not cover the operation's actual items", "SOURCE_SCOPE_VIOLATION")
        if entity == "documents":
            own_items = set(input_ids(row, "item"))
            for aid in input_ids(row, "audio"):
                require(own_items <= set(input_ids(assets.get(aid, {}), "item")), "Audio input belongs to another item", "SOURCE_SCOPE_VIOLATION")
            for tid in input_ids(row, "transcript"):
                require(set(input_ids(documents.get(tid, {}), "item")) == own_items,
                        "Transcript input belongs to another item", "SOURCE_SCOPE_VIOLATION")


def project(batch, entities):
    index = IdentityIndex(entities)
    outcomes, conflicts = [], []
    for op in batch.manifest["operations"]:
        entity, rid = op["entity"], op["record_id"]
        old = entities[entity].get(rid)
        result = {"entity": entity, "record_id": rid, "op": op["op"], "before_sha256": json_sha256(old) if old is not None else None}
        try:
            new, outcome = merge_record(op, batch.payloads[op["path"]], old, batch.manifest["producer"]["run_id"])
            if outcome != "unchanged":
                index.add(entity, new, existing=old is not None)
            entities[entity][rid] = new
            result.update(outcome=outcome, after_sha256=json_sha256(new))
        except IngestError as error:
            result.update(outcome="conflict", after_sha256=None, code=error.code)
            conflicts.append({"entity": entity, "record_id": rid, **error.as_dict()})
        outcomes.append(result)
    return outcomes, conflicts
