"""Versioned directory protocol shared by offline corpus readers and writers."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
import unicodedata
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def decode(value):
    result = json.loads(value, object_pairs_hook=_pairs,
                        parse_constant=lambda value: (_ for _ in ()).throw(ValueError("invalid JSON constant: " + value)))
    encode(result)
    return result


def read_json(path):
    return decode(Path(path).read_bytes())


def safe_file(root, name):
    if (not isinstance(name, str) or not name or "\\" in name or ":" in name
            or PurePosixPath(name).is_absolute() or any(p in {"", ".", ".."} for p in name.split("/"))):
        raise ValueError("nonportable bundle path")
    path = Path(root)
    for part in name.split("/"):
        stem = part.split(".")[0].upper()
        if (part.endswith((" ", ".")) or any(ord(char) < 32 or char in '<>"|?*' for char in part)
                or stem in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}):
            raise ValueError("bundle path is not portable across operating systems")
        path = path / part
        if path.is_symlink():
            raise ValueError("symbolic links are not allowed in bundles")
    return path


def identity(root, name):
    path = safe_file(root, name)
    if not path.is_file():
        raise ValueError("missing bundle file: " + name)
    sha, size = hashlib.sha256(), 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
            size += len(block)
    return {"path": name, "size": size, "sha256": sha.hexdigest()}


def write_bytes(root, name, data):
    path = safe_file(root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def write_json(root, name, value):
    write_bytes(root, name, encode(value) + b"\n")


def write_rows(root, name, rows):
    path = safe_file(root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        for row in rows:
            stream.write(encode(row) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def read_rows(path):
    rows = []
    with Path(path).open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                raise ValueError(f"empty JSONL row at line {number}")
            row = decode(line)
            if not isinstance(row, dict):
                raise ValueError("JSONL records must be objects")
            rows.append(row)
    return rows


def seal(root, format, **metadata):
    names = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
    if "manifest.json" in names:
        raise ValueError("cannot reseal an existing snapshot")
    result = {"format": format, "created_at": datetime.now(UTC).isoformat(), **metadata,
              "files": [identity(root, name) for name in names]}
    result["bundle_id"] = digest(result)
    write_json(root, "manifest.json", result)
    return result


def verify(root, format=None):
    root = Path(root).absolute()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("bundle must be a directory without links")
    path = safe_file(root, "manifest.json")
    if not path.is_file() or path.stat().st_size > 16 * 1024**2:
        raise ValueError("missing or oversized manifest")
    manifest = read_json(path)
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    if format is not None and manifest.get("format") != format:
        raise ValueError("unsupported bundle format")
    if manifest.get("bundle_id") != digest({k: v for k, v in manifest.items() if k != "bundle_id"}):
        raise ValueError("manifest identity mismatch")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("empty bundle inventory")
    names, portable_names = set(), set()
    for entry in files:
        if (not isinstance(entry, dict) or set(entry) != {"path", "size", "sha256"}
                or not isinstance(entry["path"], str) or type(entry["size"]) is not int
                or entry["size"] < 0 or not isinstance(entry["sha256"], str)):
            raise ValueError("invalid inventory entry")
        name = entry["path"]
        portable_name = unicodedata.normalize("NFC", name).casefold()
        if portable_name in portable_names or portable_name == "manifest.json":
            raise ValueError("duplicate or reserved inventory path")
        if identity(root, name) != entry:
            raise ValueError("file identity mismatch: " + name)
        names.add(name)
        portable_names.add(portable_name)
    actual = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("symbolic links are not allowed")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    if actual != names | {"manifest.json"}:
        raise ValueError("inventory differs from bundle files")
    return manifest


def copy_bundle(source, destination):
    before = verify(source)
    def copy_file(source_file, destination_file):
        with Path(source_file).open("rb") as reader, Path(destination_file).open("xb") as writer:
            shutil.copyfileobj(reader, writer, length=1024 * 1024)
            writer.flush()
            os.fsync(writer.fileno())
        return str(destination_file)
    shutil.copytree(source, destination, copy_function=copy_file)
    if verify(destination)["bundle_id"] != before["bundle_id"]:
        raise ValueError("source changed during copy")
    return before


@contextmanager
def create(output, *, checked=True):
    """Publish a complete new snapshot. A stable lock excludes cooperating writers."""
    output = Path(output).absolute()
    if any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError("destination must not use links")
    output.parent.mkdir(parents=True, exist_ok=True)
    lock = output.parent / ("." + output.name + ".lock")
    with lock.open("a+b") as stream:
        stream.seek(0)
        stream.write(b"0")
        stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            if output.exists():
                raise ValueError("destination already exists; use a new snapshot")
            with tempfile.TemporaryDirectory(prefix="." + output.name + "-", dir=output.parent) as temporary:
                stage = Path(temporary) / "bundle"
                stage.mkdir()
                yield stage
                if checked:
                    verify(stage)
                if output.exists():
                    raise ValueError("destination appeared during staging")
                if os.name != "nt":
                    for directory in [p for p in stage.rglob("*") if p.is_dir()] + [stage]:
                        descriptor = os.open(directory, os.O_RDONLY)
                        try:
                            os.fsync(descriptor)
                        finally:
                            os.close(descriptor)
                for attempt in range(10):
                    try:
                        if output.exists():
                            raise ValueError("destination appeared during publication")
                        stage.rename(output)
                        break
                    except PermissionError:
                        if os.name != "nt" or attempt == 9:
                            raise
                        time.sleep(0.05 * (attempt + 1))
                if os.name != "nt":
                    descriptor = os.open(output.parent, os.O_RDONLY)
                    try:
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
