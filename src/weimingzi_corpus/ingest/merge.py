"""Append-only operation semantics, external identity and source binding."""

from __future__ import annotations

import copy

from ..records import canonical_json, json_sha256
from .errors import IngestError, require
from .manifest import NAMESPACES, integer


def union(old, new):
    result = copy.deepcopy(old)
    seen = {canonical_json(v) for v in old}
    for value in new:
        key = canonical_json(value)
        if key not in seen:
            seen.add(key)
            result.append(copy.deepcopy(value))
    return result


def merge_record(op, payload, old):
    kind = op["op"]
    if kind == "insert":
        if old is None:
            return copy.deepcopy(payload), "inserted"
        require(
            canonical_json(old) == canonical_json(payload),
            "Existing ID has different content",
            "RECORD_CONFLICT",
            3,
        )
        return old, "unchanged"
    require(
        old is not None, "Operation refers to a missing record", "RECORD_CONFLICT", 3
    )
    new = copy.deepcopy(old)
    if kind == "enrich":
        for field, value in payload.items():
            if field == "metadata":
                for key, observations in value.items():
                    previous = new.setdefault("metadata", {}).get(key, [])
                    require(
                        isinstance(previous, list),
                        "Existing metadata is not an observation array",
                        "RECORD_CONFLICT",
                        3,
                    )
                    new["metadata"][key] = union(previous, observations)
            else:
                require(
                    isinstance(new.get(field, []), list),
                    "Existing field is not an array",
                    "RECORD_CONFLICT",
                    3,
                )
                new[field] = union(new.get(field, []), value)
        outcome = "enriched"
    else:
        allowed = {"availability", "local_path", "downloads", "unavailable_reason"}
        require(
            {k: v for k, v in old.items() if k not in allowed}
            == {k: v for k, v in payload.items() if k not in allowed},
            "Distribution attachment changes immutable audio fields",
            "RECORD_CONFLICT",
            3,
        )
        require(
            payload.get("availability") == "available"
            and payload.get("downloads")
            and isinstance(payload.get("local_path"), str)
            and integer(payload.get("size_bytes"), 1),
            "Incomplete audio distribution",
            "MEDIA_UNVERIFIED",
        )
        require(
            "unavailable_reason" not in payload,
            "Available audio must remove unavailable reason",
        )
        if old.get("availability") == "available":
            require(
                payload["local_path"] == old["local_path"],
                "Cannot change an existing restore path",
                "RECORD_CONFLICT",
                3,
            )
            # A replay may predate newer mirrors; the union preserves every old locator.
            new["downloads"] = union(old["downloads"], payload["downloads"])
        else:
            require(
                old.get("availability") == "unavailable", "Unknown audio availability"
            )
            new.update(
                {k: copy.deepcopy(v) for k, v in payload.items() if k in allowed}
            )
            new.pop("unavailable_reason", None)
        outcome = "distribution_attached"
    if canonical_json(old) == canonical_json(new):
        return (
            old,
            "unchanged",
        )  # Postcondition precedes CAS, including stale duplicate deliveries.
    require(
        json_sha256(old) == op["expected_record_sha256"],
        "Record precondition is stale",
        "PRECONDITION_FAILED",
        4,
    )
    return new, outcome


def identity_keys(table, row):
    if table == "items":
        kind = row.get("kind")
        for namespace, values in row.get("identifiers", {}).items():
            if kind == "video_part" and namespace != "bilibili_part":
                continue  # Every part legitimately carries its parent's BV.
            for value in values:
                yield ("external", kind, namespace, canonical_json(value))
        if kind == "video_part":
            yield ("parent_part", row.get("parent_id"), row.get("part_number"))
            for cid in row.get("metadata", {}).get("cid", []):
                yield ("cid", str(cid))
    elif table == "audio":
        yield ("audio_sha256", row.get("sha256"))
    elif table == "transcripts":
        yield ("transcript_sha256", row.get("content_sha256"))
    elif table == "edited_transcripts" and not row.get("derived_from_id"):
        for revision in row.get("metadata", {}).get("upstream_revision_id", []):
            yield ("ai_revision", row.get("item_id"), canonical_json(revision))


