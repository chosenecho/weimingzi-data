"""Strict, bounded reader for the single current native batch protocol."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from ..records import ENTITIES, canonical_json, json_sha256
from .errors import IngestError, require
from .policy import POLICY, SCOPE, TARGET

SHA = r"[0-9a-f]{64}"
COMMIT = r"(?:[0-9a-f]{40}|[0-9a-f]{64})"
RECORD = r"[a-z]-[0-9a-f]{24,64}"
SAFE = r"[A-Za-z0-9][A-Za-z0-9._:-]*"
NAMESPACES = ("bilibili_bvid", "bilibili_dynamic", "bilibili_cvid", "bilibili_opus")


def matches(value, pattern, maximum=256):
    return (
        isinstance(value, str)
        and len(value) <= maximum
        and re.fullmatch(pattern, value) is not None
    )


def shape(value, required, optional=()):
    require(isinstance(value, dict), "Expected an object")
    require(
        set(required) <= value.keys() and value.keys() <= set(required) | set(optional),
        "Missing or unexpected object fields",
    )


def array(value, minimum=0, maximum=2000, unique=False):
    require(
        isinstance(value, list) and minimum <= len(value) <= maximum,
        "Invalid array length",
    )
    if unique:
        keys = [canonical_json(v) for v in value]
        require(len(set(keys)) == len(keys), "Duplicate array entries")


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def timestamp(value):
    require(
        isinstance(value, str)
        and len(value) <= 64
        and matches(
            value,
            r"\d{4}-\d\d-\d\d[Tt]\d\d:\d\d:\d\d(?:\.\d+)?(?:[Zz]|[+-]\d\d:\d\d)",
            64,
        ),
        "Invalid RFC3339 timestamp",
    )
    try:
        parsed = datetime.fromisoformat(value.upper().replace("Z", "+00:00"))
        require(parsed.utcoffset() is not None, "Timestamp needs a timezone")
    except ValueError as error:
        raise IngestError(
            "PACKAGE_INTEGRITY_FAILED", "Invalid RFC3339 timestamp"
        ) from error


def strict_json(raw):
    def pairs(entries):
        result = {}
        for key, value in entries:
            require(key not in result, "Duplicate JSON object key")
            result[key] = value
        return result

    def constant(_):
        raise IngestError("PACKAGE_INTEGRITY_FAILED", "Non-finite JSON number")

    def real(value):
        result = float(value)
        require(math.isfinite(result), "Non-finite JSON number")
        return result

    try:
        value = json.loads(
            raw.decode("utf-8-sig"),
            object_pairs_hook=pairs,
            parse_constant=constant,
            parse_float=real,
        )
        canonical_json(value).encode("utf-8")  # Also reject lone surrogate code points.
        return value
    except (ValueError, UnicodeError, RecursionError) as error:
        if isinstance(error, IngestError):
            raise
        raise IngestError(
            "PACKAGE_INTEGRITY_FAILED", "Invalid strict UTF-8 JSON"
        ) from error


def regular(path, *, reject_links=False):
    info = path.lstat()
    require(
        not path.is_symlink() and not (getattr(info, "st_file_attributes", 0) & 0x400),
        "Symlinks and reparse points are forbidden",
    )
    require(stat.S_ISREG(info.st_mode), "Expected a regular file")
    if reject_links:
        require(info.st_nlink == 1, "Hard-linked package files are forbidden")
    return info


def read_bounded(path, maximum, *, reject_links=False):
    info = regular(path, reject_links=reject_links)
    require(info.st_size <= maximum, "File exceeds byte budget")
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    require(
        len(raw) == info.st_size and len(raw) <= maximum,
        "File changed or exceeds byte budget",
    )
    return raw


def inventory(root, max_entries=None):
    """Walk without following links; reject directory junctions as well on Windows."""
    require(root.is_dir() and not root.is_symlink(), "Missing or linked directory")
    require(
        not (getattr(root.lstat(), "st_file_attributes", 0) & 0x400),
        "Directory reparse point is forbidden",
    )
    found = {}
    folded = set()
    for folder, dirs, files in os.walk(root, followlinks=False):
        for name in [*dirs, *files]:
            path = Path(folder) / name
            info = path.lstat()
            require(
                not path.is_symlink()
                and not (getattr(info, "st_file_attributes", 0) & 0x400),
                "Symlinks and reparse points are forbidden",
            )
            rel = path.relative_to(root).as_posix()
            require(rel.casefold() not in folded, "Case-colliding paths")
            folded.add(rel.casefold())
            require(
                max_entries is None or len(folded) <= max_entries,
                "Directory exceeds entry budget",
            )
            if name in files:
                require(stat.S_ISREG(info.st_mode), "Expected a regular file")
                found[rel] = path
    return found


def reject_linked_ancestors(path):
    for part in (path, *path.parents):
        if part.exists():
            info = part.lstat()
            require(
                not part.is_symlink()
                and not (getattr(info, "st_file_attributes", 0) & 0x400),
                "Symlinked package path is forbidden",
            )


def bili_url(value):
    require(
        isinstance(value, str)
        and len(value) <= 2048
        and not any(ord(c) <= 32 for c in value)
        and "\\" not in value,
        "Invalid source URL",
        "SOURCE_SCOPE_VIOLATION",
    )
    try:
        u = urlsplit(value)
        okay = (
            u.scheme == "https"
            and u.hostname
            in {"www.bilibili.com", "bilibili.com", "t.bilibili.com", "m.bilibili.com"}
            and not u.username
            and not u.password
            and u.port in (None, 443)
            and not u.fragment
        )
    except ValueError:
        okay = False
    require(
        okay, "URL must use an allowed Bilibili HTTPS host", "SOURCE_SCOPE_VIOLATION"
    )
    query = parse_qs(u.query, keep_blank_values=True)
    require(
        set(query) <= {"p"}
        and all(len(v) == 1 and matches(v[0], r"[0-9]+") for v in query.values()),
        "Source URL contains unsupported parameters",
        "SOURCE_SCOPE_VIOLATION",
    )
    return u


def validate_source(source):
    shape(
        source,
        (
            "source_id",
            "namespace",
            "external_id",
            "publisher_uid",
            "url",
            "observed_at",
            "relation",
            "referenced_by",
        ),
        ("cid", "part_number"),
    )
    require(matches(source["source_id"], SAFE, 160), "Invalid source ID")
    require(source["namespace"] in NAMESPACES, "Invalid source namespace")
    ext = source["external_id"]
    pattern = (
        r"BV[0-9A-Za-z]{10}"
        if source["namespace"] == "bilibili_bvid"
        else r"[0-9]{1,32}"
    )
    require(matches(ext, pattern, 128), "Invalid external identity")
    uid = source["publisher_uid"]
    require(uid is None or matches(uid, r"[0-9]{1,32}"), "Invalid publisher UID")
    timestamp(source["observed_at"])
    array(source["referenced_by"], unique=True)
    require(
        all(matches(v, SAFE, 160) for v in source["referenced_by"]),
        "Invalid referring source",
    )
    if source["relation"] == "target_publication":
        require(
            uid == SCOPE["target_uid"] and not source["referenced_by"],
            "Incorrect target publication owner",
            "SOURCE_SCOPE_VIOLATION",
        )
    else:
        require(
            source["relation"] == "referenced_content" and source["referenced_by"],
            "Referenced content needs a referring publication",
            "SOURCE_SCOPE_VIOLATION",
        )
    if "cid" in source or "part_number" in source:
        require(source["namespace"] == "bilibili_bvid", "CID/part are video identities")
    if "cid" in source:
        require(matches(source["cid"], r"[0-9]{1,32}"), "Invalid CID")
    if "part_number" in source:
        require(integer(source["part_number"], 1), "Invalid part number")
        require("cid" in source, "A part source must identify its CID")
    u = bili_url(source["url"])
    paths = {
        "bilibili_bvid": f"/video/{ext}",
        "bilibili_cvid": f"/read/cv{ext}",
        "bilibili_dynamic": f"/{ext}"
        if u.hostname == "t.bilibili.com"
        else f"/opus/{ext}",
        "bilibili_opus": f"/opus/{ext}",
    }
    require(
        u.path.rstrip("/") == paths[source["namespace"]],
        "Source URL and identity disagree",
        "SOURCE_SCOPE_VIOLATION",
    )
    if "part_number" in source and u.query:
        require(
            parse_qs(u.query).get("p") == [str(source["part_number"])],
            "URL part disagrees with source",
        )


def validate_media(asset):
    shape(
        asset,
        (
            "asset_version",
            "kind",
            "sha256",
            "size_bytes",
            "mime_type",
            "locator",
            "verification",
        ),
    )
    require(
        type(asset["asset_version"]) is int
        and asset["asset_version"] == 2
        and asset["kind"] in ("video", "image"),
        "Unsupported media observation",
        "MEDIA_UNVERIFIED",
    )
    require(
        matches(asset["sha256"], SHA) and integer(asset["size_bytes"], 1),
        "Invalid media digest/size",
        "MEDIA_UNVERIFIED",
    )
    require(
        matches(asset["mime_type"], asset["kind"] + r"/[a-zA-Z0-9.+-]+", 128),
        "Media kind/MIME disagree",
        "MEDIA_UNVERIFIED",
    )
    loc = asset["locator"]
    shape(loc, ("storage", "bucket_alias", "object_key", "version_id", "access"))
    require(
        loc["storage"] == "oss"
        and loc["bucket_alias"] in POLICY["allowed_media_bucket_aliases"]
        and loc["access"] in ("authenticated", "public"),
        "Untrusted media locator",
        "MEDIA_UNVERIFIED",
    )
    require(
        matches(
            loc["object_key"],
            r"media/sha256/" + asset["sha256"] + r"(?:\.[a-z0-9]{1,12})?",
            200,
        ),
        "Media object key must contain its digest",
        "MEDIA_UNVERIFIED",
    )
    require(
        loc["version_id"] is None
        or (
            isinstance(loc["version_id"], str)
            and 1 <= len(loc["version_id"]) <= 256
            and not any(ord(c) < 32 for c in loc["version_id"])
        ),
        "Invalid object version",
    )
    proof = asset["verification"]
    shape(proof, ("mode", "verified_at", "producer_run_id"))
    require(
        proof["mode"] == "readback_sha256"
        and matches(proof["producer_run_id"], SAFE, 128),
        "Missing readback provenance",
        "MEDIA_UNVERIFIED",
    )
    timestamp(proof["verified_at"])


def validate_payload(entity, payload, record_id):
    """Check the native envelope here; the whole candidate graph validates later."""
    require(
        isinstance(payload, dict)
        and payload.get("id") == record_id
        and isinstance(payload.get("kind"), str)
        and not {"schema_version", "_legacy", "table"} & payload.keys(),
        "Payload must be a native entity record matching the operation ID",
    )
    metadata = payload.get("metadata", {})
    require(isinstance(metadata, dict), "Metadata must be an object")
    for key, observations in metadata.items():
        require(isinstance(key, str), "Invalid metadata key")
        if key == "media_assets":
            array(observations, maximum=100000)
            require(entity == "items", "Media observations belong to items")
            for asset in observations:
                validate_media(asset)
    if entity == "items":
        require(isinstance(payload.get("identifiers"), dict), "Item needs identifiers")
        for namespace, values in payload["identifiers"].items():
            if namespace in NAMESPACES or namespace == "bilibili_part":
                array(values, 1, unique=True)
                require(all(isinstance(v, str) and v for v in values), "Invalid external identities")
        for url in payload.get("urls", []):
            bili_url(url)


@dataclass
class Batch:
    manifest: dict
    manifest_sha256: str
    payloads: dict

    def summary(self):
        return {
            "status": "verified",
            "batch_id": self.manifest["batch_id"],
            "manifest_sha256": self.manifest_sha256,
            "operations": len(self.manifest["operations"]),
            "files": len(self.payloads),
        }


def verify_batch(directory: Path) -> Batch:
    directory = Path(directory).absolute()
    reject_linked_ancestors(directory)
    directory = directory.resolve(strict=True)
    limits = POLICY["limits"]
    paths = inventory(directory, max_entries=POLICY["limits"]["files"] + 100)
    require("manifest.json" in paths, "Missing manifest.json")
    raw = read_bounded(
        paths["manifest.json"], limits["manifest_bytes"], reject_links=True
    )
    m = strict_json(raw)
    shape(
        m,
        (
            "contract_version",
            "kind",
            "record_schema_version",
            "batch_id",
            "target",
            "producer",
            "source_scope",
            "base_commit",
            "created_at",
            "requires_batches",
            "sources",
            "files",
            "operations",
        ),
    )
    require(
        type(m["contract_version"]) is int
        and m["contract_version"] == 2
        and type(m["record_schema_version"]) is int
        and m["record_schema_version"] == 3
        and m["kind"] == "weimingzi_native_increment",
        "Unsupported ingest contract",
        "UNSUPPORTED_CONTRACT",
    )
    require(
        m["target"] == TARGET and m["source_scope"] == SCOPE,
        "Incorrect repository or scope",
        "SOURCE_SCOPE_VIOLATION",
    )
    require(
        matches(m["batch_id"], SHA) and matches(m["base_commit"], COMMIT),
        "Invalid batch/commit identity",
    )
    timestamp(m["created_at"])
    producer = m["producer"]
    shape(producer, ("name", "code_revision", "run_id"))
    require(
        producer["name"] in POLICY["allowed_producers"]
        and matches(producer["code_revision"], COMMIT)
        and matches(producer["run_id"], SAFE, 128),
        "Untrusted producer",
    )
    array(m["requires_batches"], unique=True)
    require(
        all(matches(v, SHA) and v != m["batch_id"] for v in m["requires_batches"]),
        "Invalid batch dependency",
    )
    require(
        json_sha256({k: v for k, v in m.items() if k != "batch_id"}) == m["batch_id"],
        "Batch ID digest mismatch",
    )
    array(m["sources"], 1)
    sources = {}
    identities = set()
    for source in m["sources"]:
        validate_source(source)
        key = (source["namespace"], source["external_id"], source.get("part_number"))
        require(
            source["source_id"] not in sources and key not in identities,
            "Duplicate source identity",
        )
        sources[source["source_id"]] = source
        identities.add(key)
    # Every reference edge must exist and be acyclic; a branch cannot hide a cycle.
    done = set()
    for source_id in sources:
        stack = [(source_id, False)]
        active = set()
        while stack:
            current, leaving = stack.pop()
            require(
                current in sources,
                "Unknown referenced source",
                "SOURCE_SCOPE_VIOLATION",
            )
            if leaving:
                active.remove(current)
                done.add(current)
                continue
            if current in done:
                continue
            require(
                current not in active,
                "Cyclic source references",
                "SOURCE_SCOPE_VIOLATION",
            )
            active.add(current)
            stack.append((current, True))
            stack.extend((ref, False) for ref in sources[current]["referenced_by"])
        reachable, pending = set(), [source_id]
        while pending:
            current = pending.pop()
            if current in reachable:
                continue
            reachable.add(current)
            pending.extend(sources[current]["referenced_by"])
        if sources[source_id]["relation"] == "referenced_content":
            require(
                any(
                    sources[target]["relation"] == "target_publication"
                    for target in reachable
                ),
                "Referenced content is not connected to a target publication",
                "SOURCE_SCOPE_VIOLATION",
            )
    array(m["files"], 1, limits["files"])
    array(m["operations"], 1, limits["operations"])
    files, payloads, total = {}, {}, 0
    for entry in m["files"]:
        shape(entry, ("path", "sha256", "size_bytes"))
        p = entry["path"]
        require(
            matches(
                p,
                r"records/(?:"
                + "|".join(ENTITIES)
                + r")/"
                + RECORD
                + r"\.json",
                200,
            ),
            "Invalid payload path",
        )
        require(
            p not in files
            and matches(entry["sha256"], SHA)
            and integer(entry["size_bytes"], 1),
            "Duplicate file or invalid file integrity fields",
        )
        require(
            p in paths and entry["size_bytes"] <= limits["payload_file_bytes"],
            "Missing or oversized payload",
        )
        total += entry["size_bytes"]
        require(
            total <= limits["payload_total_bytes"], "Batch exceeds total byte budget"
        )
        content = read_bounded(
            paths[p], limits["payload_file_bytes"], reject_links=True
        )
        require(
            len(content) == entry["size_bytes"]
            and hashlib.sha256(content).hexdigest() == entry["sha256"],
            "Payload byte integrity mismatch",
        )
        files[p] = entry
        payloads[p] = strict_json(content)
    require(set(paths) == {"manifest.json", *files}, "Unlisted package files")
    used, keys = set(), set()
    for op in m["operations"]:
        shape(op, ("op", "entity", "record_id", "path", "payload_sha256",
                   "expected_record_sha256", "source_refs"))
        entity, rid, kind, p = op["entity"], op["record_id"], op["op"], op["path"]
        require(isinstance(entity, str) and entity in ENTITIES
                and matches(rid, RECORD) and kind in ("insert", "replace"),
                "Invalid native operation")
        require(p == f"records/{entity}/{rid}.json" and p in payloads
                and p not in used and (entity, rid) not in keys,
                "Operation/file mapping is not one-to-one")
        used.add(p)
        keys.add((entity, rid))
        require(matches(op["payload_sha256"], SHA)
                and op["payload_sha256"] == json_sha256(payloads[p]),
                "Canonical payload digest mismatch")
        require(op["expected_record_sha256"] is None if kind == "insert"
                else matches(op["expected_record_sha256"], SHA),
                "Invalid record precondition")
        array(op["source_refs"], 1, unique=True)
        require(all(isinstance(ref, str) and ref in sources for ref in op["source_refs"]),
                "Unknown operation source", "SOURCE_SCOPE_VIOLATION")
        validate_payload(entity, payloads[p], rid)
    require(used == set(files), "Unused manifest files")
    return Batch(m, hashlib.sha256(raw).hexdigest(), payloads)
