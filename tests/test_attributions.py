"""Segment speaker and viewpoint attribution facts: anchors and strict fields."""

import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from weimingzi_corpus.records import (
    JSON_RECORD_TABLES,
    JSONL_TABLES,
    json_sha256,
    make_record_id,
    transcript_hash_input,
    validate_corpus,
    write_json,
    write_jsonl,
)

PARAGRAPH_TEXT = "我觉得这不是人的问题。"


class AttributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.item = self.make_item("fixture")
        self.other_item = self.make_item("other")
        for table in JSONL_TABLES:
            write_jsonl(
                self.root / "data" / (table + ".jsonl"),
                [self.item, self.other_item] if table == "items" else [],
            )
        for directory in JSON_RECORD_TABLES:
            (self.root / "data" / directory).mkdir()
        transcript = {
            "schema_version": 2,
            "id": make_record_id("t", "fixture"),
            "kind": "transcript",
            "item_id": self.item["id"],
            "method": "asr",
            "model": {"name": "fixture"},
            "language": "zh",
            "text": PARAGRAPH_TEXT,
            "time_unit": "ms",
            "segments": [
                {"index": 0, "start": 100, "end": 1500, "text": PARAGRAPH_TEXT}
            ],
            "quality": {
                "is_fully_human_reviewed": None,
                "requires_review": False,
                "is_subtitle_export_enabled": True,
                "timing_issues": [],
            },
        }
        transcript["content_sha256"] = json_sha256(transcript_hash_input(transcript))
        write_json(
            self.root / "data/transcripts" / (transcript["id"] + ".json"), transcript
        )
        self.edited = self.make_edited_transcript("fixture", self.item["id"])
        self.other_edited = self.make_edited_transcript("other", self.item["id"])
        self.foreign_edited = self.make_edited_transcript(
            "foreign", self.other_item["id"]
        )
        self.attribution = self.make_attribution(self.edited)

    def tearDown(self):
        self.temp.cleanup()

    def make_item(self, name):
        return {
            "schema_version": 2,
            "id": make_record_id("i", ["audio_recording", name]),
            "kind": "audio_recording",
            "title": "测试录音 " + name,
            "identifiers": {"fixture": [name]},
            "urls": [],
            "metadata": {},
            "relations": [],
        }

    def make_edited_transcript(self, name, item_id):
        record = {
            "schema_version": 2,
            "id": make_record_id("r", name),
            "kind": "edited_transcript",
            "item_id": item_id,
            "text": PARAGRAPH_TEXT,
            "paragraphs": [
                {"index": 0, "text": PARAGRAPH_TEXT, "start": 100, "end": 1500}
            ],
            "time_unit": "ms",
            "model": {"name": "fixture"},
            "notes_markdown": "",
            "is_complete": True,
            "transcript_ids": [],
            "quality": {"is_fully_human_reviewed": False, "requires_review": True},
        }
        self.save_edited_transcript(record)
        return record

    def save_edited_transcript(self, record):
        write_json(
            self.root / "data/edited_transcripts" / (record["id"] + ".json"), record
        )

    def make_attribution(self, edited, excerpt=None):
        return {
            "schema_version": 2,
            "kind": "segment_attribution",
            "id": make_record_id("s", [edited["id"], 0, excerpt]),
            "item_id": edited["item_id"],
            "edited_transcript_id": edited["id"],
            "anchor": {
                "paragraph_index": 0,
                "paragraph_text_sha256": hashlib.sha256(
                    PARAGRAPH_TEXT.encode("utf-8")
                ).hexdigest(),
                "excerpt": excerpt,
                "start": 100,
                "end": 1500,
                "time_unit": "ms",
            },
            "speaker_role": "primary_speaker",
            "viewpoint": "own_view",
            "review": {
                "basis": "主讲人/本人观点/整段",
                "reviewer_label": "user_in_this_conversation",
                "reviewed_on": "2026-11-06",
                "review_timezone": "Asia/Hong_Kong",
                "reviewer_reported_watched_original_video": True,
                "assistant_listened_to_audio": False,
            },
            "status": "human_confirmed",
            "urls": ["https://www.bilibili.com/video/BV0000000000/?p=1&t=0"],
        }

    def write_attributions(self, *rows):
        write_jsonl(self.root / "data/attributions.jsonl", list(rows))

    def assert_invalid(self, row, message):
        self.write_attributions(row)
        with self.assertRaisesRegex(ValueError, message):
            validate_corpus(self.root)

    def test_valid_whole_paragraph_and_excerpt_records_are_counted(self):
        excerpt = self.make_attribution(self.edited, excerpt="这不是人的问题")
        excerpt["viewpoint"] = "unknown"
        self.write_attributions(self.attribution, excerpt)
        counts = validate_corpus(self.root)
        self.assertEqual(counts["attributions"], 2)
        self.assertEqual(counts["attributions_primary_speaker_own_view"], 1)

    def test_empty_table_reports_zero(self):
        counts = validate_corpus(self.root)
        self.assertEqual(counts["attributions"], 0)
        self.assertEqual(counts["attributions_primary_speaker_own_view"], 0)

    def test_changed_paragraph_text_invalidates_attribution(self):
        self.write_attributions(self.attribution)
        changed = copy.deepcopy(self.edited)
        changed["paragraphs"][0]["text"] = "改过的段落。"
        self.save_edited_transcript(changed)
        with self.assertRaisesRegex(ValueError, "paragraph text hash mismatch"):
            validate_corpus(self.root)

    def test_excerpt_must_be_in_paragraph(self):
        row = self.make_attribution(self.edited, excerpt="段落里没有这句")
        self.assert_invalid(row, "excerpt not found")

    def test_position_must_equal_paragraph(self):
        row = copy.deepcopy(self.attribution)
        row["anchor"]["end"] = 1600
        self.assert_invalid(row, "start/end/time_unit differ")

    def test_paragraph_index_out_of_range(self):
        row = copy.deepcopy(self.attribution)
        row["anchor"]["paragraph_index"] = 3
        self.assert_invalid(row, "paragraph_index out of range")

    def test_edited_transcript_of_another_item_fails(self):
        row = copy.deepcopy(self.attribution)
        row["edited_transcript_id"] = self.foreign_edited["id"]
        self.assert_invalid(row, "belongs to a different item")

    def test_missing_edited_transcript_fails(self):
        row = copy.deepcopy(self.attribution)
        row["edited_transcript_id"] = make_record_id("r", "missing")
        self.assert_invalid(row, "unresolved edited_transcripts")

    def test_enums_and_status_are_closed(self):
        for field, value, message in (
            ("speaker_role", "未明子", "invalid speaker_role"),
            ("viewpoint", "self_speech", "invalid viewpoint"),
            ("status", "model_suggested", "status must be human_confirmed"),
        ):
            with self.subTest(field=field):
                row = copy.deepcopy(self.attribution)
                row[field] = value
                self.assert_invalid(row, message)

    def test_unknown_keys_are_rejected(self):
        row = copy.deepcopy(self.attribution)
        row["confidence"] = 0.9
        self.assert_invalid(row, "attribution keys unknown")
        row = copy.deepcopy(self.attribution)
        row["review"]["model"] = "fixture"
        self.assert_invalid(row, "review keys unknown")

    def test_review_fields_are_typed(self):
        for field, value, message in (
            ("reviewed_on", "2026-13-01", "reviewed_on"),
            ("reviewed_on", "2026/11/06", "reviewed_on"),
            ("review_timezone", "UTC", "review_timezone"),
            ("basis", " ", "basis"),
            ("reviewer_reported_watched_original_video", "yes", "boolean"),
        ):
            with self.subTest(field=field, value=value):
                row = copy.deepcopy(self.attribution)
                row["review"][field] = value
                self.assert_invalid(row, message)

    def test_id_prefix_is_required(self):
        row = copy.deepcopy(self.attribution)
        row["id"] = make_record_id("a", "attribution")
        self.assert_invalid(row, "prefix s-")

    def test_duplicate_range_is_rejected(self):
        duplicate = copy.deepcopy(self.attribution)
        duplicate["id"] = make_record_id("s", "duplicate")
        self.write_attributions(self.attribution, duplicate)
        with self.assertRaisesRegex(ValueError, "duplicate attribution"):
            validate_corpus(self.root)


if __name__ == "__main__":
    unittest.main()
