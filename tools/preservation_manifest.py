#!/usr/bin/env python3
"""Create and verify a SHA-256 fixity manifest for the archive preservation set."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

SCHEMA_VERSION = 1
CANONICAL_ROOTS = ("data", "selections")
SUPPORT_FILES = (
    "AGENTS.md",
    "README.md",
    "LICENSE",
    ".gitattributes",
    ".gitignore",
    ".github/workflows/checks.yml",
    ".github/ISSUE_TEMPLATE/archive-problem.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/data-correction.yml",
    "CONTENT-RIGHTS.md",
    "docs/AGENT-GUIDE.md",
    "docs/DATA-CARD.md",
    "docs/SCHEMA.md",
    "docs/GLOSSARY.md",
    "docs/DOWNLOAD.md",
    "docs/MAINTENANCE.md",
    "docs/INCREMENTAL-INGEST.md",
    "docs/INCREMENTAL-INGEST-SPEC.md",
    "docs/ALIBABA-FC-PROBE.md",
    "docs/CLOUDFLARE-PROBE.md",
    "docs/alibaba-fc-probe/2026-11-04.json",
    "docs/cloudflare-probe/2026-11-04.json",
    "docs/cloudflare-probe/2026-11-04-sessdata.json",
    "docs/cloudflare-probe/2026-11-04-zoku.json",
    "docs/contracts/ingest-batch-v1.schema.json",
    "docs/contracts/ingest-enrichment-v1.schema.json",
    "docs/contracts/ingest-media-asset-v1.schema.json",
    "docs/examples/INGEST-EXAMPLES.md",
    "docs/examples/ingest-policy.toml",
    "docs/examples/ingest-enrichment.json",
    "docs/examples/validate_ingest_example.py",
    "docs/examples/ingest-batch/manifest.json",
    "docs/examples/ingest-batch/records/articles/c-b21fe8194fe60f7b3d15f664.json",
    "docs/examples/ingest-batch/records/audio/m-d380123b4a48021487b43fe7.json",
    "docs/examples/ingest-batch/records/edited_transcripts/r-54185a7333b47acb2bf05e34.json",
    "docs/examples/ingest-batch/records/items/i-26a13f10fdfc708394760e5d.json",
    "docs/examples/ingest-batch/records/items/i-783d0e4a20ebf2c957bb5557.json",
    "docs/examples/ingest-batch/records/items/i-7bd9de4078c5688f711355b8.json",
    "docs/examples/ingest-batch/records/items/i-ac00e851f72a9d5a5dccc89c.json",
    "docs/examples/ingest-batch/records/posts/p-f6a779604bcdaf60bf7fbdd5.json",
    "docs/examples/ingest-batch/records/transcripts/t-a490aed5dbb30b0d37c34f10.json",
    "docs/ARCHIVE-ACCEPTANCE.md",
    "docs/PRESERVATION.md",
    "docs/PRESERVATION-ROADMAP.md",
    "functions/ingest-probe/README.md",
    "functions/ingest-probe/index.py",
    "functions/ingest-probe/requirements.lock.txt",
    "functions/ingest-probe/test_probe.py",
    "pyproject.toml",
    "src/weimingzi_corpus/__init__.py",
    "src/weimingzi_corpus/cli.py",
    "src/weimingzi_corpus/exports.py",
    "src/weimingzi_corpus/ingest/__init__.py",
    "src/weimingzi_corpus/ingest/errors.py",
    "src/weimingzi_corpus/ingest/manifest.py",
    "src/weimingzi_corpus/ingest/merge.py",
    "src/weimingzi_corpus/ingest/planning.py",
    "src/weimingzi_corpus/ingest/policy.py",
    "src/weimingzi_corpus/ingest/receipts.py",
    "src/weimingzi_corpus/records.py",
    "tools/corpus.py",
    "tools/preservation_manifest.py",
    "tools/preservation_check.ps1",
    "tools/restore_audio.py",
    "tools/check_repository.py",
    "tests/test_repository_links.py",
    "tests/test_preservation_check.py",
    "tests/test_preservation_manifest.py",
    "tests/test_corpus.py",
    "tests/test_ingest.py",
    "tests/test_restore_audio.py",
    "workers/ingest-probe/.gitignore",
    "workers/ingest-probe/pylock.toml",
    "workers/ingest-probe/pyproject.toml",
    "workers/ingest-probe/README.md",
    "workers/ingest-probe/src/cf_client.py",
    "workers/ingest-probe/src/crypto_compat.py",
    "workers/ingest-probe/src/entry.py",
    "workers/ingest-probe/src/probe.py",
    "workers/ingest-probe/src/settings.py",
    "workers/ingest-probe/test_probe.py",
    "workers/ingest-probe/vendor-wheels/README.md",
    "workers/ingest-probe/vendor-wheels/qrcode_terminal-0.8-py3-none-any.whl",
    "workers/ingest-probe/wrangler.jsonc",
    "preservation/checks/restore-drill-2026-11-05.json",
    "preservation/checks/restore-release-sample-2026-11-05.json",
)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
BASELINE_NAME_PATTERN = re.compile(
    r"^baseline-\d{4}-\d{2}-\d{2}(?:-v[1-9]\d*)?\.json$"
)


def canonical_json(value) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def manifest_digest(value: dict) -> str:
    content = {key: item for key, item in value.items() if key != "manifest_sha256"}
    return sha256_bytes(canonical_json(content).encode("utf-8"))


def file_digest(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def git_commit(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def scan_directory(root: Path, relative_root: str, category: str, errors: list) -> list:
    start = root / relative_root
    if start.is_symlink():
        errors.append({"path": relative_root, "error": "symlink_not_allowed"})
        return []
    if not start.is_dir():
        errors.append({"path": relative_root, "error": "missing_directory"})
        return []

    found = []

    def record_walk_error(error):
        filename = getattr(error, "filename", None)
        if filename:
            try:
                relative = Path(filename).relative_to(root).as_posix()
            except ValueError:
                relative = relative_root
        else:
            relative = relative_root
        errors.append({"path": relative, "error": str(error)})

    for current, directories, files in os.walk(
        start, topdown=True, onerror=record_walk_error, followlinks=False
    ):
        current_path = Path(current)
        safe_directories = []
        for directory in sorted(directories):
            candidate = current_path / directory
            if candidate.is_symlink():
                errors.append(
                    {
                        "path": candidate.relative_to(root).as_posix(),
                        "error": "symlink_not_allowed",
                    }
                )
            else:
                safe_directories.append(directory)
        directories[:] = safe_directories

        for filename in sorted(files):
            candidate = current_path / filename
            relative = candidate.relative_to(root).as_posix()
            try:
                if candidate.is_symlink():
                    raise ValueError("symlink_not_allowed")
                if not candidate.is_file():
                    raise ValueError("not_a_regular_file")
                size_bytes, digest = file_digest(candidate)
                found.append(
                    {
                        "path": relative,
                        "category": category,
                        "size_bytes": size_bytes,
                        "sha256": digest,
                    }
                )
            except (OSError, ValueError) as error:
                errors.append({"path": relative, "error": str(error)})
    return found


def collect_entries(root: Path) -> tuple[list, list]:
    errors = []
    entries = []
    for directory in CANONICAL_ROOTS:
        entries.extend(scan_directory(root, directory, "canonical_content", errors))

    support_paths = set()
    for relative in SUPPORT_FILES:
        if relative in support_paths:
            errors.append({"path": relative, "error": "duplicate_support_file"})
            continue
        support_paths.add(relative)
        path = root / Path(*PurePosixPath(relative).parts)
        try:
            candidate = root
            for part in PurePosixPath(relative).parts:
                candidate = candidate / part
                if candidate.is_symlink():
                    raise ValueError("symlink_not_allowed")
            if not path.is_file():
                raise ValueError("missing_support_file")
            size_bytes, digest = file_digest(path)
            entries.append(
                {
                    "path": relative,
                    "category": "supporting_context",
                    "size_bytes": size_bytes,
                    "sha256": digest,
                }
            )
        except (OSError, ValueError) as error:
            errors.append({"path": relative, "error": str(error)})

    entries.sort(key=lambda entry: entry["path"].encode("utf-8"))
    errors.sort(key=lambda item: (item["path"].encode("utf-8"), item["error"]))
    return entries, errors


def make_manifest(root: Path) -> dict:
    entries, errors = collect_entries(root)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repository_commit": git_commit(root),
        "scope": {
            "canonical_roots": list(CANONICAL_ROOTS),
            "supporting_context_files": list(SUPPORT_FILES),
            "excluded": {
                "docs/INDEX.md, docs/catalog/**, docs/counts.json": (
                    "generated navigation and counts; rebuildable from canonical data"
                ),
                ".cache/**, exports/**, SQLite, media/audio/**": (
                    "derived or restored working copies; verify media separately"
                ),
                "preservation/manifests/**": (
                    "baselines are versioned separately to avoid self-reference"
                ),
                "preservation/checks/*.jsonl": (
                    "append-only fixity events are maintained separately from the file baseline"
                ),
                "remote release archives": (
                    "not marked verified unless bytes are retrieved and read-back hashed"
                ),
            },
        },
        "files": entries,
        "errors": errors,
        "summary": {
            "file_count": len(entries),
            "total_size_bytes": sum(entry["size_bytes"] for entry in entries),
            "error_count": len(errors),
            "canonical_file_count": sum(
                entry["category"] == "canonical_content" for entry in entries
            ),
            "supporting_context_file_count": sum(
                entry["category"] == "supporting_context" for entry in entries
            ),
        },
    }
    manifest["manifest_sha256"] = manifest_digest(manifest)
    return manifest


def safe_repo_path(root: Path, value: str) -> Path:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or ":" in value
        or PurePosixPath(value).is_absolute()
        or ".." in PurePosixPath(value).parts
    ):
        raise ValueError(f"unsafe repository-relative path: {value!r}")
    path = root.resolve()
    for part in PurePosixPath(value).parts:
        path = path / part
        if path.is_symlink():
            raise ValueError(f"symlink path is not allowed: {value}")
    path = path.resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"path escapes repository: {value}")
    return path


def write_manifest(root: Path, relative_output: str) -> dict:
    output = safe_repo_path(root, relative_output)
    output_parts = PurePosixPath(relative_output).parts
    if output_parts[:2] != ("preservation", "manifests") or len(output_parts) < 3:
        raise ValueError("manifest output must be under preservation/manifests/")
    manifest = make_manifest(root)
    if manifest["errors"]:
        raise ValueError(
            "cannot create an incomplete manifest: "
            + json.dumps(manifest["errors"], ensure_ascii=False)
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    with path_lock(output):
        if output.exists():
            raise ValueError(f"refusing to overwrite existing manifest: {relative_output}")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{output.name}.",
                suffix=".part",
                dir=output.parent,
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                stream.write(
                    json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False)
                    + "\n"
                )
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, output)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return manifest


def verify_manifest(root: Path, relative_manifest: str) -> dict:
    path = safe_repo_path(root, relative_manifest)
    expected = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(expected, dict) or expected.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported or malformed manifest schema")
    if expected.get("manifest_sha256") != manifest_digest(expected):
        raise ValueError("manifest SHA-256 mismatch")
    if not isinstance(expected.get("errors"), list) or expected["errors"]:
        raise ValueError("manifest contains scope errors")

    entries = expected.get("files")
    if not isinstance(entries, list):
        raise ValueError("manifest files must be a list")
    expected_by_path = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("manifest file entry must be an object")
        relative = entry.get("path")
        safe_repo_path(root, relative)
        if relative in expected_by_path:
            raise ValueError(f"duplicate manifest path: {relative}")
        if (
            not isinstance(entry.get("size_bytes"), int)
            or entry["size_bytes"] < 0
            or not isinstance(entry.get("sha256"), str)
            or not SHA256_PATTERN.fullmatch(entry["sha256"])
        ):
            raise ValueError(f"invalid size or SHA-256 for: {relative}")
        expected_by_path[relative] = entry

    actual_entries, errors = collect_entries(root)
    actual_by_path = {entry["path"]: entry for entry in actual_entries}
    added = sorted(set(actual_by_path) - set(expected_by_path))
    missing = sorted(set(expected_by_path) - set(actual_by_path))
    changed = []
    verified = 0
    for relative in sorted(set(actual_by_path) & set(expected_by_path)):
        old = expected_by_path[relative]
        new = actual_by_path[relative]
        if (
            old.get("category") != new["category"]
            or old["size_bytes"] != new["size_bytes"]
            or old["sha256"] != new["sha256"]
        ):
            changed.append(
                {
                    "path": relative,
                    "expected_size_bytes": old.get("size_bytes"),
                    "actual_size_bytes": new["size_bytes"],
                    "expected_sha256": old.get("sha256"),
                    "actual_sha256": new["sha256"],
                }
            )
        else:
            verified += 1
    return {
        "manifest": relative_manifest,
        "manifest_sha256": expected["manifest_sha256"],
        "verified_file_count": verified,
        "added": added,
        "missing": missing,
        "changed": changed,
        "errors": errors,
        "ok": not (added or missing or changed or errors),
    }


def event_digest(event: dict) -> str:
    content = {key: value for key, value in event.items() if key != "event_sha256"}
    return sha256_bytes(canonical_json(content).encode("utf-8"))


def read_last_event(log_path: Path) -> str | None:
    if not log_path.exists():
        return None
    content = log_path.read_bytes()
    if not content:
        return None
    if not content.endswith(b"\n"):
        raise ValueError("fixity event log has an incomplete final line")

    previous = None
    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        try:
            event = json.loads(raw_line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"invalid fixity event at line {line_number}") from error
        if not isinstance(event, dict) or event.get("schema_version") != 1:
            raise ValueError(f"unsupported fixity event at line {line_number}")
        if event.get("previous_event_sha256") != previous:
            raise ValueError(f"broken fixity event chain at line {line_number}")
        digest = event.get("event_sha256")
        if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
            raise ValueError(f"invalid event SHA-256 at line {line_number}")
        if digest != event_digest(event):
            raise ValueError(f"fixity event SHA-256 mismatch at line {line_number}")
        previous = digest
    return previous


@contextmanager
def path_lock(path: Path):
    lock_path = path.with_name(path.name + ".lock")
    if lock_path.is_symlink():
        raise ValueError("file lock must not be a symlink")
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o666)
    with os.fdopen(descriptor, "r+b") as lock:
        if os.name == "nt":
            import msvcrt

            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def append_fixity_event(root: Path, relative_log: str, result: dict) -> dict:
    log_parts = PurePosixPath(relative_log).parts
    if log_parts[:2] != ("preservation", "checks") or len(log_parts) < 3:
        raise ValueError("fixity event log must be under preservation/checks/")
    if PurePosixPath(relative_log).suffix != ".jsonl":
        raise ValueError("fixity event log must use the .jsonl extension")
    log_path = safe_repo_path(root, relative_log)
    if log_path.exists() and not log_path.is_file():
        raise ValueError("fixity event log path is not a regular file")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with path_lock(log_path):
        previous = read_last_event(log_path)
        event = {
            "schema_version": 1,
            "checked_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "manifest": result["manifest"],
            "manifest_sha256": result["manifest_sha256"],
            "ok": result["ok"],
            "verified_file_count": result["verified_file_count"],
            "added": result["added"],
            "missing": result["missing"],
            "changed": result["changed"],
            "errors": result["errors"],
            "previous_event_sha256": previous,
        }
        event["event_sha256"] = event_digest(event)
        with log_path.open("ab") as stream:
            stream.write((canonical_json(event) + "\n").encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
    return event


def verify_event_log(root: Path, relative_log: str) -> dict:
    log_parts = PurePosixPath(relative_log).parts
    if log_parts[:2] != ("preservation", "checks") or len(log_parts) < 3:
        raise ValueError("fixity event log must be under preservation/checks/")
    if PurePosixPath(relative_log).suffix != ".jsonl":
        raise ValueError("fixity event log must use the .jsonl extension")
    log_path = safe_repo_path(root, relative_log)
    if log_path.exists() and not log_path.is_file():
        raise ValueError("fixity event log path is not a regular file")
    last_digest = read_last_event(log_path)
    if log_path.exists():
        with log_path.open("rb") as stream:
            event_count = sum(1 for _ in stream)
    else:
        event_count = 0
    return {
        "event_log": relative_log,
        "event_count": event_count,
        "last_event_sha256": last_digest,
        "ok": True,
    }


def current_manifest(root: Path) -> tuple[str, str]:
    pointer_path = safe_repo_path(root, "preservation/current-baseline.json")
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    if not isinstance(pointer, dict) or pointer.get("schema_version") != 1:
        raise ValueError("unsupported or malformed current-baseline pointer")
    relative = pointer.get("manifest")
    if (
        not isinstance(relative, str)
        or PurePosixPath(relative).parts[:2] != ("preservation", "manifests")
        or len(PurePosixPath(relative).parts) != 3
        or PurePosixPath(relative).suffix != ".json"
        or not BASELINE_NAME_PATTERN.fullmatch(PurePosixPath(relative).name)
    ):
        raise ValueError("current-baseline pointer must name a manifest under preservation/manifests/")
    expected_digest = pointer.get("manifest_sha256")
    if not isinstance(expected_digest, str) or not SHA256_PATTERN.fullmatch(expected_digest):
        raise ValueError("current-baseline pointer has an invalid manifest SHA-256")
    safe_repo_path(root, relative)
    return relative, expected_digest


def select_current_manifest(root: Path, relative_manifest: str) -> dict:
    parts = PurePosixPath(relative_manifest).parts
    if (
        parts[:2] != ("preservation", "manifests")
        or len(parts) != 3
        or not BASELINE_NAME_PATTERN.fullmatch(parts[-1])
    ):
        raise ValueError("selected manifest must be under preservation/manifests/")
    path = safe_repo_path(root, relative_manifest)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported or malformed manifest schema")
    digest = manifest.get("manifest_sha256")
    if not isinstance(digest, str) or digest != manifest_digest(manifest):
        raise ValueError("manifest SHA-256 mismatch")
    if manifest.get("errors") != []:
        raise ValueError("cannot select a manifest with scope errors")
    pointer = {
        "schema_version": 1,
        "manifest": relative_manifest,
        "manifest_sha256": digest,
    }
    pointer_path = safe_repo_path(root, "preservation/current-baseline.json")
    pointer_path.parent.mkdir(parents=True, exist_ok=True)
    with path_lock(pointer_path):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{pointer_path.name}.",
                suffix=".part",
                dir=pointer_path.parent,
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                stream.write(json.dumps(pointer, ensure_ascii=False, indent=2) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, pointer_path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return pointer


def check_current_baseline(root: Path, *, record: bool = True) -> dict:
    try:
        relative_manifest, expected_digest = current_manifest(root)
        result = verify_manifest(root, relative_manifest)
        if result["manifest_sha256"] != expected_digest:
            raise ValueError("current-baseline pointer SHA-256 mismatch")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        result = verification_failure(
            "preservation/current-baseline.json", error
        )
    if record:
        event = append_fixity_event(root, "preservation/checks/fixity.jsonl", result)
        result["event_log"] = "preservation/checks/fixity.jsonl"
        result["event_sha256"] = event["event_sha256"]
    return result


def verification_failure(manifest: str, error: Exception) -> dict:
    return {
        "manifest": manifest,
        "manifest_sha256": None,
        "verified_file_count": 0,
        "added": [],
        "missing": [],
        "changed": [],
        "errors": [{"error": str(error)}],
        "ok": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create", help="create a versioned SHA-256 manifest")
    create.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    create.add_argument("--output", required=True)
    verify = subparsers.add_parser("verify", help="verify files against a manifest")
    verify.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    verify.add_argument("--manifest", required=True)
    verify.add_argument(
        "--record",
        nargs="?",
        const="preservation/checks/fixity.jsonl",
        metavar="LOG_PATH",
        help="append the result to a chained JSONL event log",
    )
    verify_log = subparsers.add_parser(
        "verify-log", help="validate a fixity event chain without appending"
    )
    verify_log.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    verify_log.add_argument(
        "--log", default="preservation/checks/fixity.jsonl"
    )
    check_current = subparsers.add_parser(
        "check-current", help="verify the selected baseline and record the result"
    )
    check_current.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    check_current.add_argument(
        "--read-only", action="store_true",
        help="verify without appending a fixity event, for CI and read-only audits",
    )
    select_current = subparsers.add_parser(
        "select-current", help="select an existing manifest for recurring checks"
    )
    select_current.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    select_current.add_argument("--manifest", required=True)
    args = parser.parse_args(argv)

    try:
        if args.command == "create":
            manifest = write_manifest(args.root.resolve(), args.output)
            print(
                json.dumps(
                    {
                        "manifest": args.output,
                        "manifest_sha256": manifest["manifest_sha256"],
                        **manifest["summary"],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 1 if manifest["errors"] else 0

        if args.command == "verify-log":
            result = verify_event_log(args.root.resolve(), args.log)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        if args.command == "check-current":
            result = check_current_baseline(args.root.resolve(), record=not args.read_only)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["ok"] else 1

        if args.command == "select-current":
            result = select_current_manifest(args.root.resolve(), args.manifest)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        try:
            result = verify_manifest(args.root.resolve(), args.manifest)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            if not args.record:
                raise
            result = verification_failure(args.manifest, error)
            event = append_fixity_event(args.root.resolve(), args.record, result)
            result["event_log"] = args.record
            result["event_sha256"] = event["event_sha256"]
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1
        if args.record:
            event = append_fixity_event(args.root.resolve(), args.record, result)
            result["event_log"] = args.record
            result["event_sha256"] = event["event_sha256"]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
