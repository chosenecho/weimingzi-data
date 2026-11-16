"""Read-only v2 snapshot migration, independent verification and atomic publication.

Roots always contain ``data/``.  Only schema_v3 owns encoding and native writes;
this module owns the transaction and the evidence that permits publication.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import schema_v3

JSONL_TABLES = ("items", "collections", "audio", "confirmations", "attributions")
JSON_TABLES = ("transcripts", "edited_transcripts", "posts", "articles")
TABLES = JSONL_TABLES + JSON_TABLES
ENTITIES = ("items", "documents", "assets", "annotations")
REPORT_NAME = "migration-report.json"
TABLE_ENTITY = {
    "items": "items", "collections": "items", "audio": "assets",
    "confirmations": "annotations", "attributions": "annotations",
    **{table: "documents" for table in JSON_TABLES},
}


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _digest(value) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _reject_constant(value):
    raise ValueError(f"non-finite JSON constant: {value}")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _decode(data: bytes):
    return json.loads(data.decode("utf-8-sig"), object_pairs_hook=_unique_object,
                      parse_constant=_reject_constant)


def _file_entry(path: Path, root: Path) -> dict:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return {"path": path.relative_to(root).as_posix(), "size_bytes": size,
            "sha256": digest.hexdigest()}


def _check_no_links(path: Path) -> Path:
    """Check lexical ancestors before resolve can hide a symlink or junction."""
    absolute = Path(os.path.abspath(path))
    for part in (absolute, *absolute.parents):
        if part.is_symlink() or getattr(part, "is_junction", lambda: False)():
            raise ValueError(f"symlink/junction not allowed: {part}")
    return absolute.resolve()


def _paths(source: Path, output: Path) -> tuple[Path, Path]:
    source, output = _check_no_links(source), _check_no_links(output)
    if source == output or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError("source and output must be independent, non-nested roots")
    if not source.is_dir() or not (source / "data").is_dir():
        raise ValueError("source must be a repository root containing data/")
    return source, output


def _inventory(root: Path) -> list[dict]:
    data = _check_no_links(root / "data")
    files = []
    if not data.is_dir():
        raise ValueError("missing data directory")
    for current, directories, names in os.walk(data, followlinks=False):
        for name in sorted(directories + names):
            candidate = Path(current) / name
            _check_no_links(candidate)
            if candidate.is_file():
                files.append(_file_entry(candidate, root))
            elif not candidate.is_dir():
                raise ValueError(f"not a regular archive file: {candidate}")
    return sorted(files, key=lambda row: row["path"].encode("utf-8"))


def _legacy_layout(source: Path, files: list[dict]) -> None:
    expected = {f"data/{table}.jsonl" for table in JSONL_TABLES}
    actual = {row["path"] for row in files}
    if not expected.issubset(actual):
        raise ValueError(f"missing legacy tables: {sorted(expected - actual)}")
    for table in JSON_TABLES:
        if not (source / "data" / table).is_dir():
            raise ValueError(f"missing legacy table directory: {table}")
    allowed_directories = set(JSON_TABLES)
    for child in (source / "data").iterdir():
        if child.is_dir() and child.name not in allowed_directories:
            raise ValueError(f"unexpected legacy directory: {child.name}")
    for relative in actual - expected:
        parts = Path(relative).parts
        if len(parts) != 3 or parts[1] not in JSON_TABLES or not parts[2].endswith(".json"):
            raise ValueError(f"unexpected legacy file: {relative}")


def _source_rows(source: Path, table: str, files: list[dict]):
    for entry in files:
        relative = entry["path"]
        if table in JSONL_TABLES:
            if relative != f"data/{table}.jsonl":
                continue
        elif not relative.startswith(f"data/{table}/"):
            continue
        path = source / relative
        _check_no_links(path)
        data = path.read_bytes()
        if len(data) != entry["size_bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError(f"source changed while reading: {relative}")
        values = (_decode(line) for line in data.splitlines() if line.strip()) if table in JSONL_TABLES else [_decode(data)]
        for row in values:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str):
                raise ValueError(f"legacy row must have a string id: {relative}")
            if row.get("schema_version") != 2:
                raise ValueError(f"expected schema_version 2: {relative}")
            yield row, relative


def _git_state(source: Path) -> dict:
    def run(*args):
        try:
            result = subprocess.run(["git", "--no-optional-locks", "-C", str(source), *args],
                                    capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return None
    return {"head": run("rev-parse", "HEAD"),
            "data_status_porcelain": run("status", "--porcelain=v1", "--untracked-files=all", "--", "data"),
            "input": "working_tree_bytes"}


def _native_index(root: Path) -> dict:
    result = {}
    for entity in ENTITIES:
        for row, path in schema_v3.iter_native_records(root, entity):
            record_id = row["id"]
            if record_id in result:
                raise ValueError(f"duplicate native ID: {record_id}")
            result[record_id] = (entity, row, path.relative_to(root).as_posix())
    return result


def _field_destination(table: str, key: str, native: dict) -> list[str]:
    if key == "schema_version":
        return ["data/schema.json (v3 dataset marker)", "_legacy.keys (v2 constant projection)"]
    if key == "kind":
        return ["kind"]
    if key == "metadata":
        return ["metadata", "_legacy.metadata_aliases"]
    if key in ("segments", "paragraphs"):
        return ["blocks[].range|literal", "blocks[] timing/other fields", "text",
                "blocks[].input_text|input_text_ref (exact immutable source range)",
                "array position -> original block index"]
    if key == "members":
        return ["members[]", "array position -> original member position"]
    if key == "paragraphs_match_text" and key not in native:
        return ["text + blocks -> exact paragraph consistency projection"]
    if key == "quality":
        return ["quality", "blocks + time_unit -> exact timing_issues projection when derived"]
    if key == "confirmation_ids":
        return ["annotations.targets[].confirmation_index (reverse projection)"]
    if key in ("item_id", "item_ids", "audio_ids", "transcript_ids", "derived_from_id", "input_units_from_id", "article_item_ids"):
        container = "targets" if table in ("confirmations", "attributions") else "inputs"
        return [f"{container}[].role/target_id", "_legacy.keys (presence)"]
    if key in ("edited_transcript_id", "edited_transcript_ids"):
        return ["targets[].role/target_id", "_legacy.keys (presence)"]
    if key in ("review_document_markdown", "html"):
        return [f"inputs[role={key}].target_id", "assets artifact text/local_path/sha256/size_bytes"]
    if table == "audio" and key == "downloads":
        return ["downloads[].archive_id", "assets[kind=archive]", "downloads[] other fields"]
    if key in native:
        return [key]
    return ["_legacy.keys and native projection recipe"]


def _old_hashes(value, path="") -> list[dict]:
    found = []
    if isinstance(value, dict):
        for key, nested in sorted(value.items()):
            location = path + "/" + key.replace("~", "~0").replace("/", "~1")
            if "sha256" in key and isinstance(nested, str):
                found.append({"pointer": location, "value": nested})
            found.extend(_old_hashes(nested, location))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            found.extend(_old_hashes(nested, path + f"/{index}"))
    return found


def _verify_records(source: Path, output: Path, files: list[dict]) -> dict:
    native = _native_index(output)
    records = []
    counts = {}
    seen_global = set()
    for table in TABLES:
        projected = {}
        for row, _ in schema_v3.iter_legacy_records(output, table):
            if row["id"] in projected:
                raise ValueError(f"duplicate projected ID in {table}: {row['id']}")
            projected[row["id"]] = row
        count = 0
        for old, relative in _source_rows(source, table, files):
            record_id = old["id"]
            if record_id in seen_global:
                raise ValueError(f"duplicate source ID: {record_id}")
            seen_global.add(record_id)
            restored = projected.pop(record_id, None)
            if restored is None or _canonical(old) != _canonical(restored):
                raise ValueError(f"exact legacy JSON mismatch: {table}/{record_id}")
            if record_id not in native or native[record_id][0] != TABLE_ENTITY[table]:
                raise ValueError(f"old ID missing from native entity: {table}/{record_id}")
            entity, stored, target_path = native[record_id]
            records.append({"id": record_id, "legacy_table": table,
                            "source_path": relative, "native_entity": entity,
                            "native_path": target_path, "legacy_json_sha256": _digest(old),
                            "projection_json_sha256": _digest(restored), "exact_json_equal": True,
                            "old_hashes": _old_hashes(old),
                            "fields": [{"name": key, "json_sha256": _digest(old[key]),
                                        "destination": _field_destination(table, key, stored)}
                                       for key in sorted(old)]})
            count += 1
        if projected:
            raise ValueError(f"extra projected records in {table}: {sorted(projected)}")
        counts[table] = count
    if not sum(counts.values()):
        raise ValueError("source contains no legacy records")
    references = []
    for record_id, (_, row, path) in sorted(native.items()):
        for field in ("inputs", "targets"):
            for index, reference in enumerate(row.get(field, [])):
                references.append({"from_id": record_id, "path": path,
                                   "pointer": f"/{field}/{index}", **reference})
        for index, download in enumerate(row.get("downloads", [])):
            if "archive_id" in download:
                references.append({"from_id": record_id, "path": path,
                                   "pointer": f"/downloads/{index}/archive_id",
                                   "target_id": download["archive_id"], "role": "archive"})
        for index, block in enumerate(row.get("blocks", [])):
            if "input_text_ref" in block:
                references.append({"from_id": record_id, "path": path,
                                   "pointer": f"/blocks/{index}/input_text_ref",
                                   "role": "immutable_input_text", **block["input_text_ref"]})
        for field, target_field in (("members", "item_id"), ("relations", "target_item_id")):
            for index, relation in enumerate(row.get(field, [])):
                if target_field in relation:
                    references.append({"from_id": record_id, "path": path,
                                       "pointer": f"/{field}/{index}/{target_field}",
                                       "role": field, "target_id": relation[target_field]})
        if row.get("parent_id") is not None:
            references.append({"from_id": record_id, "path": path, "pointer": "/parent_id",
                               "role": "parent", "target_id": row["parent_id"]})
    references_by_target = {}
    for reference in references:
        references_by_target.setdefault(reference.get("target_id"), []).append(reference)
    artifacts = []
    for record_id, (entity, row, path) in sorted(native.items()):
        if record_id not in seen_global:
            artifacts.append({"id": record_id, "entity": entity, "kind": row.get("kind"),
                              "native_path": path, "size_bytes": row.get("size_bytes"),
                              "sha256": row.get("sha256"), "local_path": row.get("local_path"),
                              "referenced_by": references_by_target.get(record_id, [])})
    return {"legacy_counts": counts, "records": records, "references": references,
            "new_artifacts": artifacts,
            "native_counts": {entity: sum(value[0] == entity for value in native.values()) for entity in ENTITIES}}


def _validate_output(root: Path) -> None:
    errors = schema_v3.validate_native(root)
    if errors:
        raise ValueError("native validation failed: " + "; ".join(errors[:20]))
    allowed_files = {"items.jsonl", "assets.jsonl", "annotations.jsonl", "schema.json"}
    allowed_dirs = {"documents", "artifacts"}
    for child in (root / "data").iterdir():
        if child.name not in (allowed_dirs if child.is_dir() else allowed_files):
            raise ValueError(f"unexpected output entry: {child.name}")
    actual = {child.name for child in (root / "data").iterdir()}
    required = allowed_files | {"documents"}
    if not required.issubset(actual):
        raise ValueError(f"incomplete native layout: {sorted(required - actual)}")


def _write_report(root: Path, report: dict) -> None:
    (root / REPORT_NAME).write_text(json.dumps(report, ensure_ascii=False, sort_keys=True,
                                             indent=2, allow_nan=False) + "\n", encoding="utf-8")


def migrate(source: Path, output: Path, *, verify_only: bool = False) -> dict:
    """Migrate or independently verify; failures never publish a complete target.

    ``source`` is a complete v2 repository root; ``output`` is an independent
    absent/empty root (or an existing completed migration for verify_only).
    The returned report contains hashes/locations, never a duplicate old row.
    """
    source, output = _paths(Path(source), Path(output))
    source_files = _inventory(source)
    _legacy_layout(source, source_files)
    source_evidence = {"git": _git_state(source), "files": source_files,
                       "manifest_sha256": _digest(source_files),
                       "size_bytes": sum(row["size_bytes"] for row in source_files)}
    if verify_only:
        if not output.is_dir() or not (output / REPORT_NAME).is_file():
            raise ValueError("verify-only requires a completed migration report")
        _check_no_links(output / REPORT_NAME)
        target_files = _inventory(output)  # Reject links before any native decoder opens paths.
        saved = _decode((output / REPORT_NAME).read_bytes())
        if saved.get("report_sha256") != _digest({key: value for key, value in saved.items() if key != "report_sha256"}):
            raise ValueError("migration report SHA-256 mismatch")
        if saved.get("status") != "complete" or saved.get("source") != source_evidence:
            raise ValueError("source evidence differs from completed migration")
        _validate_output(output)
        verification = _verify_records(source, output, source_files)
        target_files = _inventory(output)
        target_evidence = {"files": target_files, "manifest_sha256": _digest(target_files),
                           "size_bytes": sum(row["size_bytes"] for row in target_files)}
        if target_evidence != saved.get("target"):
            raise ValueError("target file inventory differs from completed migration")
        if verification != saved.get("verification"):
            raise ValueError("record verification differs from completed migration")
        if _inventory(source) != source_files:
            raise ValueError("source changed during verification")
        return saved
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("output must be absent or an empty directory; refusing to overwrite")
    output.parent.mkdir(parents=True, exist_ok=True)
    _check_no_links(output.parent)
    lock = output.parent / ("." + output.name + ".schema-v3.lock")
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise ValueError(f"migration output is locked: {output}") from error
    os.close(descriptor)
    staging = None
    try:
        if output.exists() and (not output.is_dir() or any(output.iterdir())):
            raise ValueError("output changed; refusing to overwrite")
        staging = Path(tempfile.mkdtemp(prefix="." + output.name + ".incomplete-", dir=output.parent))
        tables = {table: (row for row, _ in _source_rows(source, table, source_files)) for table in TABLES}
        schema_v3.write_legacy_dataset(staging, tables)
        _validate_output(staging)
        verification = _verify_records(source, staging, source_files)
        if _inventory(source) != source_files:
            raise ValueError("source changed during migration")
        target_files = _inventory(staging)
        report = {"report_version": 1, "schema_version": 3, "status": "complete",
                  "source": source_evidence,
                  "target": {"files": target_files, "manifest_sha256": _digest(target_files),
                             "size_bytes": sum(row["size_bytes"] for row in target_files)},
                  "verification": verification}
        report["report_sha256"] = _digest(report)
        _write_report(staging, report)
        _check_no_links(output)
        if output.exists():
            if any(output.iterdir()):
                raise ValueError("output changed; refusing to overwrite")
            output.rmdir()  # Only the checked, empty, independent destination root.
        staging.rename(output)
        staging = None
        return report
    finally:
        if staging is not None:
            # tempfile gave this private sibling path; never remove source/output.
            if staging.parent == output.parent and staging.name.startswith("." + output.name + ".incomplete-"):
                shutil.rmtree(staging)
        lock.unlink()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Migrate a read-only v2 repository snapshot to an independent v3 root")
    parser.add_argument("--source", required=True, type=Path, help="complete repository root containing v2 data/")
    parser.add_argument("--output", required=True, type=Path, help="independent absent or empty destination root")
    parser.add_argument("--verify-only", action="store_true", help="read-only recheck of an existing completed migration")
    args = parser.parse_args(argv)
    try:
        report = migrate(args.source, args.output, verify_only=args.verify_only)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, "verify_only": args.verify_only,
                      "report": str(args.output / REPORT_NAME),
                      "report_sha256": report["report_sha256"],
                      "legacy_counts": report["verification"]["legacy_counts"],
                      "native_counts": report["verification"]["native_counts"]}, ensure_ascii=False))
    return 0
