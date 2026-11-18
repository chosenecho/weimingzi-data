"""Evidence layers derive from native input edges without merging source identities."""
from pathlib import Path
import tempfile
import unittest

from native_fixtures import fixture_records, rid, write_corpus
from weimingzi_corpus.coverage import CoverageIndex, coverage_jsonl, text_status
from weimingzi_corpus.records import document_hash_input, json_sha256, validate_corpus


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.records = fixture_records()

    def add_item(self, name, **extra):
        row = {"id": rid(name), "kind": "audio_recording", "title": name, "identifiers": {}, "metadata": {}, **extra}
        self.records["items"].append(row)
        return row["id"]

    def add_transcript(self, name, owner, text="另一文本"):
        row = {"id": rid(name, "t"), "kind": "transcript", "inputs": [{"role": "item", "target_id": owner}], "method": "asr_cloud", "time_unit": "ms", "text": text, "blocks": [{"literal": text, "start": 0, "end": 1000}], "quality": {}}
        row["content_sha256"] = json_sha256(document_hash_input(row))
        self.records["documents"].append(row)
        return row

    def index(self):
        write_corpus(self.root, self.records)
        validate_corpus(self.root)
        return CoverageIndex(self.root)

    def test_native_include_records_and_unknown_quality_preserved(self):
        report = self.index().report("BVfixture", part=1, include_records=True)
        self.assertEqual(report["item_id"], rid("part"))
        rows = report["layers"]["direct"]["records"]
        self.assertEqual(len(rows), 3)
        raw = next(row for row in rows if row["kind"] == "transcript")
        self.assertIsNone(raw["is_fully_human_reviewed"])
        self.assertEqual(raw["record"], self.records["documents"][0])
        self.assertIn("inputs", raw["record"])
        self.assertNotIn("segments", raw["record"])
        self.assertEqual(report["summary"]["direct"]["human_reviewed_complete_texts"], 0)
        self.assertEqual(len(coverage_jsonl(report).splitlines()), 3)

    def test_parent_expands_parts_but_part_does_not_expand_siblings(self):
        sibling = self.add_item("sibling", kind="video_part", parent_id=rid("video"), part_number=2)
        self.add_transcript("sibling", sibling)
        index = self.index()
        self.assertEqual(index.report(rid("video"))["scope_item_ids"], sorted([rid("video"), rid("part"), sibling]))
        self.assertEqual(index.report(rid("part"))["scope_item_ids"], [rid("part")])
        self.assertEqual(index.report("BVfixture", part=2)["item_id"], sibling)
        with self.assertRaises(ValueError):
            index.resolve("BVfixture", part=0)

    def test_four_layers_keep_explicit_association_and_audio_evidence_distinct(self):
        cross = self.add_item("cross", relations=[{"kind": "references_video", "target_item_id": rid("video"), "evidence": "明确引用"}])
        same = self.add_item("same", identifiers={"audio_sha256": ["a" * 64]})
        supplement = self.add_item("supplement", relations=[{"kind": "chapter_supplement_not_audio_identity", "target_item_id": rid("part"), "evidence": "章节补充"}])
        for name, owner in (("cross", cross), ("same", same), ("supplement", supplement)):
            self.add_transcript(name, owner)
        report = self.index().report(rid("part"))
        for layer, owner in (("cross_source", cross), ("same_audio", same), ("chapter_supplement", supplement)):
            self.assertEqual({row["item_id"] for row in report["layers"][layer]["records"]}, {owner})
        audio = report["layers"]["same_audio"]["records"][0]["associations"][0]
        self.assertTrue(audio["proves_audio_identity"])
        self.assertIn(self.records["assets"][0]["id"], {entry.get("asset_id") for entry in audio["evidence"]})
        for layer in ("cross_source", "chapter_supplement"):
            self.assertFalse(report["layers"][layer]["records"][0]["associations"][0]["proves_audio_identity"])
        reverse = self.index().report(cross)
        self.assertTrue(reverse["layers"]["cross_source"]["records"])

    def test_variants_and_literal_screening_do_not_infer_silence_or_review(self):
        self.add_transcript("empty", rid("part"), " … ")
        self.add_transcript("filler", rid("part"), "嗯，呃！")
        self.add_transcript("variant", rid("part"), "真实不同结果")
        report = self.index().report(rid("part"))
        counts = report["summary"]["direct"]
        self.assertEqual(counts["transcripts"], 4)
        self.assertEqual(counts["text_present_transcripts"], 2)
        self.assertEqual(counts["filler_only_transcripts"], 1)
        self.assertEqual(counts["empty_transcripts"], 1)
        self.assertEqual(counts["complete_text_candidates"], 2)
        self.assertEqual(counts["human_reviewed_complete_texts"], 0)
        self.assertEqual(text_status(""), "empty")
        self.assertNotIn("silent_audio_confirmed", str(report))

    def test_audio_assets_with_equal_sha_are_native_identity_evidence(self):
        same = self.add_item("same")
        self.records["assets"][0]["inputs"].append({"role": "item", "target_id": same})
        self.add_transcript("same", same)
        index = self.index()
        report = index.report(rid("part"))
        self.assertEqual(len(report["layers"]["same_audio"]["records"]), 1)
        self.assertEqual(index.resolve("BVfixture"), rid("video"))
        self.assertEqual(len(index.collections), 1)


if __name__ == "__main__":
    unittest.main()