class IdentityIndex:
    def __init__(self, tables):
        self.keys = {}
        self.ids = {}
        for table, rows in tables.items():
            for rid, row in rows.items():
                require(
                    rid not in self.ids,
                    "Baseline record ID occurs in multiple tables",
                    "IDENTITY_AMBIGUOUS",
                    3,
                )
                self.ids[rid] = table
                for key in identity_keys(table, row):
                    self.keys.setdefault(key, set()).add(rid)

    def add(self, table, row, existing=False):
        rid = row["id"]
        require(
            rid not in self.ids or (existing and self.ids[rid] == table),
            "Record ID already belongs to another table",
            "IDENTITY_AMBIGUOUS",
            3,
        )
        for key in identity_keys(table, row):
            require(
                not self.keys.get(key, set()) - {rid},
                "External/content identity already has a different record ID",
                "IDENTITY_AMBIGUOUS",
                3,
            )
        self.ids[rid] = table
        for key in identity_keys(table, row):
            self.keys.setdefault(key, set()).add(rid)


def item_matches(item, source):
    identifiers = item.get("identifiers", {})
    namespace = source["namespace"]
    aliases = (namespace,)
    if namespace in ("bilibili_dynamic", "bilibili_opus"):
        aliases = ("bilibili_dynamic", "bilibili_opus")
    if not any(source["external_id"] in identifiers.get(ns, []) for ns in aliases):
        return False
    allowed_kinds = {
        "bilibili_bvid": ("video", "video_part"),
        "bilibili_cvid": ("article",),
        "bilibili_dynamic": ("post", "article"),
        "bilibili_opus": ("post", "article"),
    }
    if item.get("kind") not in allowed_kinds[namespace]:
        return False
    if item["kind"] == "video_part":
        require(integer(item.get("part_number"), 1), "Invalid item part number")
        if source.get("part_number") != item.get("part_number"):
            return False
        require(
            "cid" in source, "A part-bound source needs CID", "SOURCE_SCOPE_VIOLATION"
        )
        cids = item.get("metadata", {}).get("cid", [])
        require(
            len(cids) == 1
            and str(cids[0]) == source["cid"]
            and type(cids[0]) in (str, int),
            "BV/part CID changed or is ambiguous",
            "CID_CHANGED",
            3,
        )
        require(
            identifiers.get("bilibili_part")
            == [f"{source['external_id']}:P{item['part_number']}"],
            "Part identity disagrees with BV and part number",
            "IDENTITY_AMBIGUOUS",
            3,
        )
    owners = item.get("metadata", {}).get("uploader_id", [])
    if owners and source["publisher_uid"] is not None:
        require(
            all(
                type(v) in (str, int) and str(v) == source["publisher_uid"]
                for v in owners
            ),
            "Source publisher disagrees with item owner",
            "SOURCE_SCOPE_VIOLATION",
        )
    return True


