"""Bronze preservation, editable Silver and declarative Gold projections."""
from __future__ import annotations

import shutil
import os
from pathlib import Path

from .bundle import (copy_bundle, create, digest, encode, read_json, read_rows, safe_file,
                     seal, verify, write_json, write_rows)

DELIVERY = "asr-delivery/v1"
SILVER = "weimingzi-silver/v1"
GOLD = "weimingzi-gold/v1"


def _core(row):
    if not isinstance(row, dict):
        raise ValueError("records must be objects")
    for key in ("record_id", "text"):
        if not isinstance(row.get(key), str) or not row[key].strip():
            raise ValueError("nonempty " + key + " required")
    source = row.get("source")
    if not isinstance(source, dict) or any(not isinstance(source.get(k), str) or not source[k].strip()
                                         for k in ("platform", "source_id", "group_id")):
        raise ValueError("stable source identity required")
    encode(row)


def _unique(rows):
    if not rows:
        raise ValueError("empty corpus")
    seen = set()
    for row in rows:
        _core(row)
        if row["record_id"] in seen:
            raise ValueError("duplicate record_id")
        seen.add(row["record_id"])


def _delivery(rows):
    _unique(rows)
    for row in rows:
        quality = row.get("quality", {})
        if (not isinstance(quality, dict) or quality.get("status") != "passed"
                or quality.get("gate") != "production-minimum/v1"
                or not isinstance(row.get("provenance"), dict) or not row["provenance"]
                or not isinstance(row.get("kind"), str) or not row["kind"].strip()):
            raise ValueError("missing producer quality contract")
        if "_lineage" in row:
            raise ValueError("_lineage is reserved for corpus custody")
        timeline = row.get("segments")
        if timeline is not None:
            if not isinstance(timeline, list) or not timeline:
                raise ValueError("invalid delivery timeline")
            previous = -1
            for segment in timeline:
                if (not isinstance(segment, dict) or type(segment.get("start_ms")) is not int
                        or type(segment.get("end_ms")) is not int or segment["start_ms"] < 0
                        or segment["start_ms"] < previous or segment["end_ms"] <= segment["start_ms"]):
                    raise ValueError("invalid delivery timeline; evidence must not be sorted or clamped")
                previous = segment["start_ms"]


def checked_rows(directory, format=None):
    directory = Path(directory)
    manifest = verify(directory, format)
    if manifest.get("records_file") != "records.jsonl":
        raise ValueError("unsupported records file")
    rows = read_rows(directory / "records.jsonl")
    if type(manifest.get("record_count")) is not int or manifest["record_count"] != len(rows):
        raise ValueError("record count mismatch")
    return manifest, rows


def ingest(delivery, output):
    delivery, output = Path(delivery).absolute(), Path(output).absolute()
    if output.is_relative_to(delivery) or delivery.is_relative_to(output):
        raise ValueError("source and destination must be separate")
    manifest, rows = checked_rows(delivery, DELIVERY)
    _delivery(rows)
    for row in rows:
        row["_lineage"] = {"origin_bundle_id": manifest["bundle_id"], "origin_record_sha256": digest(row),
                           "origin_record_id": row["record_id"], "producer_receipt_applies": True}
    with create(output) as stage:
        name = "bronze/" + manifest["bundle_id"]
        copy_bundle(delivery, stage / name)
        write_rows(stage, "records.jsonl", rows)
        result = seal(stage, SILVER, records_file="records.jsonl", record_count=len(rows),
                      origins=[{"bundle_id": manifest["bundle_id"], "directory": name}])
    return result


def checkout(snapshot, output):
    snapshot, output = Path(snapshot).absolute(), Path(output).absolute()
    manifest, rows = checked_rows(snapshot, SILVER)
    _unique(rows)
    if output.is_relative_to(snapshot) or snapshot.is_relative_to(output):
        raise ValueError("checkout and snapshot must be separate")
    with create(output, checked=False) as stage:
        copy_bundle(snapshot, stage / ".base")
        # Copies, never hardlinks: editing cannot mutate an upstream receipt.
        shutil.copyfile(snapshot / "records.jsonl", stage / "records.jsonl")
        if (snapshot / "assets").exists():
            _copy_assets(snapshot / "assets", stage / "assets")
        else:
            for origin in manifest["origins"]:
                directory = safe_file(snapshot, origin["directory"])
                original = verify(directory)
                for entry in original["files"]:
                    name = entry["path"]
                    if name.startswith("attachments/") or name.endswith(("/ai-draft.md", "/review.md")):
                        _copy_asset(safe_file(directory, name), stage / "assets", origin["bundle_id"] + "/" + name)
        write_json(stage, "checkout.json", {"format": "weimingzi-checkout/v1", "base_bundle_id": manifest["bundle_id"]})
    return {"working_directory": str(output), "base_bundle_id": manifest["bundle_id"]}


