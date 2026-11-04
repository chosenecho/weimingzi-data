"""Layered coverage keeps identities, evidence, variants and review state."""

import copy
import json
import sys
import unittest
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import test_corpus as fixtures
from weimingzi_corpus.coverage import CoverageIndex, coverage_jsonl, text_status
from weimingzi_corpus.records import (
    make_record_id,
    write_json,
    write_jsonl,
    read_json,
    json_sha256,
    transcript_hash_input,
)


@lru_cache(maxsize=1)
def repository_index():
    root = Path(__file__).resolve().parents[1]
    if not (root / "data/items.jsonl").is_file():
        raise unittest.SkipTest(
            "Full repository data is not present in sparse tools checkout"
        )
    return CoverageIndex(root)


class CoverageTests(unittest.TestCase):
    setUp = fixtures.CorpusTests.setUp
    tearDown = fixtures.CorpusTests.tearDown
    save_transcript = fixtures.CorpusTests.save_transcript

    def fixture(self):
        self.video = copy.deepcopy(self.item)
        self.video.update(
            id=make_record_id("i", "video"),
            kind="video",
            identifiers={"bilibili_bvid": ["BVfixture"]},
        )
        self.item.update(kind="video_part", parent_id=self.video["id"], part_number=1)
        self.sibling = copy.deepcopy(self.item)
        self.sibling.update(id=make_record_id("i", "sibling"), part_number=2)
        self.youtube = copy.deepcopy(self.video)
        self.youtube.update(
            id=make_record_id("i", "youtube"),
            identifiers={"youtube_id": ["youtube"]},
            relations=[
                {
                    "kind": "references",
                    "target_item_id": self.video["id"],
                    "evidence": "explicit upstream reference",
                }
            ],
        )
        self.variant = copy.deepcopy(self.video)
        self.variant.update(id=make_record_id("i", "variant"), identifiers={})
        self.supplement = copy.deepcopy(self.video)
        self.supplement.update(
            id=make_record_id("i", "supplement"),
            kind="audio_recording",
            identifiers={},
            relations=[
                {
                    "kind": "chapter_supplement_not_audio_identity",
                    "target_item_id": self.item["id"],
                    "evidence": "chapter only",
                }
            ],
        )
        write_jsonl(
            self.root / "data/items.jsonl",
            [
                self.video,
                self.item,
                self.sibling,
                self.youtube,
                self.variant,
                self.supplement,
            ],
        )
        write_jsonl(
            self.root / "data/audio.jsonl",
            [
                {
                    "schema_version": 2,
                    "id": make_record_id("m", "audio"),
                    "kind": "audio",
                    "sha256": "a" * 64,
                    "item_ids": [self.item["id"], self.variant["id"]],
                    "availability": "unavailable",
                    "local_path": None,
                }
            ],
        )

    def edited(self, item, name, complete=True, text="有实质正文。"):
        row = {
            "schema_version": 2,
            "kind": "edited_transcript",
            "id": make_record_id("r", name),
            "item_id": item["id"],
            "text": text,
            "paragraphs": [{"index": 0, "text": text}],
            "model": None,
            "is_complete": complete,
            "transcript_ids": [self.transcript["id"]],
            "quality": {"is_fully_human_reviewed": False, "requires_review": True},
        }
        write_json(self.root / "data/edited_transcripts" / (row["id"] + ".json"), row)
        return row

    def test_four_layers_preserve_evidence_without_equating_sources(self):
        self.fixture()
        foreign = self.edited(self.youtube, "cross")
        same = self.edited(self.variant, "same")
        extra = self.edited(self.supplement, "extra", complete=False)
        report = CoverageIndex(self.root).report(
            "BVfixture", part=1, include_records=True
        )
        self.assertFalse(report["summary"]["has_direct_edited_transcript"])
        self.assertTrue(report["summary"]["has_related_edited_transcript"])
        layers = report["layers"]
        for layer, row in [
            ("cross_source", foreign),
            ("same_audio", same),
            ("chapter_supplement", extra),
        ]:
            actual = layers[layer]["records"][0]
            self.assertEqual(actual["record"], row)
            self.assertEqual(actual["transcript_ids"], row["transcript_ids"])
            self.assertFalse(actual["is_fully_human_reviewed"])
        evidence = layers["cross_source"]["records"][0]["associations"][0]
        self.assertFalse(evidence["proves_audio_identity"])
        self.assertEqual(evidence["target_item_id"], self.video["id"])
        self.assertEqual(
            evidence["relation"]["evidence"], "explicit upstream reference"
        )
        same_evidence = layers["same_audio"]["records"][0]["associations"][0]
        self.assertEqual(same_evidence["sha256"], "a" * 64)
        self.assertTrue(same_evidence["proves_audio_identity"])
        self.assertEqual(
            layers["chapter_supplement"]["counts"]["complete_text_candidates"], 0
        )

    def test_direct_child_does_not_expand_to_siblings_and_parent_does(self):
        self.fixture()
        row = self.edited(self.sibling, "sibling")
        index = CoverageIndex(self.root)
        part = index.report(self.item["id"])
        parent = index.report(self.video["id"])
        self.assertEqual(part["scope_item_ids"], [self.item["id"]])
        self.assertFalse(part["summary"]["has_direct_edited_transcript"])
        self.assertIn(
            row["id"], [r["id"] for r in parent["layers"]["direct"]["records"]]
        )
        reverse = index.report(self.youtube["id"])
        self.assertIn(
            row["id"], [r["id"] for r in reverse["layers"]["cross_source"]["records"]]
        )
        self.assertEqual(reverse["layers"]["same_audio"]["records"], [])

    def test_variants_export_unchanged_and_partial_filler_empty_are_not_complete_candidates(
        self,
    ):
        self.fixture()
        rows = [
            self.edited(self.item, "complete"),
            self.edited(self.item, "partial", False),
            self.edited(self.item, "filler", text="嗯。" * 22),
            self.edited(self.item, "empty", text="  "),
        ]
        report = CoverageIndex(self.root).report(self.item["id"], include_records=True)
        self.assertEqual(report["summary"]["direct"]["edited_transcripts"], 4)
        self.assertEqual(report["summary"]["direct"]["complete_text_candidates"], 1)
        self.assertEqual(
            report["summary"]["direct"]["human_reviewed_complete_texts"], 0
        )
        exported = [json.loads(line) for line in coverage_jsonl(report).splitlines()]
        for row in rows:
            self.assertEqual(
                next(r["record"] for r in exported if r["id"] == row["id"]), row
            )

    def test_unknown_item_and_invalid_part_fail_closed(self):
        index = CoverageIndex(self.root)
        for name, part in [
            ("missing", None),
            (self.item["id"], 0),
            (self.item["id"], 2),
        ]:
            with self.assertRaises(ValueError):
                index.report(name, part)

    def test_literal_screening_is_not_a_silence_diagnosis(self):
        self.assertEqual(text_status("嗯。" * 22), "filler_only")
        self.assertEqual(text_status("  。"), "empty")
        self.assertEqual(text_status("嗯，这是正文。"), "text_present_unverified")


class RepositoryCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = repository_index()

    def test_imported_drafts_and_existing_cross_source_remain_independent(self):
        violence = self.index.report("BV1cq4y1t7TN", 1)
        self.assertIn(
            "r-e218b0a4f4d57ebb0ca1ee8c",
            [r["id"] for r in violence["layers"]["direct"]["records"]],
        )
        agriculture = self.index.report("BV1oq4y1q7rg", 1)
        direct = agriculture["layers"]["direct"]["records"]
        cross = agriculture["layers"]["cross_source"]["records"]
        self.assertIn("r-c4f6ca743a51bec6628c460f", [r["id"] for r in direct])
        original = next(r for r in direct if r["id"] == "t-42da540e9a38fd97f0a2b01a")
        self.assertEqual(
            original["quality"]["timing_issues"],
            ["segment 150: starts must not decrease"],
        )
        foreign = next(r for r in cross if r["id"] == "r-3e4fbb431036ed2edf57ae76")
        self.assertFalse(foreign["associations"][0]["proves_audio_identity"])
        self.assertIsNone(foreign["requires_review"])
        self.assertFalse(foreign["is_fully_human_reviewed"])

    def test_known_same_audio_versions_retain_exact_identity_evidence(self):
        cases = [
            (
                "i-7fee8b9e09f3f0d185f2aaa2",
                "r-9527217067414b4e8db2fcd9",
                "16fa85313fbe08c7ab6a14f035e41b35c5a0877eae67e4a4a0b99159cee3ff5d",
            ),
            (
                "i-e33df3f1154c7f435ae90247",
                "r-9a2a0391943144c593d884f3",
                "cbbd1420cf0588063ee57a70c9b42eb80c84e38d99c3a6a77d83b35ce5d17c25",
            ),
        ]
        for item_id, record_id, digest in cases:
            rows = self.index.report(item_id)["layers"]["same_audio"]["records"]
            row = next(r for r in rows if r["id"] == record_id)
            self.assertTrue(
                any(
                    a["sha256"] == digest and a["proves_audio_identity"]
                    for a in row["associations"]
                )
            )

    def test_chapter_supplements_and_incomplete_variants_are_visible(self):
        records = []
        for item_id in (
            "i-d0ea1e12a0df658bb0f8f286",
            "i-c4c2fb49b36af3b5400911db",
            "i-edec0437bb8b4a2b7af9359f",
        ):
            report = self.index.report(item_id)
            records.extend(report["layers"]["direct"]["records"])
            for relation in self.index.items[item_id]["relations"]:
                if relation["kind"] == "chapter_supplement_not_audio_identity":
                    layer = self.index.report(relation["target_item_id"])["layers"][
                        "chapter_supplement"
                    ]
                    linked = next(i for i in layer["items"] if i["item_id"] == item_id)
                    self.assertFalse(linked["associations"][0]["proves_audio_identity"])
        self.assertEqual(sum(r["kind"] == "transcript" for r in records), 3)
        self.assertEqual(sum(r["kind"] == "edited_transcript" for r in records), 5)
        self.assertTrue(any(r["is_complete"] is False for r in records))

    def test_issue_five_does_not_count_filler_as_substantive_manuscript(self):
        report = self.index.report("BV1CP4y1s7BM", 2)
        rows = report["layers"]["direct"]["records"]
        original = next(r for r in rows if r["id"] == "t-79e1eb0ea7c54df6013b144c")
        self.assertEqual(original["text_status"], "filler_only")
        counts = report["summary"]["direct"]
        self.assertLess(counts["text_present_transcripts"], counts["transcripts"])
        self.assertGreaterEqual(counts["filler_only_transcripts"], 1)

    def test_filler_quality_annotation_is_bound_to_unchanged_original_content(self):
        row = read_json(
            self.index.root / "data/transcripts/t-79e1eb0ea7c54df6013b144c.json"
        )
        digest = "65c4b62ded7f6b0fa878f8e2a5fd72207fca2c3742a28474ade904968544a4da"
        self.assertEqual(json_sha256(transcript_hash_input(row)), digest)
        self.assertEqual(row["content_sha256"], digest)
        self.assertEqual(row["text"], "嗯。" * 22)
        self.assertEqual(
            row["segments"],
            [{"index": 0, "start": 0, "end": 3675000, "text": row["text"]}],
        )
        quality = row["quality"]
        for key in (
            "requires_review",
            "is_fully_human_reviewed",
            "is_subtitle_export_enabled",
        ):
            self.assertIsNone(quality[key])
        assessment = quality["content_assessment"]
        self.assertEqual(assessment["assessed_content_sha256"], digest)
        self.assertEqual(assessment["status"], "filler_only")
        self.assertEqual(assessment["basis"], "stored_text_only")
        self.assertFalse(assessment["source_audio_checked"])
        self.assertFalse(assessment["eligible_as_substantive_transcript"])
        self.assertEqual(assessment["character_count"], len(row["text"]))
        self.assertEqual(assessment["segment_count"], len(row["segments"]))
        self.assertEqual(
            assessment["repeated_unit"] * assessment["repetition_count"], row["text"]
        )


if __name__ == "__main__":
    unittest.main()
