#!/usr/bin/env python3
"""Read real audio archives and write an immutable, scoped restore audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

import restore_audio


def now():
    return datetime.now(timezone.utc).isoformat()


def stream_digest(stream):
    digest = hashlib.sha256()
    size = 0
    for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
        size += len(block)
        digest.update(block)
    return {"size_bytes": size, "sha256": digest.hexdigest()}


def digest_file(path):
    with path.open("rb") as stream:
        return stream_digest(stream)


def audit_group(key, group):
    result = {
        "archive_key": key,
        "started_at": now(),
        "expected_archive": dict(group["archive"]),
        "files": [],
        "ok": False,
    }
    try:
        archive = restore_audio.download_archive(
            group["archive"], group["release_tag"]
        )
        observed = digest_file(archive)
        result["observed_archive"] = observed
        if any(observed[name] != group["archive"][name] for name in observed):
            raise ValueError("Archive size or SHA-256 mismatch")
        restore_audio.restore_audio_archive(archive, group["files"])
        with ZipFile(archive) as bundle:
            for row in group["files"]:
                with bundle.open(row["member_path"]) as source:
                    member = stream_digest(source)
                target = restore_audio.resolve_audio_repository_path(row["local_path"])
                restored = digest_file(target)
                expected = {name: row[name] for name in ("size_bytes", "sha256")}
                entry = {
                    "member_path": row["member_path"],
                    "local_path": row["local_path"],
                    "expected": expected,
                    "observed_member": member,
                    "observed_restored": restored,
                    "ok": member == expected and restored == expected,
                }
                result["files"].append(entry)
                if not entry["ok"]:
                    raise ValueError("Member or restored file mismatch: " + row["local_path"])
        result["ok"] = True
    except Exception as error:
        result["error"] = {"type": type(error).__name__, "message": str(error)}
    result["completed_at"] = now()
    return result


def write_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(report, output, ensure_ascii=False, indent=2, allow_nan=False)
        output.write("\n")


def audit_temporary_group(key, group):
    original_root = restore_audio.ROOT
    try:
        with tempfile.TemporaryDirectory(prefix="audio-restore-audit-") as scratch:
            restore_audio.ROOT = Path(scratch)
            return audit_group(key, group)
    finally:
        restore_audio.ROOT = original_root


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", action="append", help="release-tag/archive.zip; repeatable")
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=2)
    parser.add_argument("--temporary-media", action="store_true",
                        help="restore one archive at a time in a temporary directory")
    parser.add_argument("--output", required=True, help="new JSON under preservation/checks/")
    args = parser.parse_args(argv)
    if args.temporary_media and args.workers != 1:
        parser.error("Temporary media mode requires --workers 1")
    output = restore_audio.resolve_audio_repository_path(args.output)
    checks = restore_audio.resolve_audio_repository_path("preservation/checks")
    if not output.is_relative_to(checks) or output.suffix != ".json":
        parser.error("Output must be a JSON file under preservation/checks/")
    checkpoints = output.with_suffix(".parts")
    if output.exists() or checkpoints.exists():
        parser.error("Output exists; choose a new versioned report")
    index = restore_audio.resolve_audio_repository_path("data/audio.jsonl")
    index_before = digest_file(index)
    groups = restore_audio.load_audio_archive_groups()
    all_archive_count = len(groups)
    all_audio_count = sum(len(group["files"]) for group in groups.values())
    if args.archive:
        unknown = set(args.archive) - groups.keys()
        if unknown:
            parser.error("Unknown archives: " + ", ".join(sorted(unknown)))
        groups = {key: group for key, group in groups.items() if key in args.archive}
    report = {
        "schema": "audio-restore-audit/v1",
        "started_at": now(),
        "index": {"path": "data/audio.jsonl", **index_before},
        "tools": {
            "audit_audio_restore.py": digest_file(Path(__file__).resolve()),
            "restore_audio.py": digest_file(Path(restore_audio.__file__).resolve()),
        },
        "scope": {
            "indexed_restorable_archives": all_archive_count,
            "indexed_restorable_audio": all_audio_count,
            "selected_archives": sorted(groups),
            "selected_audio": sum(len(group["files"]) for group in groups.values()),
            "media_storage": "temporary_per_archive" if args.temporary_media else "local_cache",
            "excludes": "Unavailable audio, content accuracy, rights, independent-copy and future availability claims",
        },
        "archives": [],
    }
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        operation = audit_temporary_group if args.temporary_media else audit_group
        futures = {executor.submit(operation, key, group): key for key, group in groups.items()}
        for future in as_completed(futures):
            result = future.result()
            report["archives"].append(result)
            write_report(checkpoints / (str(len(report["archives"])).zfill(3) + ".json"), {
                "schema": "audio-restore-audit-part/v1",
                "complete": False,
                "index": report["index"],
                "tools": report["tools"],
                "archive": result,
            })
            print(json.dumps({"archive": result["archive_key"], "ok": result["ok"],
                              "completed": len(report["archives"]), "total": len(groups),
                              "error": result.get("error")}), flush=True)
    report["archives"].sort(key=lambda result: result["archive_key"])
    report["index_unchanged"] = digest_file(index) == index_before
    report["ok"] = report["index_unchanged"] and all(result["ok"] for result in report["archives"])
    report["completed_at"] = now()
    write_report(output, report)
    print(json.dumps({"report": args.output, "ok": report["ok"]}), flush=True)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