def _copy_asset(source, destination, name):
    if Path(source).is_symlink() or not Path(source).is_file():
        raise ValueError("editable assets must be regular files")
    target = safe_file(destination, name)
    target.parent.mkdir(parents=True, exist_ok=True)
    with Path(source).open("rb") as reader, target.open("xb") as writer:
        shutil.copyfileobj(reader, writer, length=1024 * 1024)
        writer.flush()
        os.fsync(writer.fileno())


def _copy_assets(source, destination):
    if Path(source).is_symlink():
        raise ValueError("editable assets must not use symbolic links")
    for path in sorted(Path(source).rglob("*")):
        if path.is_symlink():
            raise ValueError("editable assets must not use symbolic links")
        if path.is_file():
            _copy_asset(path, destination, path.relative_to(source).as_posix())


def import_local(records, output):
    """Import user content without claiming it passed an ASR producer gate."""
    records, output = Path(records).absolute(), Path(output).absolute()
    if records.is_relative_to(output):
        raise ValueError("destination contains the source")
    raw = records.read_bytes()
    rows = read_rows(records)
    if records.read_bytes() != raw:
        raise ValueError("source changed during import")
    _unique(rows)
    if any("_lineage" in row for row in rows):
        raise ValueError("_lineage is reserved for corpus custody")
    with create(output) as stage:
        origin = stage / "bronze/local"
        origin.mkdir(parents=True)
        from .bundle import write_bytes
        write_bytes(origin, "records.jsonl", raw)
        receipt = seal(origin, "weimingzi-local-source/v1", records_file="records.jsonl",
                       record_count=len(rows), quality_claim="none")
        for row in rows:
            original_hash = digest(row)
            row["_lineage"] = {"origin_bundle_id": receipt["bundle_id"], "origin_record_sha256": original_hash,
                              "origin_record_id": row["record_id"], "producer_receipt_applies": False}
            row["quality"] = {"status": "downstream-imported", "producer_receipt_applies": False,
                              "supplied_quality": row.get("quality")}
        write_rows(stage, "records.jsonl", rows)
        result = seal(stage, SILVER, records_file="records.jsonl", record_count=len(rows),
                      origins=[{"bundle_id": receipt["bundle_id"], "directory": "bronze/local"}])
    return result


def merge(snapshots, output):
    """Combine frozen sources; differing versions of the same record fail closed."""
    output = Path(output).absolute()
    rows, origins, parents, assets = {}, {}, [], {}
    for source in snapshots:
        source = Path(source).absolute()
        if output.is_relative_to(source) or source.is_relative_to(output):
            raise ValueError("merge source and destination must be separate")
        manifest, items = checked_rows(source, SILVER)
        _unique(items)
        parents.append(manifest["bundle_id"])
        if (source / "assets").exists():
            assets[manifest["bundle_id"]] = source / "assets"
        for item in items:
            key = item["record_id"]
            if key in rows and digest(rows[key]) != digest(item):
                raise ValueError("conflicting record versions; select the intended snapshot explicitly: " + key)
            rows[key] = item
        for origin in manifest["origins"]:
            path = safe_file(source, origin["directory"])
            if verify(path)["bundle_id"] != origin["bundle_id"]:
                raise ValueError("origin identity mismatch")
            origins[origin["bundle_id"]] = path
    _unique(list(rows.values()))
    with create(output) as stage:
        for identity, path in sorted(origins.items()):
            copy_bundle(path, stage / "bronze" / identity)
        for identity, path in sorted(assets.items()):
            _copy_assets(path, stage / "assets" / identity)
        write_rows(stage, "records.jsonl", [rows[k] for k in sorted(rows)])
        result = seal(stage, SILVER, records_file="records.jsonl", record_count=len(rows),
                      origins=[{"bundle_id": k, "directory": "bronze/" + k} for k in sorted(origins)],
                      parent_bundle_ids=parents, assets_quality_claim="none")
    return result


