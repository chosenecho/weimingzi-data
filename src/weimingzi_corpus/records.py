"""Canonical records, references and lossless subtitle validation. Standard library only."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath

JSONL_TABLES = ("items", "collections", "audio", "confirmations", "attributions")
JSON_RECORD_TABLES = ("transcripts", "edited_transcripts", "posts", "articles")
RECORD_ID_PATTERN = re.compile(r"^[a-z]-[0-9a-f]{24,64}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ATTRIBUTION_ID_PREFIX = "s"
ATTRIBUTION_SPEAKER_ROLES = ("primary_speaker", "other_speaker", "unknown")
ATTRIBUTION_VIEWPOINTS = (
    "own_view",
    "quoted_or_read_aloud",
    "explained_or_paraphrased",
    "unknown",
)
ATTRIBUTION_STATUS = "human_confirmed"
ATTRIBUTION_REVIEW_TIMEZONE = "Asia/Hong_Kong"
ATTRIBUTION_KEYS = {
    "schema_version",
    "kind",
    "id",
    "item_id",
    "edited_transcript_id",
    "anchor",
    "speaker_role",
    "viewpoint",
    "review",
    "status",
    "urls",
}
ATTRIBUTION_ANCHOR_KEYS = {
    "paragraph_index",
    "paragraph_text_sha256",
    "excerpt",
    "start",
    "end",
    "time_unit",
}
ATTRIBUTION_REQUIRED_REVIEW_KEYS = {
    "basis",
    "reviewer_label",
    "reviewed_on",
    "review_timezone",
    "reviewer_reported_watched_original_video",
    "assistant_listened_to_audio",
}
ATTRIBUTION_OPTIONAL_REVIEW_KEYS = {"source_url"}


def canonical_json(value) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def json_sha256(value) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def make_record_id(prefix: str, value) -> str:
    return prefix + "-" + json_sha256(value)[:24]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path):
    with path.open(encoding="utf-8-sig") as stream:
        for number, line in enumerate(stream, 1):
            if line.strip():
                try:
                    yield json.loads(line)
                except (ValueError, TypeError) as error:
                    raise ValueError(f"{path}:{number}: {error}") from error


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for record in sorted(rows, key=lambda r: r["id"]):
            stream.write(canonical_json(record) + "\n")


def validate_relative_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or ":" in value or "\\" in value:
        raise ValueError(f"Unsafe relative path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"Unsafe relative path: {value!r}")
    return path


def resolve_repository_path(root: Path, value: str) -> Path:
    path = (root / Path(*validate_relative_path(value).parts)).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Path escapes root: {value}")
    return path


def iter_records(root: Path, table: str):
    from .schema_v3 import is_v3, iter_legacy_records

    if is_v3(root):
        yield from iter_legacy_records(root, table)
        return
    if table in JSONL_TABLES:
        for record in read_jsonl(root / "data" / (table + ".jsonl")):
            yield record, root / "data" / (table + ".jsonl")
    elif table in JSON_RECORD_TABLES:
        for path in sorted((root / "data" / table).glob("*.json")):
            yield read_json(path), path
    else:
        raise ValueError(f"Unknown table: {table}")


def content_record_path(root: Path, table: str, record_id: str) -> Path:
    """Locate maintained content without exposing a storage version to callers."""
    from .schema_v3 import is_v3

    if table not in JSON_RECORD_TABLES:
        raise ValueError(f"Unknown content table: {table}")
    directory = "documents" if is_v3(root) else table
    return resolve_repository_path(root, f"data/{directory}/{record_id}.json")


def load_content_record(root: Path, record_id: str) -> dict:
    """Read one content record as a lossless legacy semantic view."""
    from .schema_v3 import is_v3, load_legacy_record

    if is_v3(root):
        path = content_record_path(root, JSON_RECORD_TABLES[0], record_id)
        if path.is_file():
            return load_legacy_record(root, record_id)
        raise ValueError("Unknown content record: " + record_id)
    for table in JSON_RECORD_TABLES:
        path = content_record_path(root, table, record_id)
        if path.is_file():
            return read_json(path)
    raise ValueError("Unknown content record: " + record_id)


def write_record_updates(root: Path, updates: dict) -> list[Path]:
    """Upsert legacy-shaped records through the versioned storage seam.

    Callers build an isolated candidate first. Every replacement detaches hard links;
    returned paths are relative to root and are the complete installation file set.
    """
    from .schema_v3 import is_v3, write_legacy_updates

    unknown = set(updates) - set((*JSONL_TABLES, *JSON_RECORD_TABLES))
    if unknown:
        raise ValueError(f"Unknown tables: {sorted(unknown)}")
    if is_v3(root):
        return write_legacy_updates(root, updates)
    changed = []
    for table, incoming in updates.items():
        rows = list(incoming)
        if not rows:
            continue
        if table in JSONL_TABLES:
            existing = {row["id"]: row for row, _ in iter_records(root, table)}
            existing.update({row["id"]: row for row in rows})
            targets = [(Path("data") / (table + ".jsonl"), existing.values())]
        else:
            targets = [
                (Path("data") / table / (row["id"] + ".json"), row)
                for row in rows
            ]
        for relative, value in targets:
            destination = resolve_repository_path(root, relative.as_posix())
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
                temporary = Path(stream.name)
            try:
                if table in JSONL_TABLES:
                    write_jsonl(temporary, value)
                else:
                    write_json(temporary, value)
                if not destination.exists() or temporary.read_bytes() != destination.read_bytes():
                    os.replace(temporary, destination)
                    changed.append(relative)
            finally:
                temporary.unlink(missing_ok=True)
    return sorted(changed)


def install_candidate_updates(root: Path, candidate: Path, paths) -> None:
    """Install an allowed candidate delta, including deletions, with file rollback.

    Only the supplied changed paths participate. A missing candidate file means
    deletion; validate both endpoints and back up every original before mutation.
    """
    relative_paths = sorted({Path(path) for path in paths})
    updates = [
        (
            relative,
            resolve_repository_path(root, relative.as_posix()),
            resolve_repository_path(candidate, relative.as_posix()),
        )
        for relative in relative_paths
    ]
    with tempfile.TemporaryDirectory(prefix="rollback-", dir=candidate) as name:
        backup = Path(name)
        installed = []
        for relative, target, _ in updates:
            if target.exists():
                saved = backup / relative
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved)
        try:
            for relative, target, source in updates:
                if source.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(source, target)
                else:
                    target.unlink(missing_ok=True)
                installed.append((relative, target))
        except OSError:
            for relative, target in reversed(installed):
                saved = backup / relative
                if saved.exists():
                    os.replace(saved, target)
                else:
                    target.unlink(missing_ok=True)
            raise


def find_timestamp_issues(record: dict) -> list[str]:
    issues = []
    previous = None
    for number, segment in enumerate(record.get("segments", [])):
        try:
            start, end = Decimal(str(segment["start"])), Decimal(str(segment["end"]))
            if not start.is_finite() or not end.is_finite():
                raise InvalidOperation
        except (KeyError, InvalidOperation, ValueError):
            issues.append(f"segment {number}: invalid timestamp")
            continue
        if start < 0 or end <= start:
            issues.append(f"segment {number}: expected 0 <= start < end")
        if previous is not None and start < previous:
            issues.append(f"segment {number}: starts must not decrease")
        previous = start
    return issues


def transcript_hash_input(record: dict) -> dict:
    return {
        key: record[key]
        for key in (
            "item_id",
            "method",
            "language",
            "model",
            "time_unit",
            "text",
            "segments",
        )
    }


def validate_quality_flags(record: dict) -> None:
    flags = record.get("quality")
    if not isinstance(flags, dict):
        raise ValueError(f"{record['id']}: quality must be an object")
    for name in (
        "is_fully_human_reviewed",
        "requires_review",
        "is_subtitle_export_enabled",
    ):
        if flags.get(name) is not None and not isinstance(flags[name], bool):
            raise ValueError(f"{record['id']}: {name} must be boolean or null")


def validate_recognition_issues(value, record_id: str) -> None:
    """Validate explicit seconds without conflating timestamp errors and missing text."""
    if isinstance(value, list):
        for nested in value:
            validate_recognition_issues(nested, record_id)
    elif isinstance(value, dict):
        for key, nested in value.items():
            if key == "recognition_issue_intervals":
                pending = list(nested) if isinstance(nested, list) else [nested]
                while pending:
                    interval = pending.pop()
                    if isinstance(interval, list):
                        pending.extend(interval)
                        continue
                    if not isinstance(interval, dict):
                        raise ValueError(
                            f"{record_id}: expected recognition issue object"
                        )
                    start = interval.get("start_seconds")
                    end = interval.get("end_seconds")
                    if (
                        isinstance(start, bool)
                        or isinstance(end, bool)
                        or not isinstance(start, (int, float))
                        or not isinstance(end, (int, float))
                        or not Decimal(str(start)).is_finite()
                        or not Decimal(str(end)).is_finite()
                        or not 0 <= start < end
                    ):
                        raise ValueError(
                            f"{record_id}: recognition issue requires explicit seconds"
                        )
            validate_recognition_issues(nested, record_id)


def validate_attribution_shape(row: dict) -> None:
    """Check a segment attribution record on its own; links are checked later."""
    record_id = row["id"]
    if not record_id.startswith(ATTRIBUTION_ID_PREFIX + "-"):
        raise ValueError(
            f"{record_id}: attribution id must use prefix {ATTRIBUTION_ID_PREFIX}-"
        )
    unknown_keys = set(row) - ATTRIBUTION_KEYS
    missing_keys = ATTRIBUTION_KEYS - set(row)
    if unknown_keys or missing_keys:
        raise ValueError(
            f"{record_id}: attribution keys unknown={sorted(unknown_keys)} missing={sorted(missing_keys)}"
        )
    for name in ("item_id", "edited_transcript_id"):
        if not isinstance(row[name], str) or not RECORD_ID_PATTERN.fullmatch(row[name]):
            raise ValueError(f"{record_id}: invalid {name}")
    anchor = row["anchor"]
    if not isinstance(anchor, dict) or set(anchor) != ATTRIBUTION_ANCHOR_KEYS:
        raise ValueError(
            f"{record_id}: attribution anchor requires exactly {sorted(ATTRIBUTION_ANCHOR_KEYS)}"
        )
    if type(anchor["paragraph_index"]) is not int or anchor["paragraph_index"] < 0:
        raise ValueError(f"{record_id}: invalid paragraph_index")
    if not isinstance(
        anchor["paragraph_text_sha256"], str
    ) or not SHA256_PATTERN.fullmatch(anchor["paragraph_text_sha256"]):
        raise ValueError(f"{record_id}: invalid paragraph_text_sha256")
    if anchor["excerpt"] is not None and (
        not isinstance(anchor["excerpt"], str) or not anchor["excerpt"]
    ):
        raise ValueError(f"{record_id}: excerpt must be non-empty text or null")
    if row["speaker_role"] not in ATTRIBUTION_SPEAKER_ROLES:
        raise ValueError(f"{record_id}: invalid speaker_role {row['speaker_role']!r}")
    if row["viewpoint"] not in ATTRIBUTION_VIEWPOINTS:
        raise ValueError(f"{record_id}: invalid viewpoint {row['viewpoint']!r}")
    if row["status"] != ATTRIBUTION_STATUS:
        raise ValueError(
            f"{record_id}: attribution status must be {ATTRIBUTION_STATUS}"
        )
    review = row["review"]
    if not isinstance(review, dict):
        raise ValueError(f"{record_id}: review must be an object")
    unknown_keys = set(review) - (
        ATTRIBUTION_REQUIRED_REVIEW_KEYS | ATTRIBUTION_OPTIONAL_REVIEW_KEYS
    )
    missing_keys = ATTRIBUTION_REQUIRED_REVIEW_KEYS - set(review)
    if unknown_keys or missing_keys:
        raise ValueError(
            f"{record_id}: review keys unknown={sorted(unknown_keys)} missing={sorted(missing_keys)}"
        )
    for name in ("basis", "reviewer_label"):
        if not isinstance(review[name], str) or not review[name].strip():
            raise ValueError(f"{record_id}: review {name} must be non-empty text")
    reviewed_on = review["reviewed_on"]
    try:
        if not isinstance(reviewed_on, str) or not ISO_DATE_PATTERN.fullmatch(
            reviewed_on
        ):
            raise ValueError
        date.fromisoformat(reviewed_on)
    except ValueError:
        raise ValueError(f"{record_id}: reviewed_on must be YYYY-MM-DD") from None
    if review["review_timezone"] != ATTRIBUTION_REVIEW_TIMEZONE:
        raise ValueError(
            f"{record_id}: review_timezone must be {ATTRIBUTION_REVIEW_TIMEZONE}"
        )
    for name in (
        "reviewer_reported_watched_original_video",
        "assistant_listened_to_audio",
    ):
        if not isinstance(review[name], bool):
            raise ValueError(f"{record_id}: review {name} must be boolean")
    if "source_url" in review and (
        not isinstance(review["source_url"], str)
        or not review["source_url"].startswith("https://")
    ):
        raise ValueError(f"{record_id}: review source_url must use HTTPS")
    if not isinstance(row["urls"], list) or not all(
        isinstance(url, str) and url.startswith("https://") for url in row["urls"]
    ):
        raise ValueError(f"{record_id}: urls must be HTTPS text")


def validate_attribution_anchor(row: dict, edited_transcript: dict) -> None:
    """Require the anchor to describe the current paragraph, so text edits invalidate it."""
    record_id, anchor = row["id"], row["anchor"]
    if edited_transcript["item_id"] != row["item_id"]:
        raise ValueError(
            f"{record_id}: attribution edited transcript belongs to a different item"
        )
    paragraphs = edited_transcript["paragraphs"]
    if anchor["paragraph_index"] >= len(paragraphs):
        raise ValueError(f"{record_id}: paragraph_index out of range")
    paragraph = paragraphs[anchor["paragraph_index"]]
    text = paragraph.get("text", "")
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != anchor[
        "paragraph_text_sha256"
    ]:
        raise ValueError(f"{record_id}: attribution paragraph text hash mismatch")
    if anchor["excerpt"] is not None and anchor["excerpt"] not in text:
        raise ValueError(f"{record_id}: attribution excerpt not found in paragraph")
    expected_position = (
        paragraph.get("start"),
        paragraph.get("end"),
        edited_transcript.get("time_unit"),
    )
    if (anchor["start"], anchor["end"], anchor["time_unit"]) != expected_position:
        raise ValueError(
            f"{record_id}: attribution start/end/time_unit differ from the paragraph"
        )


def validate_corpus(root: Path) -> dict:
    """Check native structure first, then all historical semantic invariants."""
    from .schema_v3 import is_v3, validate_native

    native = is_v3(root)
    if native:
        errors = validate_native(root)
        if errors:
            raise ValueError("Invalid schema v3 corpus: " + "; ".join(errors))
    counts, all_ids, items, contents, audio = (
        Counter({table: 0 for table in (*JSONL_TABLES, *JSON_RECORD_TABLES)}),
        {},
        {},
        {},
        {},
    )
    references = []
    (
        confirmations,
        edited_transcript_anchors,
        edited_transcript_parents,
        unit_references,
    ) = {}, {}, {}, {}
    recognition_chunks_by_transcript, evidence_references = {}, []
    attributions, attributions_by_edited_transcript = {}, {}
    attribution_anchor_keys = set()
    restore_paths, archive_members, archives = set(), set(), {}
    hashes = set()
    invalid_timing = 0
    for table in (*JSONL_TABLES, *JSON_RECORD_TABLES):
        for row, path in iter_records(root, table):
            record_id = row.get("id")
            if not isinstance(record_id, str) or not RECORD_ID_PATTERN.fullmatch(
                record_id
            ):
                raise ValueError(f"{path}: invalid id {record_id!r}")
            if row.get("schema_version") != 2 or row.get("kind") is None:
                raise ValueError(f"{path}: expected schema_version=2 and kind")
            kinds = {
                "items": {
                    "video",
                    "video_part",
                    "audio_recording",
                    "post",
                    "article",
                    "person",
                },
                "collections": {
                    "article_collection",
                    "video_collection",
                    "video_series",
                },
                "audio": {"audio"},
                "confirmations": {"confirmation"},
                "attributions": {"segment_attribution"},
                "transcripts": {"transcript"},
                "edited_transcripts": {"edited_transcript"},
                "posts": {"post"},
                "articles": {"article"},
            }
            if row["kind"] not in kinds[table]:
                raise ValueError(f"{record_id}: unexpected kind for {table}")
            if record_id in all_ids:
                raise ValueError(f"Duplicate id {record_id}")
            if table in JSON_RECORD_TABLES and path.stem != record_id:
                raise ValueError(f"{path}: filename must equal id")
            all_ids[record_id] = table
            counts[table] += 1

            def collect_evidence(value):
                if isinstance(value, dict):
                    if "transcript_id" in value and "recognition_chunk_ids" in value:
                        evidence_references.append(
                            (record_id, row.get("item_id"), value)
                        )
                    for nested in value.values():
                        collect_evidence(nested)
                elif isinstance(value, list):
                    for nested in value:
                        collect_evidence(nested)

            collect_evidence(row.get("quality"))
            collect_evidence(row.get("metadata"))
            validate_recognition_issues(row.get("quality"), record_id)
            validate_recognition_issues(row.get("metadata"), record_id)
            if table in ("transcripts", "edited_transcripts"):
                model = row.get("model")
                if model is not None and (
                    not isinstance(model, dict)
                    or not isinstance(model.get("name"), str)
                ):
                    raise ValueError(
                        f"{record_id}: model must be an object with name or null"
                    )
            if table == "items":
                if not isinstance(row.get("title"), str) or not isinstance(
                    row.get("identifiers"), dict
                ):
                    raise ValueError(f"{record_id}: expected title and identifiers")
                items[record_id] = row
                if row.get("parent_id"):
                    references.append((record_id, "items", row["parent_id"]))
                for relation in row.get("relations", []):
                    references.append((record_id, "items", relation["target_item_id"]))
            elif table == "collections":
                if not isinstance(row.get("members"), list):
                    raise ValueError(f"{record_id}: expected ordered members")
                counts["collection_members"] += len(row["members"])
                for member in row["members"]:
                    references.append((record_id, "items", member["item_id"]))
            elif table == "audio":
                if not isinstance(
                    row.get("sha256"), str
                ) or not SHA256_PATTERN.fullmatch(row["sha256"]):
                    raise ValueError(f"{record_id}: invalid audio SHA-256")
                if row["sha256"] in hashes:
                    raise ValueError(f"Duplicate audio SHA-256: {row['sha256']}")
                hashes.add(row["sha256"])
                audio[record_id] = row
                for item in row.get("item_ids", []):
                    references.append((record_id, "items", item))
                if row.get("availability") == "available":
                    validate_relative_path(row["local_path"])
                    downloads = row.get("downloads", [])
                    if row["local_path"] in restore_paths:
                        raise ValueError(f"{record_id}: duplicate audio restore path")
                    restore_paths.add(row["local_path"])
                    if (
                        not downloads
                        or not isinstance(row.get("size_bytes"), int)
                        or row["size_bytes"] < 0
                    ):
                        raise ValueError(f"{record_id}: incomplete Release locator")
                    for location in downloads:
                        validate_relative_path(location["member_path"])
                        validate_relative_path(location["archive"]["name"])
                        validate_relative_path(location["release_tag"])
                        archive = location["archive"]
                        key = (location["release_tag"], archive["name"])
                        if key in archives and archives[key] != archive:
                            raise ValueError(
                                f"{record_id}: conflicting archive metadata"
                            )
                        archives[key] = archive
                        member = (*key, location["member_path"])
                        if member in archive_members:
                            raise ValueError(f"{record_id}: duplicate archive member")
                        archive_members.add(member)
                        if not SHA256_PATTERN.fullmatch(
                            archive["sha256"]
                        ) or not isinstance(archive["size_bytes"], int):
                            raise ValueError(
                                f"{record_id}: invalid archive digest/size"
                            )
                        if not archive["url"].startswith("https://"):
                            raise ValueError(f"{record_id}: archive URL must use HTTPS")
                    counts["restorable_audio"] += 1
                    counts["audio_bytes"] += row["size_bytes"]
                else:
                    if row.get("availability") != "unavailable":
                        raise ValueError(f"{record_id}: invalid availability")
                    counts["unavailable_audio"] += 1
            elif table in JSON_RECORD_TABLES:
                references.append((record_id, "items", row["item_id"]))
                contents[record_id] = {"item_id": row["item_id"], "table": table}
                if table in ("transcripts", "edited_transcripts", "articles"):
                    if not isinstance(row.get("text"), str):
                        raise ValueError(f"{record_id}: expected text")
                    validate_quality_flags(row)
                if table == "transcripts":
                    if row.get("time_unit") not in ("ms", "s") or not isinstance(
                        row.get("segments"), list
                    ):
                        raise ValueError(f"{record_id}: invalid segments/time unit")
                    for index, segment in enumerate(row["segments"]):
                        if (
                            not isinstance(segment.get("text"), str)
                            or segment.get("index") != index
                        ):
                            raise ValueError(
                                f"{record_id}: segment index/text mismatch at {index}"
                            )
                    if json_sha256(transcript_hash_input(row)) != row.get(
                        "content_sha256"
                    ):
                        raise ValueError(
                            f"{record_id}: transcript content SHA-256 mismatch"
                        )
                    if "recognition_chunks" in row:
                        if not isinstance(
                            row["recognition_chunks"], list
                        ) or json_sha256(row["recognition_chunks"]) != row.get(
                            "recognition_chunks_sha256"
                        ):
                            raise ValueError(
                                f"{record_id}: recognition chunk SHA-256 mismatch"
                            )
                        recognition_chunk_ids = [
                            a["id"] for a in row["recognition_chunks"]
                        ]
                        if len(set(recognition_chunk_ids)) != len(
                            recognition_chunk_ids
                        ):
                            raise ValueError(
                                f"{record_id}: duplicate recognition chunk id"
                            )
                        for recognition_chunk in row["recognition_chunks"]:
                            if recognition_chunk.get(
                                "time_unit"
                            ) != "ms" or not isinstance(
                                recognition_chunk.get("sentences"), list
                            ):
                                raise ValueError(
                                    f"{record_id}: invalid recognition chunk"
                                )
                    recognition_chunks_by_transcript[record_id] = {
                        a["id"] for a in row.get("recognition_chunks", [])
                    }
                    issues = find_timestamp_issues(row)
                    if issues != row["quality"].get("timing_issues", []):
                        raise ValueError(
                            f"{record_id}: timing issue list does not describe stored values"
                        )
                    invalid_timing += bool(issues)
                    counts["segments"] += len(row["segments"])
                if table == "edited_transcripts":
                    if not isinstance(row.get("paragraphs"), list):
                        raise ValueError(f"{record_id}: expected paragraphs")
                    if row.get("time_unit") not in ("ms", "s", None):
                        raise ValueError(f"{record_id}: invalid paragraph time unit")
                    if not isinstance(row.get("is_complete"), bool):
                        raise ValueError(f"{record_id}: is_complete must be boolean")
                    counts["paragraphs"] += len(row["paragraphs"])
                    record_issues = 0
                    for index, paragraph in enumerate(row["paragraphs"]):
                        if (
                            type(paragraph.get("index")) is not int
                            or paragraph["index"] != index
                        ):
                            raise ValueError(f"{record_id}: paragraph index mismatch")
                        issues = paragraph.get("issues", [])
                        if not isinstance(issues, list):
                            raise ValueError(f"{record_id}: issues must be an array")
                        for issue in issues:
                            if not isinstance(issue, dict) or not isinstance(
                                issue.get("note"), str
                            ):
                                raise ValueError(f"{record_id}: issue requires a note")
                            if "candidate" in issue and not isinstance(
                                issue["candidate"], str
                            ):
                                raise ValueError(f"{record_id}: candidate must be text")
                            if "evidence_labels" in issue and (
                                not isinstance(issue["evidence_labels"], list)
                                or not all(
                                    isinstance(label, str)
                                    for label in issue["evidence_labels"]
                                )
                            ):
                                raise ValueError(
                                    f"{record_id}: evidence_labels must be text labels"
                                )
                        record_issues += len(issues)
                        counts["paragraphs_with_review_issues"] += bool(issues)
                    counts["review_issues"] += record_issues
                    counts["edited_transcripts_with_review_issues"] += bool(
                        record_issues
                    )
                    counts["edited_transcripts_with_notes"] += bool(
                        row.get("notes_markdown")
                    )
                    counts["edited_transcripts_with_review_documents"] += bool(
                        row.get("review_document_markdown")
                    )
                    for ref in row.get("transcript_ids", []):
                        references.append((record_id, "transcripts", ref))
                    for ref in row.get("confirmation_ids", []):
                        references.append((record_id, "confirmations", ref))
                        confirmation = confirmations.get(ref)
                        if confirmation is not None and (
                            confirmation["item_id"] != row["item_id"]
                            or record_id not in confirmation["edited_transcript_ids"]
                        ):
                            raise ValueError(
                                f"{record_id}: confirmation {ref} does not apply to this edited transcript"
                            )
                    if row.get("derived_from_id"):
                        references.append(
                            (record_id, "edited_transcripts", row["derived_from_id"])
                        )
                        edited_transcript_parents[record_id] = row["derived_from_id"]
                    if row.get("input_units_from_id"):
                        references.append(
                            (
                                record_id,
                                "edited_transcripts",
                                row["input_units_from_id"],
                            )
                        )
                        unit_references[record_id] = row["input_units_from_id"]
                    edited_transcript_anchors[record_id] = set()
                    for attribution in attributions_by_edited_transcript.get(
                        record_id, []
                    ):
                        validate_attribution_anchor(attribution, row)
                    for confirmation in confirmations.values():
                        if confirmation["item_id"] == row["item_id"]:
                            anchor = confirmation["anchor"]["original_text"]
                            corrected = confirmation["corrected_text"]
                            if (
                                (anchor and anchor in row["text"])
                                or (corrected and corrected in row["text"])
                                or any(
                                    (anchor and anchor in p.get("text", ""))
                                    or (corrected and corrected in p.get("text", ""))
                                    for p in row["paragraphs"]
                                )
                            ):
                                edited_transcript_anchors[record_id].add(
                                    confirmation["id"]
                                )
                    if not row.get("is_complete", True):
                        counts["incomplete_edited_transcripts"] += 1
                for ref in row.get("audio_ids", []):
                    references.append((record_id, "audio", ref))
                if table == "posts":
                    if not isinstance(row.get("content"), dict):
                        raise ValueError(f"{record_id}: expected rich post content")
                    for article in row.get("article_item_ids", []):
                        references.append((record_id, "items", article))
            elif table == "confirmations":
                confirmations[record_id] = row
                if not row.get("edited_transcript_ids"):
                    raise ValueError(
                        f"{record_id}: confirmation has no edited transcript anchor"
                    )
                references.append((record_id, "items", row["item_id"]))
                for edited_transcript in row.get("edited_transcript_ids", []):
                    references.append(
                        (record_id, "edited_transcripts", edited_transcript)
                    )
                anchor = row["anchor"]
                if (
                    hashlib.sha256(anchor["original_text"].encode("utf-8")).hexdigest()
                    != anchor["original_text_sha256"]
                ):
                    raise ValueError(f"{record_id}: confirmation anchor hash mismatch")
                if (
                    hashlib.sha256(row["corrected_text"].encode("utf-8")).hexdigest()
                    != row["corrected_text_sha256"]
                ):
                    raise ValueError(f"{record_id}: corrected text hash mismatch")
            elif table == "attributions":
                validate_attribution_shape(row)
                attributions[record_id] = row
                anchor_key = (
                    row["edited_transcript_id"],
                    row["anchor"]["paragraph_index"],
                    row["anchor"]["excerpt"],
                )
                if anchor_key in attribution_anchor_keys:
                    raise ValueError(
                        f"{record_id}: duplicate attribution for the same paragraph range"
                    )
                attribution_anchor_keys.add(anchor_key)
                attributions_by_edited_transcript.setdefault(
                    row["edited_transcript_id"], []
                ).append(row)
                references.append((record_id, "items", row["item_id"]))
                references.append(
                    (record_id, "edited_transcripts", row["edited_transcript_id"])
                )
                counts["attributions_primary_speaker_own_view"] += (
                    row["speaker_role"] == "primary_speaker"
                    and row["viewpoint"] == "own_view"
                )
    for record_id, table, target in references:
        if all_ids.get(target) != table:
            raise ValueError(f"{record_id}: unresolved {table} reference {target}")
    for record_id, item, evidence in evidence_references:
        target = evidence["transcript_id"]
        if all_ids.get(target) != "transcripts" or contents[target]["item_id"] != item:
            raise ValueError(f"{record_id}: unresolved transcript evidence {target}")
        if (
            not evidence["recognition_chunk_ids"]
            or not set(evidence["recognition_chunk_ids"])
            <= recognition_chunks_by_transcript[target]
        ):
            raise ValueError(f"{record_id}: unresolved recognition chunk evidence")
    for record_id, parent in {**edited_transcript_parents, **unit_references}.items():
        if contents[record_id]["item_id"] != contents[parent]["item_id"]:
            raise ValueError(
                f"{record_id}: edited transcript parent belongs to a different item"
            )
    for record_id in edited_transcript_parents:
        seen, current = {record_id}, edited_transcript_parents[record_id]
        while current in edited_transcript_parents:
            if current in seen:
                raise ValueError(f"{record_id}: edited transcript parent cycle")
            seen.add(current)
            current = edited_transcript_parents[current]
    for record_id, confirmation in confirmations.items():
        for edited_transcript in confirmation["edited_transcript_ids"]:
            if contents[edited_transcript]["item_id"] != confirmation["item_id"]:
                raise ValueError(
                    f"{record_id}: confirmation target belongs to a different item"
                )
            if record_id not in edited_transcript_anchors.get(edited_transcript, set()):
                raise ValueError(
                    f"{record_id}: confirmation text cannot be located in edited transcript {edited_transcript}"
                )
    for record_id, row in items.items():
        counts["items_" + row["kind"]] += 1
        if row.get("parent_id"):
            seen = {record_id}
            current = row["parent_id"]
            while current:
                if current in seen:
                    raise ValueError(f"{record_id}: parent cycle")
                seen.add(current)
                current = items[current].get("parent_id")
    counts["timing_issue_transcripts"] = invalid_timing
    for name in (
        "attributions_primary_speaker_own_view",
        "review_issues",
        "paragraphs_with_review_issues",
        "edited_transcripts_with_review_issues",
        "edited_transcripts_with_notes",
        "edited_transcripts_with_review_documents",
    ):
        counts.setdefault(name, 0)
    return dict(sorted(counts.items()))
