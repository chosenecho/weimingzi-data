"""Isolated projections, bound plans, and fail-closed per-file installation."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import MutableMapping
from contextlib import contextmanager
from pathlib import Path

from ..exports import generate_catalog_docs
from ..records import (
    JSONL_TABLES,
    JSON_RECORD_TABLES,
    iter_records,
    json_sha256,
    read_json,
    validate_corpus,
    write_json,
    write_record_updates,
)
from ..schema_v3 import is_v3
from .errors import IngestError, require
from .manifest import (
    COMMIT,
    SHA,
    inventory,
    matches,
    read_bounded,
    strict_json,
    validate_media,
    verify_batch,
)
from .merge import project, validate_scope
from .policy import TABLES, TARGET, policy_hash
from .receipts import make_receipt, read_receipt

CATALOG = (
    "docs/INDEX.md",
    "docs/counts.json",
    *(
        f"docs/catalog/{name}.md"
        for name in (
            "videos",
            "audio_recordings",
            "posts",
            "articles",
            "people",
            "collections",
            "reviews",
        )
    ),
)


def git(root, *args):
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=False
    )
    require(
        result.returncode == 0,
        "Git precondition failed: " + " ".join(args[:2]),
        "PRECONDITION_FAILED",
        4,
    )
    return result.stdout.decode("utf-8", errors="strict").strip()


def control_path(root, name):
    path = Path(git(root, "rev-parse", "--git-path", "weimingzi-ingest-" + name))
    return path if path.is_absolute() else root / path


def check_checkout(root):
    require(
        Path(git(root, "rev-parse", "--show-toplevel")).resolve() == root.resolve(),
        "Root must be the Git checkout root",
        "PRECONDITION_FAILED",
        4,
    )
    require(
        not control_path(root, "incomplete.json").exists(),
        "Incomplete installation: discard this dedicated checkout and rebuild",
        "WORKTREE_INCOMPLETE",
        4,
    )
    remote = git(root, "remote", "get-url", "origin")
    require(
        remote
        in (
            "https://github.com/chosenecho/weimingzi-data.git",
            "https://github.com/chosenecho/weimingzi-data",
            "git@github.com:chosenecho/weimingzi-data.git",
            "ssh://git@github.com/chosenecho/weimingzi-data.git",
        ),
        "Checkout origin is not the fixed target repository",
        "PRECONDITION_FAILED",
        4,
    )
    require(
        not git(root, "status", "--porcelain=v1", "--untracked-files=all"),
        "Use a clean, dedicated Git checkout for plan/apply",
        "PRECONDITION_FAILED",
        4,
    )
    head = git(root, "rev-parse", "HEAD")
    require(matches(head, COMMIT), "Invalid checkout HEAD", "PRECONDITION_FAILED", 4)
    return head


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot(root):
    files = {}
    for folder in ("data", "selections", "ingest/receipts"):
        base = root / folder
        if base.exists():
            files.update(
                {
                    folder + "/" + p: file_sha256(path)
                    for p, path in inventory(base).items()
                }
            )
    for rel in CATALOG:
        path = root / rel
        # Check ancestors too; never traverse an existing docs junction.
        for ancestor in (root / "docs", path.parent):
            if ancestor.exists():
                require(
                    not ancestor.is_symlink()
                    and not (
                        getattr(ancestor.lstat(), "st_file_attributes", 0) & 0x400
                    ),
                    "Linked catalog directory",
                )
        if path.exists():
            read_bounded(path, 64 * 1024**2)
            files[rel] = file_sha256(path)
    return dict(sorted(files.items()))


def core_hash():
    package = Path(__file__).resolve().parent
    paths = [
        *package.glob("*.py"),
        package.parent / "records.py",
        package.parent / "schema_v3.py",
        package.parent / "exports.py",
        package.parent / "cli.py",
    ]
    return json_sha256(
        {
            p.name if p.parent != package else "ingest/" + p.name: file_sha256(p)
            for p in sorted(paths)
        }
    )


class RecordFiles(MutableMapping):
    """Keep large JSON bodies on disk; only modified records stay in memory."""

    def __init__(self, directory):
        self.paths = {p.stem: p for p in sorted(directory.glob("*.json"))}
        self.changed = {}

    def __getitem__(self, key):
        return self.changed[key] if key in self.changed else read_json(self.paths[key])

    def __setitem__(self, key, value):
        self.changed[key] = value

    def __delitem__(self, key):
        raise TypeError("Ingest cannot delete records")

    def __iter__(self):
        return iter(dict.fromkeys([*self.paths, *self.changed]))

    def __len__(self):
        return len(set(self.paths) | self.changed.keys())


def load_tables(root):
    tables = {}
    native = is_v3(root)
    for table in TABLES:
        if native or table in JSONL_TABLES:
            rows = {}
            for row, _ in iter_records(root, table):
                require(row["id"] not in rows, "Baseline has duplicate JSONL IDs")
                rows[row["id"]] = row
            tables[table] = rows
        else:
            tables[table] = RecordFiles(root / "data" / table)
    return tables


def validate_repository(root):
    """Supplement the existing corpus validator, without re-reading all transcript bodies."""
    root = Path(root).resolve()
    if (root / ".git").exists():
        require(
            not control_path(root, "incomplete.json").exists(),
            "Incomplete installation: discard checkout before publication",
            "WORKTREE_INCOMPLETE",
            4,
        )
    assets = 0
    for table in TABLES:
        if table != "items":
            continue
        for row, _ in iter_records(root, table):
            media = row.get("metadata", {}).get("media_assets", [])
            require(
                isinstance(media, list),
                "media_assets must be an observation array",
                "MEDIA_UNVERIFIED",
            )
            for asset in media:
                validate_media(asset)
                assets += 1
    receipts = 0
    base = root / "ingest/receipts"
    if base.exists():
        for rel, path in inventory(base).items():
            require(
                re.fullmatch(SHA + r"\.json", rel) is not None,
                "Unexpected receipt path",
            )
            read_receipt(path)
            receipts += 1
    return {"receipts": receipts, "media_assets": assets}


def clone_inputs(root, candidate, *, include_receipts=True):
    def link_or_copy(source, dest):
        try:
            os.link(source, dest)
        except OSError:
            shutil.copy2(source, dest)

    for folder in ("data", "selections", *(("ingest/receipts",) if include_receipts else ())):
        if (root / folder).exists():
            shutil.copytree(
                root / folder, candidate / folder, copy_function=link_or_copy
            )
    if not is_v3(candidate):
        for table in JSON_RECORD_TABLES:
            (candidate / "data" / table).mkdir(parents=True, exist_ok=True)


def allowed_change(path, batch_id, *, native=False):
    if native:
        return (
            path in CATALOG
            or path == f"ingest/receipts/{batch_id}.json"
            or path in ("data/items.jsonl", "data/assets.jsonl", "data/annotations.jsonl")
            or re.fullmatch(r"data/documents/[a-z]-[0-9a-f]{24,64}\.json", path)
            is not None
            or re.fullmatch(r"data/artifacts/[0-9a-f]{64}\.(?:md|html)", path)
            is not None
        )
    return (
        path in CATALOG
        or path
        in (
            "data/items.jsonl",
            "data/audio.jsonl",
            "data/collections.jsonl",
            f"ingest/receipts/{batch_id}.json",
        )
        or re.fullmatch(
            r"data/(?:"
            + "|".join(JSON_RECORD_TABLES)
            + r")/[a-z]-[0-9a-f]{24,64}\.json",
            path,
        )
        is not None
    )


@contextmanager
def prepare(root, batch_path):
    root = Path(root).resolve()
    batch = verify_batch(batch_path)
    commit = check_checkout(root)
    validate_corpus(root)
    before = snapshot(root)
    tracked = set(git(root, "ls-files", "-z").rstrip("\0").split("\0"))
    require(
        before.keys() <= tracked,
        "All maintained input files must be Git tracked",
        "PRECONDITION_FAILED",
        4,
    )
    supplements = validate_repository(root)
    manifest = batch.manifest
    proof = root / "ingest/receipts" / (manifest["batch_id"] + ".json")
    report = {
        "plan_version": 1,
        "batch_id": manifest["batch_id"],
        "manifest_sha256": batch.manifest_sha256,
        "target": TARGET,
        "target_commit": commit,
        "producer_base_commit": manifest["base_commit"],
        "policy_sha256": policy_hash(),
        "core_sha256": core_hash(),
        "input_files": before,
        "operations": [],
        "changes": [],
        "conflicts": [],
        "validation": {"valid": True, **supplements},
        "status": "planned",
        "exit_code": 0,
    }
    if proof.exists():
        receipt = read_receipt(proof)
        require(
            receipt["manifest_sha256"] == batch.manifest_sha256,
            "Batch ID has a different accepted manifest",
            "BATCH_ID_COLLISION",
            3,
        )
        report["status"] = "already_accepted"
        report["plan_id"] = json_sha256(report)
        yield report, None
        return
    for dependency in manifest["requires_batches"]:
        require(
            (root / f"ingest/receipts/{dependency}.json").is_file(),
            "Required batch has no tracked receipt on this baseline",
            "DEPENDENCY_PENDING",
            4,
        )
    with tempfile.TemporaryDirectory(prefix="wm-ingest-") as name:
        candidate = Path(name)
        clone_inputs(root, candidate)
        tables = load_tables(candidate)
        report["operations"], report["conflicts"] = project(batch, tables)
        report["exit_code"] = max(
            (c["exit_code"] for c in report["conflicts"]), default=0
        )
        try:
            if not report["conflicts"]:
                # Materialize all changed records before checking cross-table references.
                changed = [
                    r for r in report["operations"] if r["outcome"] != "unchanged"
                ]
                write_record_updates(
                    candidate,
                    {
                        table: [
                            tables[table][outcome["record_id"]]
                            for outcome in changed if outcome["table"] == table
                        ]
                        for table in {r["table"] for r in changed}
                    },
                )
                validate_scope(batch, tables)
                if changed:
                    write_json(
                        candidate
                        / "ingest/receipts"
                        / (manifest["batch_id"] + ".json"),
                        make_receipt(batch, commit, report["operations"]),
                    )
                    report["validation"]["counts"] = generate_catalog_docs(candidate)
                    report["validation"].update(validate_repository(candidate))
                    after = snapshot(candidate)
                    for path, digest in after.items():
                        if before.get(path) != digest:
                            require(
                                allowed_change(path, manifest["batch_id"], native=is_v3(root)),
                                "Candidate changes a protected path",
                            )
                            report["changes"].append(
                                {
                                    "path": path,
                                    "before_sha256": before.get(path),
                                    "after_sha256": digest,
                                }
                            )
                    require(
                        before.keys() <= after.keys(),
                        "Candidate deletes maintained files",
                    )
                else:
                    report["validation"]["counts"] = validate_corpus(candidate)
                    report["status"] = "already_present"
        except (
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            RecursionError,
        ) as error:
            if isinstance(error, IngestError):
                detail, exit_code = error.as_dict(), error.exit_code
            else:
                detail, exit_code = (
                    {"code": "PACKAGE_INTEGRITY_FAILED", "message": str(error)},
                    2,
                )
            report["conflicts"].append(detail)
            report["exit_code"] = exit_code
        if report["conflicts"]:
            report["status"] = "conflict"
            report["validation"]["valid"] = False
            report["changes"] = []
        require(
            check_checkout(root) == commit and snapshot(root) == before,
            "Baseline changed during planning",
            "BASE_MOVED",
            4,
        )
        report["plan_id"] = json_sha256(report)
        yield report, candidate


def report_path(root, path):
    """Reports are local outputs, never a way to overwrite code or batch payloads."""
    root, path = Path(root).resolve(), Path(path).absolute()
    resolved = path.resolve()
    for part in (path, *path.parents):
        if part.exists():
            require(
                not part.is_symlink()
                and not (getattr(part.lstat(), "st_file_attributes", 0) & 0x400),
                "Linked report paths are forbidden",
                "PRECONDITION_FAILED",
                4,
            )
    require(
        not resolved.is_relative_to(root) or resolved.is_relative_to(root / ".cache"),
        "Put reports outside the checkout or under ignored .cache",
        "PRECONDITION_FAILED",
        4,
    )
    if resolved.is_relative_to(root):
        result = subprocess.run(
            ["git", "-C", str(root), "check-ignore", "--quiet", "--", str(resolved)],
            capture_output=True,
        )
        require(
            result.returncode == 0,
            "Report output must be ignored by Git",
            "PRECONDITION_FAILED",
            4,
        )
    return resolved


def write_report(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=".ingest-plan-", dir=path.parent, delete=False
    ) as stream:
        temp = Path(stream.name)
    try:
        write_json(temp, value)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def plan_batch(root, batch_path, report=None):
    output = report_path(root, report) if report is not None else None
    if output:
        require(
            not output.is_relative_to(Path(batch_path).resolve()),
            "Report cannot overwrite the package",
            "PRECONDITION_FAILED",
            4,
        )
    with prepare(root, batch_path) as (result, _):
        if output:
            write_report(output, result)
        return result


def install_file(source, target):
    """Same-filesystem replacement; separate function permits interrupted-write tests."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=".ingest-install-", dir=target.parent, delete=False
    ) as stream:
        temp = Path(stream.name)
    try:
        shutil.copyfile(source, temp)
        with temp.open("r+b") as stream:
            os.fsync(stream.fileno())
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)


