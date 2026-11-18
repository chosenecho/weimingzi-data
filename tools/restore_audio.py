#!/usr/bin/env python3
"""Restore hash-addressed audio directly from native audio and archive assets."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import json

from weimingzi_corpus.records import (
    read_json,
    read_jsonl,
    validate_relative_path,
    resolve_repository_path,
)

ROOT = Path(__file__).resolve().parents[1]


def resolve_audio_repository_path(name):
    return resolve_repository_path(ROOT, name)


def file_sha256(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def is_file_intact(path, row):
    return (
        path.is_file()
        and path.stat().st_size == row["size_bytes"]
        and file_sha256(path) == row["sha256"]
    )


def audio_index_context():
    """Return the native assets index and its schema dependency."""
    schema = resolve_audio_repository_path("data/schema.json")
    expected = {
        "schema_version": 3,
        "entities": ["items", "documents", "assets", "annotations"],
        "range_unit": "unicode_codepoint",
        "range_end": "exclusive",
    }
    if read_json(schema) != expected:
        raise ValueError("Audio restoration requires the current native schema")
    return {
        "path": resolve_audio_repository_path("data/assets.jsonl"),
        "dependencies": [schema],
    }


def load_audio_archive_groups():
    context = audio_index_context()
    assets = {}
    for record in read_jsonl(context["path"]):
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            raise ValueError("Invalid native asset record")
        if record["id"] in assets:
            raise ValueError("Duplicate asset ID")
        assets[record["id"]] = record
    records = (record for record in assets.values() if record.get("kind") == "audio")
    groups = {}
    paths = set()
    shas = set()
    members = set()
    for record in records:
        if record.get("availability") != "available":
            continue
        resolve_audio_repository_path(record["local_path"])
        if record["local_path"] in paths or record["sha256"] in shas:
            raise ValueError("Duplicate restore destination or audio hash")
        paths.add(record["local_path"])
        shas.add(record["sha256"])
        if (
            type(record["size_bytes"]) is not int
            or record["size_bytes"] < 0
            or not re.fullmatch("[0-9a-f]{64}", record["sha256"])
        ):
            raise ValueError("Invalid audio hash/size")
        downloads = record.get("downloads", [])
        if not downloads:
            raise ValueError("Missing audio download locator")
        # Multiple valid locators can exist; the first is sufficient for a restore.
        location = downloads[0]
        archive = assets.get(location.get("archive_id"))
        if archive is None or archive.get("kind") != "archive":
            raise ValueError("Audio download must reference a native archive asset")
        tag = location["release_tag"]
        member = location["member_path"]
        validate_relative_path(tag)
        validate_relative_path(member)
        if len(validate_relative_path(archive["name"]).parts) != 1:
            raise ValueError("Archive name must be a plain filename")
        if (
            type(archive["size_bytes"]) is not int
            or archive["size_bytes"] < 0
            or not re.fullmatch("[0-9a-f]{64}", archive["sha256"])
        ):
            raise ValueError("Invalid archive hash/size")
        if not archive["url"].startswith("https://"):
            raise ValueError("Archive URL must use HTTPS")
        key = tag + "/" + archive["name"]
        if (key, member) in members:
            raise ValueError("Duplicate archive member")
        members.add((key, member))
        group = groups.setdefault(
            key, {"release_tag": tag, "archive": archive, "files": []}
        )
        if group["archive"] != archive:
            raise ValueError("Conflicting archive metadata")
        group["files"].append(
            {
                "local_path": record["local_path"],
                "size_bytes": record["size_bytes"],
                "sha256": record["sha256"],
                "member_path": member,
            }
        )
    return groups


def download_archive(archive, release_tag):
    cache = resolve_audio_repository_path(
        ".cache/media/" + release_tag + "/" + archive["name"]
    )
    cache.parent.mkdir(parents=True, exist_ok=True)
    if is_file_intact(cache, archive):
        return cache
    partial = cache.with_name(cache.name + ".part")
    for attempt in range(1, 4):
        try:
            request = Request(
                archive["url"], headers={"User-Agent": "weimingzi-corpus/2.0"}
            )
            with (
                urlopen(request, timeout=120) as response,
                partial.open("wb") as output,
            ):
                shutil.copyfileobj(response, output, 4 * 1024 * 1024)
            if not is_file_intact(partial, archive):
                raise ValueError("Archive size or SHA-256 mismatch: " + archive["name"])
            os.replace(partial, cache)
            return cache
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 * attempt)
    raise RuntimeError("Download did not complete")


def restore_audio_archive(archive, rows):
    expected = {row["member_path"]: row for row in rows}
    if len(expected) != len(rows) or len({r["local_path"] for r in rows}) != len(rows):
        raise ValueError("Duplicate ZIP entry assignment")
    for row in rows:
        resolve_audio_repository_path(row["local_path"])
        validate_relative_path(row["member_path"])
    with ZipFile(archive) as bundle:
        members = bundle.infolist()
        if len(members) != len(expected) or {m.filename for m in members} != set(
            expected
        ):
            raise ValueError("Unexpected archive members")
        for member in members:
            validate_relative_path(member.filename)
            row = expected[member.filename]
            if member.is_dir() or member.file_size != row["size_bytes"]:
                raise ValueError("Unexpected archive member size")
        for member in members:
            row = expected[member.filename]
            target = resolve_audio_repository_path(row["local_path"])
            if is_file_intact(target, row):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_name(target.name + ".part")
            with bundle.open(member) as source, partial.open("wb") as output:
                shutil.copyfileobj(source, output, 4 * 1024 * 1024)
            if not is_file_intact(partial, row):
                raise ValueError("Audio SHA-256 mismatch: " + row["local_path"])
            os.replace(partial, target)
    return len(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive", action="append", help="release-tag/archive.zip; repeatable"
    )
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    groups = load_audio_archive_groups()
    if args.archive:
        unknown = set(args.archive) - groups.keys()
        if unknown:
            parser.error("Unknown archive: " + ", ".join(sorted(unknown)))
        groups = {k: v for k, v in groups.items() if k in args.archive}
    rows = [row for group in groups.values() for row in group["files"]]
    if args.list:
        print(
            json.dumps(
                {
                    "audio_files": len(rows),
                    "audio_bytes": sum(r["size_bytes"] for r in rows),
                    "archives": list(groups),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.verify_only:
        missing = [
            r["local_path"]
            for r in rows
            if not is_file_intact(resolve_audio_repository_path(r["local_path"]), r)
        ]
        print(
            json.dumps(
                {"checked": len(rows), "missing_or_invalid": missing},
                ensure_ascii=False,
                indent=2,
            )
        )
        return bool(missing)
    restored = 0
    for name, group in groups.items():
        if not all(
            is_file_intact(resolve_audio_repository_path(r["local_path"]), r)
            for r in group["files"]
        ):
            print("Downloading " + name, flush=True)
            restore_audio_archive(
                download_archive(group["archive"], group["release_tag"]), group["files"]
            )
        restored += len(group["files"])
        print(f"Verified {restored} / {len(rows)} audio files", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
