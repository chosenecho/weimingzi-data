"""Consumer-owned permissions for the single current native ingest protocol."""

from ..records import json_sha256

TARGET = {"repository": "chosenecho/weimingzi-data", "branch": "main"}
SCOPE = {"platform": "bilibili", "target_uid": "23191782"}
COMMON_OBSERVATIONS = ("upstream_run_id", "source_artifact_sha256", "observed_at")
OBSERVATIONS = {
    "items": (*COMMON_OBSERVATIONS, "title", "uploader_name", "uploader_id", "cid",
              "duration_ms", "published_at_unix_seconds", "observed_at_unix_seconds", "media_assets"),
    "documents": (*COMMON_OBSERVATIONS, "upstream_transcript_id", "upstream_content_sha256",
                  "upstream_revision_id", "observed_at_unix_seconds"),
    "assets": COMMON_OBSERVATIONS,
}
POLICY = {
    "policy_version": 2,
    "contract_version": 2,
    "record_schema_version": 3,
    "target": TARGET,
    "source_scope": SCOPE,
    "allowed_producers": ["weimingzi-bilibili-ingest"],
    # Producer provenance establishes automatic collection, never human authority.
    "insert_kinds": {
        "items": ["video", "video_part", "post", "article", "video_collection"],
        "documents": ["transcript", "edited_transcript", "post", "article"],
        "assets": ["audio", "archive"],
        "annotations": [],
    },
    "append_fields": {"items": ["urls", "relations", "members"], "documents": [], "assets": ["downloads"]},
    "observation_fields": OBSERVATIONS,
    "allowed_media_bucket_aliases": ["archive"],
    "limits": {
        "manifest_bytes": 2 * 1024**2,
        "payload_file_bytes": 16 * 1024**2,
        "payload_total_bytes": 64 * 1024**2,
        "operations": 2000,
        "files": 2000,
    },
}


def policy_hash():
    return json_sha256(POLICY)