def apply_batch(root, batch_path, plan_path):
    root = Path(root).resolve()
    approved = strict_json(read_bounded(Path(plan_path), 16 * 1024**2))
    require(
        isinstance(approved, dict)
        and matches(approved.get("plan_id"), SHA)
        and approved["plan_id"]
        == json_sha256({k: v for k, v in approved.items() if k != "plan_id"})
        and approved.get("status")
        in ("planned", "already_present", "already_accepted"),
        "Invalid or non-applicable plan",
        "PRECONDITION_FAILED",
        4,
    )
    lock, marker = control_path(root, "lock"), control_path(root, "incomplete.json")
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError as error:
        raise IngestError(
            "PRECONDITION_FAILED",
            "Another installation holds the local lock; do not automatically remove it",
            4,
        ) from error
    try:
        with handle:
            handle.write(str(os.getpid()))
            handle.flush()
            os.fsync(handle.fileno())
            with prepare(root, batch_path) as (actual, candidate):
                require(
                    actual["target_commit"] == approved.get("target_commit"),
                    "Plan target HEAD moved",
                    "BASE_MOVED",
                    4,
                )
                require(
                    actual == approved,
                    "Plan inputs, policy, code or projection changed",
                    "PRECONDITION_FAILED",
                    4,
                )
                require(
                    actual["validation"]["valid"],
                    "Candidate validation failed",
                    "PRECONDITION_FAILED",
                    4,
                )
                if not actual["changes"]:
                    return {
                        "status": actual["status"],
                        "batch_id": actual["batch_id"],
                        "plan_id": actual["plan_id"],
                        "changed_files": 0,
                        "witness_commit": actual["target_commit"],
                    }
                write_json(
                    marker,
                    {
                        "batch_id": actual["batch_id"],
                        "plan_id": actual["plan_id"],
                        "target_commit": actual["target_commit"],
                        "changes": actual["changes"],
                    },
                )
                with marker.open("r+b") as stream:
                    os.fsync(stream.fileno())
                for change in actual["changes"]:
                    install_file(candidate / change["path"], root / change["path"])
                expected = dict(actual["input_files"])
                expected.update(
                    {c["path"]: c["after_sha256"] for c in actual["changes"]}
                )
                require(
                    snapshot(root) == dict(sorted(expected.items()))
                    and git(root, "rev-parse", "HEAD") == actual["target_commit"],
                    "Installation readback failed; discard checkout",
                    "WORKTREE_INCOMPLETE",
                    4,
                )
                marker.unlink()
                return {
                    "status": "applied",
                    "batch_id": actual["batch_id"],
                    "plan_id": actual["plan_id"],
                    "changed_files": len(actual["changes"]),
                    "publication_ready": True,
                }
    finally:
        lock.unlink(missing_ok=True)
