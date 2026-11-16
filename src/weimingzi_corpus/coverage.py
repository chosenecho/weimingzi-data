"""Evidence-preserving manuscript coverage, without merging source identities."""

from __future__ import annotations

import copy
import unicodedata
from collections import defaultdict
from pathlib import Path

from .records import (
    SHA256_PATTERN, canonical_json, content_record_path, iter_records,
    load_content_record,
)

LAYERS = ("direct", "cross_source", "same_audio", "chapter_supplement")


def text_status(text: str) -> str:
    """Literal text screening; never a judgment of source-audio silence."""
    meaningful = [
        c for c in text if not c.isspace() and unicodedata.category(c)[0] not in "PSZC"
    ]
    if not meaningful:
        return "empty"
    if set(meaningful) <= set("嗯呃啊哦唔额唉哎噢"):
        return "filler_only"
    return "text_present_unverified"


def record_summary(row: dict, table: str, root: Path | None = None) -> dict:
    quality = row.get("quality", {})
    return {
        "id": row["id"],
        "item_id": row["item_id"],
        "kind": row["kind"],
        "record_path": (
            content_record_path(root, table, row["id"])
            .relative_to(root.resolve()).as_posix()
            if root is not None else f"data/{table}/{row['id']}.json"
        ),
        "method": row.get("method"),
        "model": row.get("model"),
        "transcript_ids": row.get("transcript_ids", []),
        "is_complete": row.get("is_complete"),
        "is_fully_human_reviewed": quality.get("is_fully_human_reviewed"),
        "requires_review": quality.get("requires_review"),
        "text_status": text_status(row["text"]),
        "quality": quality,
    }


def counts(records: list[dict]) -> dict:
    # A candidate is a nonempty, non-filler completed output, not approved prose.
    unique = {r["id"]: r for r in records}.values()
    transcripts, edited, candidates, reviewed = 0, 0, 0, 0
    text_present, filler, empty = 0, 0, 0
    for row in unique:
        transcripts += row["kind"] == "transcript"
        if row["kind"] == "transcript":
            text_present += row["text_status"] == "text_present_unverified"
            filler += row["text_status"] == "filler_only"
            empty += row["text_status"] == "empty"
        if row["kind"] == "edited_transcript":
            edited += 1
            candidate = (
                row["is_complete"] is True
                and row["text_status"] == "text_present_unverified"
            )
            candidates += candidate
            reviewed += candidate and row["is_fully_human_reviewed"] is True
    return {
        "transcripts": transcripts,
        "text_present_transcripts": text_present,
        "filler_only_transcripts": filler,
        "empty_transcripts": empty,
        "edited_transcripts": edited,
        "complete_text_candidates": candidates,
        "human_reviewed_complete_texts": reviewed,
    }


