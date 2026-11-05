"""Deterministic application proofs, independent of later human edits."""

from ..records import json_sha256
from .errors import require
from .manifest import (
    COMMIT,
    RECORD,
    SHA,
    array,
    matches,
    read_bounded,
    shape,
    strict_json,
    validate_source,
)
from .policy import POLICY, TABLES, TARGET


def make_receipt(batch, commit, outcomes):
    value = {
        "receipt_version": 1,
        "batch_id": batch.manifest["batch_id"],
        "manifest_sha256": batch.manifest_sha256,
        "target": TARGET,
        "producer": batch.manifest["producer"],
        "sources": batch.manifest["sources"],
        "applied_base_commit": commit,
        "operations": outcomes,
    }
    value["receipt_sha256"] = json_sha256(value)
    return value


def read_receipt(path):
    value = strict_json(read_bounded(path, 4 * 1024**2))
    shape(
        value,
        (
            "receipt_version",
            "batch_id",
            "manifest_sha256",
            "target",
            "producer",
            "sources",
            "applied_base_commit",
            "operations",
            "receipt_sha256",
        ),
    )
    require(
        type(value["receipt_version"]) is int
        and value["receipt_version"] == 1
        and value["target"] == TARGET,
        "Invalid receipt version/target",
    )
    require(
        matches(value["batch_id"], SHA)
        and path.name == value["batch_id"] + ".json"
        and matches(value["manifest_sha256"], SHA)
        and matches(value["applied_base_commit"], COMMIT),
        "Invalid receipt identity",
    )
    require(
        value["receipt_sha256"]
        == json_sha256({k: v for k, v in value.items() if k != "receipt_sha256"}),
        "Receipt digest mismatch",
    )
    shape(value["producer"], ("name", "code_revision", "run_id"))
    require(
        value["producer"]["name"] in POLICY["allowed_producers"]
        and matches(value["producer"]["code_revision"], COMMIT)
        and matches(value["producer"]["run_id"], r"[A-Za-z0-9][A-Za-z0-9._:-]*", 128),
        "Invalid receipt producer",
    )
    array(value["sources"], 1)
    for source in value["sources"]:
        validate_source(source)
    array(value["operations"], 1)
    keys = set()
    for op in value["operations"]:
        shape(
            op, ("table", "record_id", "op", "before_sha256", "after_sha256", "outcome")
        )
        require(
            op["table"] in TABLES
            and matches(op["record_id"], RECORD)
            and op["op"] in ("insert", "enrich", "attach_audio_distribution")
            and op["outcome"]
            in ("inserted", "enriched", "distribution_attached", "unchanged"),
            "Invalid receipt operation",
        )
        require(
            (op["table"], op["record_id"]) not in keys, "Duplicate receipt operation"
        )
        keys.add((op["table"], op["record_id"]))
        require(
            (op["before_sha256"] is None or matches(op["before_sha256"], SHA))
            and matches(op["after_sha256"], SHA),
            "Invalid receipt record digest",
        )
    return value
