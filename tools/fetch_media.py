#!/usr/bin/env python3
"""Download immutable Release archives into the current data/ layout."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import time
from urllib.request import Request, urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
COLLECTIONS = {
    "base": "metadata/media/base.json",
    "asr-2026-11-03": "metadata/media/asr-2026-11-03.json",
}

def safe_relative(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if not path.parts or path.is_absolute() or ".." in path.parts or ":" in name or "\\" in name:
        raise ValueError(f"Unsafe relative path: {name!r}")
    return path

def target_path(name: str) -> Path:
    path = (ROOT / Path(*safe_relative(name).parts)).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError(f"Path escapes repository: {name}")
    return path

def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()

def valid(path: Path, row: dict) -> bool:
    return path.is_file() and path.stat().st_size == row["bytes"] and digest(path) == row["sha256"]

def load_manifest(name: str) -> dict:
    manifest = json.loads(target_path(name).read_text(encoding="utf-8"))
    if manifest.get("schema") != "weimingzi-media-v2":
        raise ValueError(f"Expected a v2 media manifest: {name}")
    assets = {}
    for asset in manifest["assets"]:
        if len(safe_relative(asset["name"]).parts) != 1:
            raise ValueError("Asset names must be plain filenames")
        if asset["name"] in assets:
            raise ValueError("Duplicate asset name")
        safe_relative(manifest["release_tag"])
        assets[asset["name"]] = asset
    paths, members = set(), set()
    for row in manifest["files"]:
        target_path(row["path"])
        safe_relative(row["archive_path"])
        member = (row["archive"], row["archive_path"])
        if row["archive"] not in assets or row["path"] in paths or member in members:
            raise ValueError("Duplicate or unassigned audio manifest entry")
        paths.add(row["path"])
        members.add(member)
    for row in [*manifest["assets"], *manifest["files"]]:
        if not isinstance(row["bytes"], int) or row["bytes"] < 0:
            raise ValueError("Invalid byte count")
        if not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            raise ValueError("Invalid SHA-256")
    return manifest

def download(asset: dict, release_tag: str) -> Path:
    cache = target_path(".cache/media/" + release_tag + "/" + asset["name"])
    cache.parent.mkdir(parents=True, exist_ok=True)
    if valid(cache, asset):
        return cache
    partial = cache.with_name(cache.name + ".part")
    for attempt in range(1, 4):
        try:
            request = Request(asset["url"], headers={"User-Agent": "weimingzi-data/2.0"})
            with urlopen(request, timeout=120) as response, partial.open("wb") as output:
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

def restore_archive(archive: Path, rows: list[dict]) -> int:
    expected = {row["archive_path"]: row for row in rows}
    if len(expected) != len(rows):
        raise ValueError("Duplicate ZIP entry assignment")
    with ZipFile(archive) as bundle:
        members = bundle.infolist()
        if len(members) != len(expected) or {m.filename for m in members} != set(expected):
            raise ValueError("Unexpected archive members")
        for member in members:
            row = expected[member.filename]
            safe_relative(member.filename)
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

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--collection", choices=["all", *COLLECTIONS], default=None,
                           help="Audio collection; default: all")
    selection.add_argument("--manifest", help="Repository-relative v2 media manifest")
    parser.add_argument("--asset", action="append", help="Restore only this ZIP asset; repeatable")
    parser.add_argument("--verify-only", action="store_true", help="Check restored audio without network")
    parser.add_argument("--list", action="store_true", help="Print selected audio counts and byte sizes")
    args = parser.parse_args(argv)
    collection = args.collection or "all"
    names = [args.manifest] if args.manifest else (
        list(COLLECTIONS.values()) if collection == "all" else [COLLECTIONS[collection]]
    )
    manifests = [(name, load_manifest(name)) for name in names]
    all_paths = [row["path"] for _, manifest in manifests for row in manifest["files"]]
    if len(set(all_paths)) != len(all_paths):
        raise ValueError("Collections contain duplicate restore destinations")
    known = {asset["name"] for _, manifest in manifests for asset in manifest["assets"]}
    if args.asset and not set(args.asset).issubset(known):
        parser.error("Unknown asset name for the selected collection")
    selected = [
        (manifest, asset, [row for row in manifest["files"] if row["archive"] == asset["name"]])
        for _, manifest in manifests for asset in manifest["assets"]
        if not args.asset or asset["name"] in args.asset
    ]
    rows = [row for _, _, group in selected for row in group]
    if args.list:
        print(json.dumps({"audio_files": len(rows), "audio_bytes": sum(r["bytes"] for r in rows),
                          "archive_bytes": sum(a["bytes"] for _, a, _ in selected),
                          "assets": [a["name"] for _, a, _ in selected]}, ensure_ascii=False, indent=2))
        return 0
    if args.verify_only:
        missing = [row["path"] for row in rows if not valid(target_path(row["path"]), row)]
        print(json.dumps({"checked": len(rows), "missing_or_invalid": missing}, ensure_ascii=False, indent=2))
        return 1 if missing else 0
    restored = 0
    for manifest, asset, group in selected:
        if all(valid(target_path(row["path"]), row) for row in group):
            restored += len(group)
            print(f"Verified {restored} / {len(rows)} audio files", flush=True)
            continue
        print("Downloading " + asset["name"], flush=True)
        archive = download(asset, manifest["release_tag"])
        restored += restore_archive(archive, group)
        print(f"Verified {restored} / {len(rows)} audio files", flush=True)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
