#!/usr/bin/env python3
"""Restore hash-addressed audio using the single data/media.jsonl index."""

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

from weimingzi_corpus.data import read_jsonl, relative_path, safe_target

ROOT = Path(__file__).resolve().parents[1]


def target_path(name):
    return safe_target(ROOT, name)


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def valid(path, row):
    return (
        path.is_file()
        and path.stat().st_size == row["bytes"]
        and digest(path) == row["sha256"]
    )


def load_media(name="data/media.jsonl"):
    groups = {}
    paths = set()
    shas = set()
    members = set()
    for record in read_jsonl(target_path(name)):
        if record.get("availability") != "release":
            continue
        target_path(record["path"])
        if record["path"] in paths or record["sha256"] in shas:
            raise ValueError("Duplicate restore destination or audio hash")
        paths.add(record["path"])
        shas.add(record["sha256"])
        if (
            not isinstance(record["bytes"], int)
            or record["bytes"] < 0
            or not re.fullmatch("[0-9a-f]{64}", record["sha256"])
        ):
            raise ValueError("Invalid audio hash/size")
        downloads = record.get("downloads", [])
        if not downloads:
            raise ValueError("Missing audio download locator")
        # Multiple valid locators can exist; the first is sufficient for a restore.
        download = downloads[0]
        asset = download["asset"]
        tag = download["release_tag"]
        member = download["member"]
        relative_path(tag)
        relative_path(member)
        if len(relative_path(asset["name"]).parts) != 1:
            raise ValueError("Asset name must be a plain filename")
        if (
            not isinstance(asset["bytes"], int)
            or asset["bytes"] < 0
            or not re.fullmatch("[0-9a-f]{64}", asset["sha256"])
        ):
            raise ValueError("Invalid archive hash/size")
        if not asset["url"].startswith("https://"):
            raise ValueError("Archive URL must use HTTPS")
        key = tag + "/" + asset["name"]
        if (key, member) in members:
            raise ValueError("Duplicate archive member")
        members.add((key, member))
        group = groups.setdefault(
            key, {"release_tag": tag, "asset": asset, "files": []}
        )
        if group["asset"] != asset:
            raise ValueError("Conflicting archive metadata")
        group["files"].append(
            {
                "path": record["path"],
                "bytes": record["bytes"],
                "sha256": record["sha256"],
                "archive_path": member,
            }
        )
    return groups


def download(asset, release_tag):
    cache = target_path(".cache/media/" + release_tag + "/" + asset["name"])
    cache.parent.mkdir(parents=True, exist_ok=True)
    if valid(cache, asset):
        return cache
    partial = cache.with_name(cache.name + ".part")
    for attempt in range(1, 4):
        try:
            request = Request(
                asset["url"], headers={"User-Agent": "weimingzi-data/3.0"}
            )
            with (
                urlopen(request, timeout=120) as response,
                partial.open("wb") as output,
            ):
                shutil.copyfileobj(response, output, 4 * 1024 * 1024)
            if not valid(partial, asset):
                raise ValueError("Archive size or SHA-256 mismatch: " + asset["name"])
            os.replace(partial, cache)
            return cache
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 * attempt)
    raise RuntimeError("Download did not complete")


def restore_archive(archive, rows):
    expected = {row["archive_path"]: row for row in rows}
    if len(expected) != len(rows) or len({r["path"] for r in rows}) != len(rows):
        raise ValueError("Duplicate ZIP entry assignment")
    for row in rows:
        target_path(row["path"])
        relative_path(row["archive_path"])
    with ZipFile(archive) as bundle:
        members = bundle.infolist()
        if len(members) != len(expected) or {m.filename for m in members} != set(
            expected
        ):
            raise ValueError("Unexpected archive members")
        for member in members:
            relative_path(member.filename)
            row = expected[member.filename]
            if member.is_dir() or member.file_size != row["bytes"]:
                raise ValueError("Unexpected archive member size")
        for member in members:
            row = expected[member.filename]
            target = target_path(row["path"])
            if valid(target, row):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_name(target.name + ".part")
            with bundle.open(member) as source, partial.open("wb") as output:
                shutil.copyfileobj(source, output, 4 * 1024 * 1024)
            if not valid(partial, row):
                raise ValueError("Audio SHA-256 mismatch: " + row["path"])
            os.replace(partial, target)
    return len(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", default="data/media.jsonl")
    parser.add_argument(
        "--asset", action="append", help="release-tag/archive.zip; repeatable"
    )
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    groups = load_media(args.index)
    if args.asset:
        unknown = set(args.asset) - groups.keys()
        if unknown:
            parser.error("Unknown archive: " + ", ".join(sorted(unknown)))
        groups = {k: v for k, v in groups.items() if k in args.asset}
    rows = [row for group in groups.values() for row in group["files"]]
    if args.list:
        print(
            json.dumps(
                {
                    "audio_files": len(rows),
                    "audio_bytes": sum(r["bytes"] for r in rows),
                    "archives": list(groups),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.verify_only:
        missing = [r["path"] for r in rows if not valid(target_path(r["path"]), r)]
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
        if not all(valid(target_path(r["path"]), r) for r in group["files"]):
            print("Downloading " + name, flush=True)
            restore_archive(
                download(group["asset"], group["release_tag"]), group["files"]
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