class CoverageIndex:
    """Load only small summaries; full records are read on explicit export."""

    def __init__(self, root: Path, load_content: bool = True):
        self.root = root
        self.items = {r["id"]: r for r, _ in iter_records(root, "items")}
        self.collections = [r for r, _ in iter_records(root, "collections")]
        self.children = defaultdict(set)
        self.by_item = defaultdict(list)
        self.audio_groups = defaultdict(set)
        self.audio_evidence = defaultdict(list)
        for row in self.items.values():
            if row.get("parent_id"):
                self.children[row["parent_id"]].add(row["id"])
            for digest in row["identifiers"].get("audio_sha256", []):
                if SHA256_PATTERN.fullmatch(digest):
                    self.audio_groups[digest].add(row["id"])
                    self.audio_evidence[digest].append(
                        {"item_id": row["id"], "field": "identifiers.audio_sha256"}
                    )
        for row, _ in iter_records(root, "audio"):
            self.audio_groups[row["sha256"]].update(row.get("item_ids", []))
            self.audio_evidence[row["sha256"]].append(
                {
                    "audio_id": row["id"],
                    "item_ids": row.get("item_ids", []),
                    "field": "sha256",
                    "availability": row["availability"],
                }
            )
        for table in ("transcripts", "edited_transcripts") if load_content else ():
            for row, _ in iter_records(root, table):
                self.by_item[row["item_id"]].append(record_summary(row, table, root))

    def resolve(self, identifier: str, part: int | None = None) -> str:
        if part is not None and part < 1:
            raise ValueError("Part must be positive")
        if identifier in self.items:
            matches = [self.items[identifier]]
        else:
            matches = [
                i
                for i in self.items.values()
                if i["kind"] in {"video", "video_part", "audio_recording"}
                and any(identifier in values for values in i["identifiers"].values())
            ]
            videos = [i for i in matches if i["kind"] == "video"]
            if len(videos) == 1:
                matches = videos
        if part is not None and len(matches) == 1:
            parent = matches[0]
            matches = (
                [parent]
                if parent["kind"] == "video_part"
                else [self.items[i] for i in self.children[parent["id"]]]
            )
            matches = [i for i in matches if i.get("part_number") == part]
        if len(matches) != 1:
            raise ValueError("Expected one matching item: " + identifier)
        return matches[0]["id"]

    def family(self, item_id: str) -> set[str]:
        # Expand only a video endpoint; a part does not stand for its siblings.
        return {item_id} | (
            self.children[item_id] if self.items[item_id]["kind"] == "video" else set()
        )

    def report(
        self, identifier: str, part: int | None = None, include_records: bool = False
    ) -> dict:
        item_id = self.resolve(identifier, part)
        scope = self.family(item_id)
        context = scope | {
            self.items[i]["parent_id"] for i in scope if self.items[i].get("parent_id")
        }
        associations = {layer: defaultdict(list) for layer in LAYERS}

        def add(layer, target, evidence):
            if layer != "direct" and target in scope:
                return
            if evidence not in associations[layer][target]:
                associations[layer][target].append(evidence)

        for direct in sorted(scope):
            add(
                "direct",
                direct,
                {
                    "kind": "direct_item",
                    "item_id": direct,
                    "scope": "queried_item"
                    if direct == item_id
                    else "child_of_queried_video",
                },
            )
        for source in sorted(self.items.values(), key=lambda i: i["id"]):
            for relation in source.get("relations", []):
                kind = relation["kind"]
                layer = (
                    "cross_source"
                    if kind
                    in {"references", "references_video", "audible_rerecording_of"}
                    else "chapter_supplement"
                    if kind == "chapter_supplement_not_audio_identity"
                    else None
                )
                if not layer:
                    continue
                a, b = source["id"], relation["target_item_id"]
                for near, far in ((a, b), (b, a)):
                    if near in context:
                        evidence = {
                            "kind": kind,
                            "source_item_id": a,
                            "target_item_id": b,
                            "relation": relation,
                            "proves_audio_identity": False,
                            "scope": "chapter_only"
                            if layer == "chapter_supplement"
                            else "audible_rerecording_not_time_alignment"
                            if kind == "audible_rerecording_of"
                            else "explicit_reference_not_part_alignment",
                        }
                        for target in sorted(self.family(far)):
                            add(layer, target, evidence)
        for digest, members in sorted(self.audio_groups.items()):
            anchors = members & scope
            if anchors:
                for target in sorted(members - scope):
                    add(
                        "same_audio",
                        target,
                        {
                            "kind": "same_audio_sha256",
                            "sha256": digest,
                            "source_item_ids": sorted(anchors),
                            "target_item_id": target,
                            "evidence": self.audio_evidence[digest],
                            "proves_audio_identity": True,
                        },
                    )
        layers = {}
        for layer in LAYERS:
            records = []
            for target, evidence in sorted(associations[layer].items()):
                for summary in self.by_item[target]:
                    row = copy.deepcopy(summary)
                    row["associations"] = evidence
                    if include_records:
                        row["record"] = load_content_record(self.root, row["id"])
                    records.append(row)
            records.sort(key=lambda r: (r["item_id"], r["id"]))
            layers[layer] = {
                "items": [
                    {
                        "item_id": target,
                        "title": self.items[target]["title"],
                        "associations": evidence,
                    }
                    for target, evidence in sorted(associations[layer].items())
                ],
                "records": records,
                "counts": counts(records),
            }
        direct = layers["direct"]["counts"]
        related = counts([r for layer in LAYERS[1:] for r in layers[layer]["records"]])
        return {
            "format": "manuscript-coverage/v1",
            "query": {"identifier": identifier, "part": part},
            "item_id": item_id,
            "scope_item_ids": sorted(scope),
            "layers": layers,
            "summary": {
                "direct": direct,
                "related": related,
                "has_direct_edited_transcript": bool(direct["edited_transcripts"]),
                "has_related_edited_transcript": bool(related["edited_transcripts"]),
            },
        }


def coverage_jsonl(report: dict) -> str:
    return "".join(
        canonical_json({"query_item_id": report["item_id"], "layer": layer, **row})
        + chr(10)
        for layer in LAYERS
        for row in report["layers"][layer]["records"]
    )
