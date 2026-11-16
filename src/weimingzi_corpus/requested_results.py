"""Lossless adapter for requested-video-results/v1 packages (no ASR execution)."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

from .records import (
    find_timestamp_issues,
    iter_records,
    json_sha256,
    make_record_id,
    transcript_hash_input,
    validate_corpus,
    validate_relative_path,
    install_candidate_updates,
    write_record_updates,
)
from .exports import render_subtitles

FORMAT = "requested-video-results/v1"
MEMBERS = (
    "metadata.json",
    "asr.json",
    "asr-quality.json",
    "proofread.json",
    "asr.txt",
    "asr.srt",
    "asr.vtt",
    "ai-draft.md",
    "review.md",
)


def package_records(root: Path, source: Path) -> dict[str, list[dict]]:
    """Verify every member before adapting; never extract archive paths."""
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    items = [row for row, _ in iter_records(root, "items")]
    result = {"transcripts": [], "edited_transcripts": []}
    with zipfile.ZipFile(source) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries if not entry.is_dir()]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate package member")
        for entry in entries:
            validate_relative_path(entry.filename)
        if sum(entry.file_size for entry in entries) > 100 * 1024 * 1024:
            raise ValueError("Package exceeds 100 MiB uncompressed")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("format") != FORMAT:
            raise ValueError("Unsupported package format")
        bvids = manifest["bvids"]
        if not bvids or len(bvids) != len(set(bvids)):
            raise ValueError("Expected distinct package BVIDs")
        for bvid in bvids:
            if (
                not isinstance(bvid, str)
                or not bvid.startswith("BV")
                or not bvid.isalnum()
            ):
                raise ValueError("Invalid package BVID")
        expected = {bvid + "/" + name for bvid in bvids for name in MEMBERS}
        files = manifest["files"]
        if (
            len(files) != len(expected)
            or {f["path"] for f in files} != expected
            or set(names) != expected | {"manifest.json"}
        ):
            raise ValueError("Package member list does not match manifest")
        payload = {}
        for member in files:
            data = archive.read(member["path"])
            if (
                len(data) != member["bytes"]
                or hashlib.sha256(data).hexdigest() != member["sha256"]
            ):
                raise ValueError(
                    "Package member size/SHA-256 mismatch: " + member["path"]
                )
            payload[member["path"]] = data.decode("utf-8")

        if manifest.get("video_count") != len(bvids) or manifest.get(
            "part_count"
        ) != len(bvids):
            raise ValueError("This adapter requires one part per video")
        for bvid in bvids:

            def read(name):
                return payload[bvid + "/" + name]

            metadata = json.loads(read("metadata.json"))
            asr = json.loads(read("asr.json"))
            quality = json.loads(read("asr-quality.json"))
            proof = json.loads(read("proofread.json"))
            if metadata["bvid"] != bvid or len(metadata["parts"]) != 1:
                raise ValueError("Package video/part identity mismatch")
            part = metadata["parts"][0]
            matches = [
                i
                for i in items
                if i["kind"] == "video_part"
                and bvid in i["identifiers"].get("bilibili_bvid", [])
                and i.get("part_number") == part["page_index"] + 1
                and part["cid"] in i.get("metadata", {}).get("cid", [])
            ]
            if len(matches) != 1:
                raise ValueError("Expected one existing BVID/page/CID item: " + bvid)
            item_id = matches[0]["id"]
            upstream = asr["transcript_id"]
            if (
                part["asr_transcript_id"] != upstream
                or proof["base_transcript_id"] != upstream
                or quality["transcript_id"] != upstream
                or quality["video_part_id"] != asr["video_part_id"]
                or part["asr_run_id"] != asr["run_id"]
                or quality["run_id"] != asr["run_id"]
                or quality["content_sha256"] != asr["content_sha256"]
                or part["asr_segments"] != len(asr["segments"])
                or quality["segment_count"] != len(asr["segments"])
            ):
                raise ValueError("Package ASR provenance mismatch")
            if asr["source_kind"] != "asr-local":
                raise ValueError("Unsupported package recognition method")
            if (
                proof["model"] != part["proofread"]["model"]
                or proof["model"] != manifest["editorial_model"]
                or proof["revision_id"] != part["proofread"]["revision_id"]
                or proof["human_reviewed"] is not False
                or manifest["human_reviewed"] is not False
                or part["proofread"]["human_reviewed"] is not False
                or proof["quality_status"] != "needs-review"
                or part["proofread"]["quality_status"] != proof["quality_status"]
            ):
                raise ValueError("Package editorial provenance/review mismatch")
            provenance = {
                "package_sha256": digest,
                "manifest": manifest,
                "member_prefix": bvid,
                "video_snapshot": metadata,
            }
            segments = []
            units = []
            for index, segment in enumerate(asr["segments"]):
                if segment["ordinal"] != index:
                    raise ValueError("Package segment order mismatch")
                segments.append(
                    {
                        "index": index,
                        "start": segment["start_ms"],
                        "end": segment["end_ms"],
                        "text": segment["text"],
                    }
                )
                units.append({"label": f"t{upstream}:s{index}", **segment})
            transcript = {
                "schema_version": 2,
                "kind": "transcript",
                "id": make_record_id("t", [FORMAT, digest, bvid, "asr.json"]),
                "item_id": item_id,
                "method": "asr_local",
                "model": None,
                "language": asr["language"],
                "time_unit": "ms",
                "text": read("asr.txt"),
                "segments": segments,
                "audio_ids": [],
                "quality": {
                    "is_fully_human_reviewed": False,
                    "requires_review": True,
                    "is_subtitle_export_enabled": True,
                    "timing_issues": [],
                    "source_admission": quality,
                },
                "metadata": {
                    "source_package": provenance,
                    "upstream": {k: v for k, v in asr.items() if k != "segments"},
                },
            }
            if find_timestamp_issues(transcript):
                raise ValueError("Package has invalid timestamps; no automatic repair")
            if (
                not segments
                or read("asr.txt").strip()
                != chr(10).join(s["text"] for s in segments).strip()
            ):
                raise ValueError("Package TXT differs from ASR segments")
            # The supplied exports also certify that no rounding/text repair is needed.
            for extension in ("srt", "vtt"):
                if (
                    render_subtitles(transcript, extension).strip()
                    != read("asr." + extension).strip()
                ):
                    raise ValueError("Package subtitle differs from ASR: " + extension)
            transcript["content_sha256"] = json_sha256(
                transcript_hash_input(transcript)
            )
            paragraphs, referenced = [], []
            for index, block in enumerate(proof["blocks"]):
                labels = block["segment_ids"]
                referenced.extend(labels)
                if any(
                    not set(issue.get("evidence_refs", [])) <= set(labels)
                    for issue in block["issues"]
                ):
                    raise ValueError("Editorial evidence outside its block")
                paragraphs.append(
                    {
                        "index": index,
                        "input_text": block["original_text"],
                        "text": block["text"],
                        "start": block["start_ms"],
                        "end": block["end_ms"],
                        "input_unit_labels": labels,
                        "issues": [
                            {
                                "note": issue["note"],
                                "candidate": issue["candidate"],
                                "evidence_labels": issue["evidence_refs"],
                            }
                            for issue in block["issues"]
                        ],
                    }
                )
            if Counter(referenced) != Counter(u["label"] for u in units):
                raise ValueError("Editorial blocks must cover every input exactly once")
            if (
                len(paragraphs) != part["proofread"]["blocks"]
                or sum(bool(p["issues"]) for p in paragraphs)
                != part["proofread"]["issue_blocks"]
            ):
                raise ValueError("Editorial block counts mismatch")
            text = read("ai-draft.md")
            edited = {
                "schema_version": 2,
                "kind": "edited_transcript",
                "id": make_record_id("r", [FORMAT, digest, bvid, "proofread.json"]),
                "item_id": item_id,
                "text": text,
                "paragraphs": paragraphs,
                "model": {"name": proof["model"]},
                "time_unit": "ms",
                "transcript_ids": [transcript["id"]],
                "notes_markdown": "",
                "review_document_markdown": read("review.md"),
                "is_complete": True,
                "paragraphs_match_text": text.strip()
                == (chr(10) * 2).join(p["text"] for p in paragraphs).strip(),
                "quality": {
                    "is_fully_human_reviewed": False,
                    "requires_review": True,
                    "status": proof["quality_status"],
                    "completion_basis": "every packaged input segment referenced once; not an audio coverage judgment",
                },
                "input_units": {
                    "base": {
                        "upstream_transcript_id": upstream,
                        "content_sha256": asr["content_sha256"],
                        "method": "asr_local",
                        "language": asr["language"],
                        "segments": units,
                    },
                    "unassigned_reference_labels": [],
                },
                "metadata": {
                    "source_package": provenance,
                    "upstream": {k: v for k, v in proof.items() if k != "blocks"},
                },
            }
            result["transcripts"].append(transcript)
            result["edited_transcripts"].append(edited)
    return result


def import_requested_results(root: Path, source: Path) -> dict:
    incoming = package_records(root, source)
    new = {}
    for table, rows in incoming.items():
        existing = {r["id"]: r for r, _ in iter_records(root, table)}
        for row in rows:
            if row["id"] in existing and row != existing[row["id"]]:
                raise ValueError(
                    "Import would overwrite a different record: " + row["id"]
                )
        new[table] = [row for row in rows if row["id"] not in existing]
    cache = root / ".cache"
    cache.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="package-", dir=cache) as name:
        candidate = Path(name)
        shutil.copytree(root / "data", candidate / "data", copy_function=os.link)
        changed_paths = write_record_updates(candidate, new)
        validate_corpus(candidate)
        install_candidate_updates(root, candidate, changed_paths)
    return {
        "inserted": {table: len(rows) for table, rows in new.items()},
        "record_ids": {
            table: [r["id"] for r in rows] for table, rows in incoming.items()
        },
    }
