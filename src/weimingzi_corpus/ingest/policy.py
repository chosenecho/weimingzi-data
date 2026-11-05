"""Consumer-owned v1 policy. A batch cannot supply or expand these permissions."""

from ..records import json_sha256

TABLES = (
    "items",
    "audio",
    "collections",
    "transcripts",
    "edited_transcripts",
    "posts",
    "articles",
)
TARGET = {"repository": "chosenecho/weimingzi-data", "branch": "main"}
SCOPE = {"platform": "bilibili", "target_uid": "23191782"}
FIELDS = {
    "items": ("metadata", "urls", "relations"),
    "transcripts": ("metadata", "audio_ids"),
    "edited_transcripts": ("metadata",),
    "posts": ("metadata", "article_item_ids"),
    "articles": ("metadata",),
    "audio": ("metadata", "item_ids"),
}
COMMON = ("upstream_run_id", "source_artifact_sha256", "observed_at")
METADATA = {
    "items": (
        *COMMON,
        "title",
        "uploader_name",
        "duration_ms",
        "published_at_unix_seconds",
        "observed_at_unix_seconds",
        "media_assets",
    ),
    "transcripts": (*COMMON, "upstream_transcript_id", "upstream_content_sha256"),
    "edited_transcripts": (*COMMON, "upstream_revision_id"),
    "posts": (*COMMON, "observed_at_unix_seconds"),
    "articles": (*COMMON, "observed_at_unix_seconds"),
    "audio": COMMON,
}
POLICY = {
    "policy_version": 1,
    "target": TARGET,
    "source_scope": SCOPE,
    "allowed_producers": ["weimingzi-bilibili-ingest"],
    "allowed_media_bucket_aliases": ["archive"],
    "limits": {
        "manifest_bytes": 2 * 1024**2,
        "payload_file_bytes": 16 * 1024**2,
        "payload_total_bytes": 64 * 1024**2,
        "operations": 2000,
        "files": 2000,
    },
    "enrich_fields": FIELDS,
    "enrich_metadata": METADATA,
}


def policy_hash():
    return json_sha256(POLICY)
