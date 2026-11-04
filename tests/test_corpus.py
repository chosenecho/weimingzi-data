"""Data semantics, references, lossless exports and isolated imports."""

import copy
import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from weimingzi_corpus.cli import import_record, output_path
from weimingzi_corpus.data import (
    DIRECTORIES,
    TABLES,
    fingerprint,
    identifier,
    read_json,
    records,
    timing_issues,
    transcript_identity,
    validate,
    write_json,
    write_jsonl,
)
from weimingzi_corpus.exports import catalog, navigation, sqlite_export, subtitle


class CorpusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.item = {
            "schema_version": 1,
            "id": identifier("i", ["recording", "fixture"]),
            "kind": "recording",
            "title": "测试录音",
            "identifiers": {"fixture": ["one"]},
            "urls": [],
            "attributes": {},
            "relations": [],
        }
        for table in TABLES:
            write_jsonl(
                self.root / "data" / (table + ".jsonl"),
                [self.item] if table == "items" else [],
            )
        for directory in DIRECTORIES:
            (self.root / "data" / directory).mkdir()
        write_json(
            self.root / "selections/training.json", {"schema_version": 1, "entries": []}
        )
        self.transcript = {
            "schema_version": 1,
            "id": identifier("t", "fixture"),
            "kind": "transcript",
            "item_id": self.item["id"],
            "method": "asr",
            "model": "fixture",
            "language": "zh",
            "text": "物质世界。",
            "time_unit": "ms",
            "segments": [
                {"ordinal": 0, "start": 100, "end": 1500, "text": "物质世界。"}
            ],
            "quality": {
                "human_reviewed": None,
                "requires_review": False,
                "timed_exports_available": True,
                "timing_issues": [],
            },
        }
        self.save_transcript()

    def tearDown(self):
        self.temp.cleanup()

    def save_transcript(self):
        self.transcript["content_sha256"] = fingerprint(
            transcript_identity(self.transcript)
        )
        write_json(
            self.root / "data/transcripts" / (self.transcript["id"] + ".json"),
            self.transcript,
        )

    def test_complete_minimal_corpus_and_unknown_review_status(self):
        self.assertEqual(validate(self.root)["transcripts"], 1)
        saved = next(records(self.root, "transcripts"))[0]
        self.assertIsNone(saved["quality"]["human_reviewed"])
        self.assertIs(saved["quality"]["requires_review"], False)

    def test_changed_content_requires_new_integrity_digest(self):
        path = self.root / "data/transcripts" / (self.transcript["id"] + ".json")
        changed = read_json(path)
        changed["text"] = "改过的正文"
        write_json(path, changed)
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            validate(self.root)

    def test_bad_timing_is_preserved_and_cannot_be_exported(self):
        self.transcript["segments"].append(
            {"ordinal": 1, "start": 50, "end": 300, "text": "倒退时间"}
        )
        self.transcript["quality"]["timing_issues"] = timing_issues(self.transcript)
        self.save_transcript()
        self.assertEqual(validate(self.root)["timing_issue_transcripts"], 1)
        with self.assertRaisesRegex(ValueError, "starts must not decrease"):
            subtitle(self.transcript, "vtt")
        self.assertEqual(self.transcript["segments"][1]["start"], 50)

    def test_unreported_timing_problem_fails_validation(self):
        self.transcript["segments"][0]["end"] = 0
        self.save_transcript()
        with self.assertRaisesRegex(ValueError, "timing issue list"):
            validate(self.root)

    def test_subtitles_preserve_exact_milliseconds(self):
        self.assertIn("00:00:00,100 --> 00:00:01,500", subtitle(self.transcript, "srt"))
        self.transcript["time_unit"] = "s"
        self.transcript["segments"][0].update(start=0.1, end=1.5)
        self.assertIn("00:00:00.100 --> 00:00:01.500", subtitle(self.transcript, "vtt"))

    def test_submillisecond_values_are_not_rounded(self):
        self.transcript["time_unit"] = "s"
        self.transcript["segments"][0].update(start=0.0001, end=1.5)
        with self.assertRaisesRegex(ValueError, "millisecond precision"):
            subtitle(self.transcript, "srt")
        self.assertEqual(self.transcript["segments"][0]["start"], 0.0001)

    def test_explicit_disabled_timed_export_is_respected(self):
        self.transcript["quality"]["timed_exports_available"] = False
        with self.assertRaisesRegex(ValueError, "disables"):
            subtitle(self.transcript, "vtt")

    def test_result_must_reference_existing_item(self):
        self.transcript["item_id"] = identifier("i", "missing")
        self.save_transcript()
        with self.assertRaisesRegex(ValueError, "unresolved items"):
            validate(self.root)

    def test_parent_cycle_is_rejected(self):
        self.item["parent_id"] = self.item["id"]
        write_jsonl(self.root / "data/items.jsonl", [self.item])
        with self.assertRaisesRegex(ValueError, "parent cycle"):
            validate(self.root)

    def test_boolean_review_flags_cannot_be_strings(self):
        self.transcript["quality"]["human_reviewed"] = "false"
        self.save_transcript()
        with self.assertRaisesRegex(ValueError, "boolean or null"):
            validate(self.root)

    def reading(self):
        r = {
            "schema_version": 1,
            "id": identifier("r", "fixture"),
            "kind": "reading",
            "item_id": self.item["id"],
            "text": "物质世界。",
            "paragraphs": [{"ordinal": 0, "text": "物质世界。"}],
            "time_unit": "ms",
            "model": "fixture",
            "notes": "",
            "complete": True,
            "transcript_ids": [self.transcript["id"]],
            "quality": {"human_reviewed": False, "requires_review": True},
        }
        write_json(self.root / "data/readings" / (r["id"] + ".json"), r)
        return r

    def test_training_selection_does_not_grant_review_approval(self):
        r = self.reading()
        write_json(
            self.root / "selections/training.json",
            {
                "entries": [
                    {
                        "item_id": self.item["id"],
                        "reading_id": r["id"],
                        "annotation_ids": [],
                    }
                ]
            },
        )
        self.assertEqual(validate(self.root)["training_entries"], 1)
        self.assertIs(
            read_json(self.root / "data/readings" / (r["id"] + ".json"))["quality"][
                "human_reviewed"
            ],
            False,
        )

    def test_training_selection_cannot_reference_another_item(self):
        r = self.reading()
        write_json(
            self.root / "selections/training.json",
            {
                "entries": [
                    {"item_id": identifier("i", "missing"), "reading_id": r["id"]}
                ]
            },
        )
        with self.assertRaisesRegex(ValueError, "training entry"):
            validate(self.root)

    def test_confirmation_is_located_by_original_text_hash(self):
        r = self.reading()
        text = "物质世界。"
        digest = hashlib.sha256(text.encode()).hexdigest()
        a = {
            "schema_version": 1,
            "id": identifier("a", "confirmation"),
            "kind": "confirmation",
            "item_id": self.item["id"],
            "reading_ids": [r["id"]],
            "scope": "wording_only",
            "anchor": {"original_text": text, "original_text_sha256": digest},
            "corrected_text": text,
            "corrected_text_sha256": digest,
        }
        write_jsonl(self.root / "data/annotations.jsonl", [a])
        self.assertEqual(validate(self.root)["annotations"], 1)
        a["anchor"]["original_text_sha256"] = "0" * 64
        write_jsonl(self.root / "data/annotations.jsonl", [a])
        with self.assertRaisesRegex(ValueError, "anchor hash"):
            validate(self.root)

    def test_canonical_import_is_idempotent(self):
        source = self.root / "incoming.json"
        write_json(source, self.item)
        self.assertEqual(import_record(self.root, "items", source), 0)

    def test_invalid_import_does_not_change_primary_files(self):
        r = self.reading()
        existing = self.root / "data/items.jsonl"
        before = existing.read_bytes()
        r["id"] = identifier("r", "new")
        r["item_id"] = identifier("i", "missing")
        source = self.root / "incoming.json"
        write_json(source, r)
        with self.assertRaisesRegex(ValueError, "unresolved items"):
            import_record(self.root, "readings", source)
        self.assertEqual(existing.read_bytes(), before)
        self.assertFalse((self.root / "data/readings" / (r["id"] + ".json")).exists())

    def test_valid_import_adds_one_record(self):
        new = copy.deepcopy(self.item)
        new["id"] = identifier("i", "new")
        new["identifiers"] = {"fixture": ["two"]}
        source = self.root / "incoming.json"
        write_json(source, new)
        self.assertEqual(import_record(self.root, "items", source), 1)
        self.assertEqual(validate(self.root)["items"], 2)

    def test_conflicting_id_import_does_not_overwrite(self):
        modified = copy.deepcopy(self.item)
        modified["title"] = "其他标题"
        source = self.root / "incoming.json"
        write_json(source, modified)
        with self.assertRaisesRegex(ValueError, "overwrite"):
            import_record(self.root, "items", source)
        self.assertEqual(next(records(self.root, "items"))[0]["title"], "测试录音")

    def test_exports_cannot_overwrite_primary_data(self):
        for target in [
            "data/items.jsonl",
            "docs/INDEX.md",
            ".git/config",
            "src/main.py",
        ]:
            with self.subTest(target=target), self.assertRaises(ValueError):
                output_path(self.root, str(self.root / target))

    def test_sqlite_projection_retains_records_and_searches_chinese(self):
        self.reading()
        output = self.root / ".cache/search.sqlite3"
        sqlite_export(self.root, output)
        c = sqlite3.connect(output)
        try:
            self.assertEqual(
                c.execute("select count(*) from transcripts").fetchone()[0], 1
            )
            self.assertEqual(
                c.execute("select count(*) from readings").fetchone()[0], 1
            )
            self.assertEqual(
                c.execute(
                    "select count(*) from search where search match ?", ('"物质世界"',)
                ).fetchone()[0],
                2,
            )
            self.assertEqual(
                json.loads(c.execute("select data from transcripts").fetchone()[0]),
                self.transcript,
            )
        finally:
            c.close()

    def test_word_alignment_tampering_fails_validation(self):
        self.transcript["alignments"] = [
            {
                "id": identifier("x", "word"),
                "time_unit": "ms",
                "sentences": [
                    {"words": [{"text": "物质", "begin_time": 100, "end_time": 400}]}
                ],
            }
        ]
        self.transcript["alignments_sha256"] = fingerprint(
            self.transcript["alignments"]
        )
        self.save_transcript()
        self.assertEqual(validate(self.root)["transcripts"], 1)
        self.transcript["alignments"][0]["sentences"][0]["words"][0]["end_time"] = 700
        self.save_transcript()
        with self.assertRaisesRegex(ValueError, "alignment SHA-256"):
            validate(self.root)

    def test_reading_derivation_cycle_fails_validation(self):
        r = self.reading()
        r["derived_from"] = r["id"]
        write_json(self.root / "data/readings" / (r["id"] + ".json"), r)
        with self.assertRaisesRegex(ValueError, "reading parent cycle"):
            validate(self.root)

    def test_missing_input_unit_reference_fails_validation(self):
        r = self.reading()
        r["reference_units_reading_id"] = identifier("r", "missing")
        write_json(self.root / "data/readings" / (r["id"] + ".json"), r)
        with self.assertRaisesRegex(ValueError, "unresolved readings"):
            validate(self.root)

    def test_gap_evidence_cannot_reference_a_missing_alignment(self):
        self.transcript["attributes"] = {
            "untranscribed_intervals": [
                [
                    {
                        "evidence": [
                            {
                                "transcript_id": self.transcript["id"],
                                "alignment_ids": [identifier("x", "missing")],
                            }
                        ]
                    }
                ]
            ]
        }
        self.save_transcript()
        with self.assertRaisesRegex(ValueError, "unresolved alignment evidence"):
            validate(self.root)

    def test_catalog_and_navigation_derive_from_same_records(self):
        self.reading()
        self.assertIn(self.transcript["id"], catalog(self.root))
        navigation(self.root)
        navigation(self.root, check=True)
        (self.root / "docs/INDEX.md").write_text("stale", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "stale"):
            navigation(self.root, check=True)


if __name__ == "__main__":
    unittest.main()