def freeze(working, output):
    working, output = Path(working).absolute(), Path(output).absolute()
    if output.is_relative_to(working) or working.is_relative_to(output):
        raise ValueError("working directory and frozen output must be separate")
    control = read_json(working / "checkout.json")
    manifest, base = checked_rows(working / ".base", SILVER)
    if control != {"format": "weimingzi-checkout/v1", "base_bundle_id": manifest["bundle_id"]}:
        raise ValueError("checkout base identity mismatch")
    rows = read_rows(working / "records.jsonl")
    _unique(rows)
    old = {row["record_id"]: row for row in base}
    for row in rows:
        original = old.get(row["record_id"])
        if original is None:
            raise ValueError("new source records must enter through a delivery, not inherit an unrelated receipt")
        before = {k: v for k, v in original.items() if k != "_lineage"}
        after = {k: v for k, v in row.items() if k != "_lineage"}
        changed = digest(before) != digest(after)
        row["_lineage"] = {**original["_lineage"], "parent_bundle_id": manifest["bundle_id"],
                           "parent_record_sha256": digest(original),
                           "producer_receipt_applies": not changed and original["_lineage"]["producer_receipt_applies"]}
        if not row["_lineage"]["producer_receipt_applies"]:
            row["quality"] = {"status": "downstream-edited", "producer_receipt_applies": False,
                              "upstream": original.get("quality")}
    with create(output) as stage:
        for origin in manifest["origins"]:
            copy_bundle(safe_file(working / ".base", origin["directory"]), safe_file(stage, origin["directory"]))
        if (working / "assets").exists():
            _copy_assets(working / "assets", stage / "assets")
        write_rows(stage, "records.jsonl", rows)
        result = seal(stage, SILVER, records_file="records.jsonl", record_count=len(rows),
                      origins=manifest["origins"], parent_bundle_id=manifest["bundle_id"],
                      assets_quality_claim="none")
    return result


def _lookup(row, path):
    if not isinstance(path, str) or not path:
        raise ValueError("field paths must be nonempty dot-separated strings")
    value = row
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            raise ValueError("missing field: " + path)
        value = value[part]
    return value


def validate_profile(profile):
    if not isinstance(profile, dict) or set(profile) - {"format", "name", "fields", "required", "filter", "defaults", "purpose"}:
        raise ValueError("unsupported projection profile fields")
    if profile.get("format") != "weimingzi-projection/v1" or not isinstance(profile.get("name"), str):
        raise ValueError("invalid projection profile")
    fields = profile.get("fields")
    if not isinstance(fields, dict) or not fields or any(not isinstance(k, str) or not k for k in fields):
        raise ValueError("projection fields must be a nonempty mapping")
    for path in fields.values():
        if not isinstance(path, str) or not path:
            raise ValueError("field paths must be strings")
    required = profile.get("required", {})
    defaults = profile.get("defaults", {})
    filters = profile.get("filter", {})
    if (not isinstance(required, dict) or set(required) - set(fields)
            or any(v not in {"string", "number", "boolean", "object", "array"} for v in required.values())
            or not isinstance(defaults, dict) or set(defaults) - set(fields)
            or not isinstance(filters, dict) or any(not isinstance(v, list) or not v for v in filters.values())):
        raise ValueError("invalid projection contract")
    encode(profile)


def _types(row, required):
    types = {"string": str, "number": (int, float), "boolean": bool, "object": dict, "array": list}
    for key, name in required.items():
        value = row.get(key)
        if (not isinstance(value, types[name]) or (name == "number" and type(value) is bool)
                or (name == "string" and not value.strip())):
            raise ValueError("projection contract requires " + key + " as nonempty " + name)


def project(snapshot, profile, output):
    snapshot, output = Path(snapshot).absolute(), Path(output).absolute()
    if output.is_relative_to(snapshot) or snapshot.is_relative_to(output):
        raise ValueError("projection must not contain or modify its source snapshot")
    validate_profile(profile)
    manifest, rows = checked_rows(snapshot, SILVER)
    _unique(rows)
    projected, lineage = [], []
    for row in rows:
        if any(_lookup(row, key) not in allowed for key, allowed in profile.get("filter", {}).items()):
            continue
        item = {}
        for name, path in profile["fields"].items():
            try:
                item[name] = _lookup(row, path)
            except ValueError:
                if name not in profile.get("defaults", {}):
                    raise
                item[name] = profile["defaults"][name]
        _types(item, profile.get("required", {}))
        projected.append(item)
        lineage.append({"row": len(projected), "output_sha256": digest(item), "record_id": row["record_id"],
                        "source": row["source"], "source_record_sha256": digest(row),
                        "custody": row["_lineage"], "source_quality": row.get("quality"),
                        "silver_bundle_id": manifest["bundle_id"]})
    if not projected:
        raise ValueError("projection selected no records")
    with create(output) as stage:
        write_rows(stage, "records.jsonl", projected)
        write_rows(stage, "lineage.jsonl", lineage)
        write_json(stage, "profile.json", profile)
        result = seal(stage, GOLD, records_file="records.jsonl", record_count=len(projected),
                      lineage_file="lineage.jsonl", profile_file="profile.json",
                      source_bundle_id=manifest["bundle_id"], profile_sha256=digest(profile),
                      purpose=profile.get("purpose", "unspecified"))
    return result