def validate_scope(batch, tables):
    """Tie source declarations to actual records and actual reference edges."""
    sources = {s["source_id"]: s for s in batch.manifest["sources"]}
    items = tables["items"]
    bound = {
        sid: {rid for rid, item in items.items() if item_matches(item, source)}
        for sid, source in sources.items()
    }
    for sid, source in sources.items():
        require(bound[sid], "Source has no matching item", "SOURCE_SCOPE_VIOLATION")
        for referring in source["referenced_by"]:
            targets = {
                r.get("target_item_id")
                for iid in bound[referring]
                for r in items[iid].get("relations", [])
            }
            targets.update(
                a
                for post in tables["posts"].values()
                if post.get("item_id") in bound[referring]
                for a in post.get("article_item_ids", [])
            )
            require(
                targets & bound[sid],
                "Referenced source lacks a corresponding item relationship",
                "SOURCE_SCOPE_VIOLATION",
            )
    for op in batch.manifest["operations"]:
        row = tables[op["table"]].get(op["record_id"])
        require(
            row is not None,
            "Operation target is absent from candidate",
            "SOURCE_SCOPE_VIOLATION",
        )
        payload = batch.payloads[op["path"]]
        if op["table"] == "items":
            affected = {row["id"]}
            for namespace, values in row.get("identifiers", {}).items():
                if namespace in NAMESPACES:
                    require(
                        all(
                            any(
                                s["external_id"] == value
                                and (
                                    s["namespace"] == namespace
                                    or {s["namespace"], namespace}
                                    <= {"bilibili_dynamic", "bilibili_opus"}
                                )
                                for s in sources.values()
                            )
                            for value in values
                        ),
                        "Item contains an undeclared Bilibili identity",
                        "SOURCE_SCOPE_VIOLATION",
                    )
            if row.get("kind") == "video_part":
                parent = items.get(row.get("parent_id"))
                require(
                    parent is not None
                    and parent.get("kind") == "video"
                    and set(parent.get("identifiers", {}).get("bilibili_bvid", []))
                    == set(row.get("identifiers", {}).get("bilibili_bvid", [])),
                    "Part and parent video identities disagree",
                    "IDENTITY_AMBIGUOUS",
                    3,
                )
            if op["op"] == "enrich":
                affected.update(
                    r["target_item_id"] for r in payload.get("relations", [])
                )
        elif op["table"] == "audio":
            affected = set(payload.get("item_ids", row.get("item_ids", [])))
            require(affected, "Audio needs associated items", "SOURCE_SCOPE_VIOLATION")
        elif op["table"] == "collections":
            affected = {m["item_id"] for m in row.get("members", [])}
            require(affected, "Collection needs members", "SOURCE_SCOPE_VIOLATION")
        else:
            affected = {row.get("item_id")}
            affected.update(payload.get("article_item_ids", []))
        covered = set().union(*(bound[ref] for ref in op["source_refs"]))
        require(
            affected <= covered
            and all(bound[ref] & affected for ref in op["source_refs"]),
            "Operation source references do not cover its actual items",
            "SOURCE_SCOPE_VIOLATION",
        )
        # Transcript/audio links describe the actual input item, not any linked video.
        for aid in row.get("audio_ids", []):
            require(
                row.get("item_id") in tables["audio"].get(aid, {}).get("item_ids", []),
                "Transcript audio belongs to another item",
                "SOURCE_SCOPE_VIOLATION",
            )
        for tid in row.get("transcript_ids", []):
            require(
                tables["transcripts"].get(tid, {}).get("item_id") == row.get("item_id"),
                "AI input transcript belongs to another item",
                "SOURCE_SCOPE_VIOLATION",
            )
        for asset in payload.get("metadata", {}).get("media_assets", []):
            require(
                asset["verification"]["producer_run_id"]
                == batch.manifest["producer"]["run_id"],
                "Media readback belongs to a different producer run",
                "MEDIA_UNVERIFIED",
            )


def project(batch, tables):
    index = IdentityIndex(tables)
    outcomes, conflicts = [], []
    for op in batch.manifest["operations"]:
        table, rid = op["table"], op["record_id"]
        old = tables[table].get(rid)
        result = {
            "table": table,
            "record_id": rid,
            "op": op["op"],
            "before_sha256": json_sha256(old) if old is not None else None,
        }
        try:
            new, outcome = merge_record(op, batch.payloads[op["path"]], old)
            if outcome != "unchanged":
                index.add(table, new, existing=old is not None)
            tables[table][rid] = new
            result.update(outcome=outcome, after_sha256=json_sha256(new))
        except IngestError as error:
            result.update(outcome="conflict", after_sha256=None, code=error.code)
            conflicts.append({"table": table, "record_id": rid, **error.as_dict()})
        outcomes.append(result)
    return outcomes, conflicts
