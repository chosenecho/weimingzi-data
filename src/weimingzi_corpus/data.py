"""Canonical records, references and lossless subtitle validation. Standard library only."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath

TABLES = ("items", "collections", "media", "annotations")
DIRECTORIES = ("transcripts", "readings", "dynamics", "articles")
ID = re.compile(r"^[a-z]-[0-9a-f]{24,64}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def canonical(value) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def fingerprint(value) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def identifier(prefix: str, value) -> str:
    return prefix + "-" + fingerprint(value)[:24]


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


def write_jsonl(path: Path, records) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for record in sorted(records, key=lambda r: r["id"]):
            stream.write(canonical(record) + "\n")


def relative_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or ":" in value or "\\" in value:
        raise ValueError(f"Unsafe relative path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"Unsafe relative path: {value!r}")
    return path


def safe_target(root: Path, value: str) -> Path:
    path = (root / Path(*relative_path(value).parts)).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Path escapes root: {value}")
    return path


def records(root: Path, table: str):
    if table in TABLES:
        for record in read_jsonl(root / "data" / (table + ".jsonl")):
            yield record, root / "data" / (table + ".jsonl")
    elif table in DIRECTORIES:
        for path in sorted((root / "data" / table).glob("*.json")):
            yield read_json(path), path
    else:
        raise ValueError(f"Unknown table: {table}")


def timing_issues(record: dict) -> list[str]:
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


def transcript_identity(record: dict) -> dict:
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


def quality(record: dict) -> None:
    flags = record.get("quality")
    if not isinstance(flags, dict):
        raise ValueError(f"{record['id']}: quality must be an object")
    for name in ("human_reviewed", "requires_review", "timed_exports_available"):
        if flags.get(name) is not None and not isinstance(flags[name], bool):
            raise ValueError(f"{record['id']}: {name} must be boolean or null")


def validate(root: Path) -> dict:
    """Check identity, types, coverage of exceptional timestamps, and every internal link."""
    counts, all_ids, items, contents, media = (
        Counter({table: 0 for table in (*TABLES, *DIRECTORIES)}),
        {},
        {},
        {},
        {},
    )
    references = []
    annotations, reading_anchors, reading_parents, unit_references = {}, {}, {}, {}
    alignments_by_transcript, evidence_references = {}, []
    restore_paths, archive_members, archives = set(), set(), {}
    hashes = set()
    invalid_timing = 0
    for table in (*TABLES, *DIRECTORIES):
        for row, path in records(root, table):
            rid = row.get("id")
            if not isinstance(rid, str) or not ID.fullmatch(rid):
                raise ValueError(f"{path}: invalid id {rid!r}")
            if row.get("schema_version") != 1 or row.get("kind") is None:
                raise ValueError(f"{path}: expected schema_version=1 and kind")
            kinds = {
                "items": {"video", "part", "recording", "dynamic", "article", "person"},
                "collections": {"article_list", "season", "series"},
                "media": {"audio"},
                "annotations": {"confirmation"},
                "transcripts": {"transcript"},
                "readings": {"reading"},
                "dynamics": {"dynamic"},
                "articles": {"article"},
            }
            if row["kind"] not in kinds[table]:
                raise ValueError(f"{rid}: unexpected kind for {table}")
            if rid in all_ids:
                raise ValueError(f"Duplicate id {rid}")
            if table in DIRECTORIES and path.stem != rid:
                raise ValueError(f"{path}: filename must equal id")
            all_ids[rid] = table
            counts[table] += 1

            def collect_evidence(value):
                if isinstance(value, dict):
                    if "transcript_id" in value and "alignment_ids" in value:
                        evidence_references.append((rid, row.get("item_id"), value))
                    for nested in value.values():
                        collect_evidence(nested)
                elif isinstance(value, list):
                    for nested in value:
                        collect_evidence(nested)

            collect_evidence(row.get("quality"))
            collect_evidence(row.get("attributes"))
            if table == "items":
                if not isinstance(row.get("title"), str) or not isinstance(
                    row.get("identifiers"), dict
                ):
                    raise ValueError(f"{rid}: expected title and identifiers")
                items[rid] = row
                if row.get("parent_id"):
                    references.append((rid, "items", row["parent_id"]))
                for relation in row.get("relations", []):
                    references.append((rid, "items", relation["item_id"]))
            elif table == "collections":
                if not isinstance(row.get("members"), list):
                    raise ValueError(f"{rid}: expected ordered members")
                counts["collection_members"] += len(row["members"])
                for member in row["members"]:
                    references.append((rid, "items", member["item_id"]))
            elif table == "media":
                if not isinstance(row.get("sha256"), str) or not SHA256.fullmatch(
                    row["sha256"]
                ):
                    raise ValueError(f"{rid}: invalid media SHA-256")
                if row["sha256"] in hashes:
                    raise ValueError(f"Duplicate media SHA-256: {row['sha256']}")
                hashes.add(row["sha256"])
                media[rid] = row
                for item in row.get("item_ids", []):
                    references.append((rid, "items", item))
                if row.get("availability") == "release":
                    relative_path(row["path"])
                    downloads = row.get("downloads", [])
                    if row["path"] in restore_paths:
                        raise ValueError(f"{rid}: duplicate audio restore path")
                    restore_paths.add(row["path"])
                    if (
                        not downloads
                        or not isinstance(row.get("bytes"), int)
                        or row["bytes"] < 0
                    ):
                        raise ValueError(f"{rid}: incomplete Release locator")
                    for download in downloads:
                        relative_path(download["member"])
                        relative_path(download["asset"]["name"])
                        relative_path(download["release_tag"])
                        asset = download["asset"]
                        key = (download["release_tag"], asset["name"])
                        if key in archives and archives[key] != asset:
                            raise ValueError(f"{rid}: conflicting archive metadata")
                        archives[key] = asset
                        member = (*key, download["member"])
                        if member in archive_members:
                            raise ValueError(f"{rid}: duplicate archive member")
                        archive_members.add(member)
                        if not SHA256.fullmatch(asset["sha256"]) or not isinstance(
                            asset["bytes"], int
                        ):
                            raise ValueError(f"{rid}: invalid archive digest/size")
                        if not asset["url"].startswith("https://"):
                            raise ValueError(f"{rid}: archive URL must use HTTPS")
                    counts["restorable_audio"] += 1
                    counts["audio_bytes"] += row["bytes"]
                else:
                    if row.get("availability") != "unavailable":
                        raise ValueError(f"{rid}: invalid availability")
                    counts["unavailable_audio"] += 1
            elif table in DIRECTORIES:
                references.append((rid, "items", row["item_id"]))
                contents[rid] = {"item_id": row["item_id"], "table": table}
                if table in ("transcripts", "readings", "articles"):
                    if not isinstance(row.get("text"), str):
                        raise ValueError(f"{rid}: expected text")
                    quality(row)
                if table == "transcripts":
                    if row.get("time_unit") not in ("ms", "s") or not isinstance(
                        row.get("segments"), list
                    ):
                        raise ValueError(f"{rid}: invalid segments/time unit")
                    for index, segment in enumerate(row["segments"]):
                        if (
                            not isinstance(segment.get("text"), str)
                            or segment.get("ordinal") != index
                        ):
                            raise ValueError(
                                f"{rid}: segment ordinal/text mismatch at {index}"
                            )
                    if fingerprint(transcript_identity(row)) != row.get(
                        "content_sha256"
                    ):
                        raise ValueError(f"{rid}: transcript content SHA-256 mismatch")
                    if "alignments" in row:
                        if not isinstance(row["alignments"], list) or fingerprint(
                            row["alignments"]
                        ) != row.get("alignments_sha256"):
                            raise ValueError(f"{rid}: alignment SHA-256 mismatch")
                        alignment_ids = [a["id"] for a in row["alignments"]]
                        if len(set(alignment_ids)) != len(alignment_ids):
                            raise ValueError(f"{rid}: duplicate alignment id")
                        for alignment in row["alignments"]:
                            if alignment.get("time_unit") != "ms" or not isinstance(
                                alignment.get("sentences"), list
                            ):
                                raise ValueError(
                                    f"{rid}: invalid recognition alignment"
                                )
                    alignments_by_transcript[rid] = {
                        a["id"] for a in row.get("alignments", [])
                    }
                    issues = timing_issues(row)
                    if issues != row["quality"].get("timing_issues", []):
                        raise ValueError(
                            f"{rid}: timing issue list does not describe stored values"
                        )
                    invalid_timing += bool(issues)
                    counts["segments"] += len(row["segments"])
                if table == "readings":
                    if not isinstance(row.get("paragraphs"), list):
                        raise ValueError(f"{rid}: expected paragraphs")
                    if row.get("time_unit") not in ("ms", "s", None):
                        raise ValueError(f"{rid}: invalid paragraph time unit")
                    counts["paragraphs"] += len(row["paragraphs"])
                    for ref in row.get("transcript_ids", []):
                        references.append((rid, "transcripts", ref))
                    if row.get("derived_from"):
                        references.append((rid, "readings", row["derived_from"]))
                        reading_parents[rid] = row["derived_from"]
                    if row.get("reference_units_reading_id"):
                        references.append(
                            (rid, "readings", row["reference_units_reading_id"])
                        )
                        unit_references[rid] = row["reference_units_reading_id"]
                    reading_anchors[rid] = set()
                    for annotation in annotations.values():
                        if annotation["item_id"] == row["item_id"]:
                            anchor = annotation["anchor"]["original_text"]
                            corrected = annotation["corrected_text"]
                            if (
                                anchor in row["text"]
                                or corrected in row["text"]
                                or any(
                                    anchor in p.get("text", "")
                                    or corrected in p.get("text", "")
                                    for p in row["paragraphs"]
                                )
                            ):
                                reading_anchors[rid].add(annotation["id"])
                    if not row.get("complete", True):
                        counts["incomplete_readings"] += 1
                for ref in row.get("media_ids", []):
                    references.append((rid, "media", ref))
                if table == "dynamics":
                    if not isinstance(row.get("content"), dict):
                        raise ValueError(f"{rid}: expected rich dynamic content")
                    for article in row.get("article_item_ids", []):
                        references.append((rid, "items", article))
            elif table == "annotations":
                annotations[rid] = row
                if not row.get("reading_ids"):
                    raise ValueError(f"{rid}: confirmation has no reading anchor")
                references.append((rid, "items", row["item_id"]))
                for reading in row.get("reading_ids", []):
                    references.append((rid, "readings", reading))
                anchor = row["anchor"]
                if (
                    hashlib.sha256(anchor["original_text"].encode("utf-8")).hexdigest()
                    != anchor["original_text_sha256"]
                ):
                    raise ValueError(f"{rid}: annotation anchor hash mismatch")
                if (
                    hashlib.sha256(row["corrected_text"].encode("utf-8")).hexdigest()
                    != row["corrected_text_sha256"]
                ):
                    raise ValueError(f"{rid}: corrected text hash mismatch")
    for rid, table, target in references:
        if all_ids.get(target) != table:
            raise ValueError(f"{rid}: unresolved {table} reference {target}")
    for rid, item, evidence in evidence_references:
        target = evidence["transcript_id"]
        if all_ids.get(target) != "transcripts" or contents[target]["item_id"] != item:
            raise ValueError(f"{rid}: unresolved transcript evidence {target}")
        if (
            not evidence["alignment_ids"]
            or not set(evidence["alignment_ids"]) <= alignments_by_transcript[target]
        ):
            raise ValueError(f"{rid}: unresolved alignment evidence")
    for rid, parent in {**reading_parents, **unit_references}.items():
        if contents[rid]["item_id"] != contents[parent]["item_id"]:
            raise ValueError(f"{rid}: reading parent belongs to a different item")
    for rid in reading_parents:
        seen, current = {rid}, reading_parents[rid]
        while current in reading_parents:
            if current in seen:
                raise ValueError(f"{rid}: reading parent cycle")
            seen.add(current)
            current = reading_parents[current]
    for rid, annotation in annotations.items():
        if not any(
            rid in reading_anchors.get(reading, set())
            for reading in annotation["reading_ids"]
        ):
            raise ValueError(
                f"{rid}: confirmation text cannot be located in its readings"
            )
    for rid, row in items.items():
        counts["items_" + row["kind"]] += 1
        if row.get("parent_id"):
            seen = {rid}
            current = row["parent_id"]
            while current:
                if current in seen:
                    raise ValueError(f"{rid}: parent cycle")
                seen.add(current)
                current = items[current].get("parent_id")
    selection = read_json(root / "selections" / "training.json")
    selected_items = set()
    for entry in selection["entries"]:
        item, reading = entry["item_id"], entry["reading_id"]
        if item in selected_items or contents.get(reading) != {
            "item_id": item,
            "table": "readings",
        }:
            raise ValueError(f"Invalid or duplicate training entry: {entry}")
        selected_items.add(item)
        for annotation in entry.get("annotation_ids", []):
            if all_ids.get(annotation) != "annotations":
                raise ValueError(f"Unresolved training annotation {annotation}")
            if (
                annotations[annotation]["item_id"] != item
                or reading not in annotations[annotation]["reading_ids"]
            ):
                raise ValueError(
                    f"Training annotation does not apply to selected reading: {annotation}"
                )
    counts["training_entries"] = len(selection["entries"])
    counts["timing_issue_transcripts"] = invalid_timing
    return dict(sorted(counts.items()))
