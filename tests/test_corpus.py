"""Data semantics, references, lossless exports and isolated imports."""

import copy
import hashlib
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing, redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from weimingzi_corpus.cli import import_records, main, validate_export_path
from weimingzi_corpus.records import (
    JSON_RECORD_TABLES,
    JSONL_TABLES,
    json_sha256,
    make_record_id,
    read_json,
    iter_records,
    find_timestamp_issues,
    transcript_hash_input,
    validate_corpus,
    write_json,
    write_jsonl,
)
from weimingzi_corpus.exports import (
    render_catalog_csv,
    generate_catalog_docs,
    export_sqlite,
    render_subtitles,
    render_review_markdown,
    iter_review_issues,
)


class CorpusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.item = {
            "schema_version": 2,
            "id": make_record_id("i", ["audio_recording", "fixture"]),
            "kind": "audio_recording",
            "title": "测试录音",
            "identifiers": {"fixture": ["one"]},
            "urls": [],
            "metadata": {},
            "relations": [],
        }
        for table in JSONL_TABLES:
            write_jsonl(
                self.root / "data" / (table + ".jsonl"),
                [self.item] if table == "items" else [],
            )
        for directory in JSON_RECORD_TABLES:
            (self.root / "data" / directory).mkdir()
        self.transcript = {
            "schema_version": 2,
            "id": make_record_id("t", "fixture"),
            "kind": "transcript",
            "item_id": self.item["id"],
            "method": "asr",
            "model": {"name": "fixture"},
            "language": "zh",
            "text": "物质世界。",
            "time_unit": "ms",
            "segments": [{"index": 0, "start": 100, "end": 1500, "text": "物质世界。"}],
            "quality": {
                "is_fully_human_reviewed": None,
                "requires_review": False,
                "is_subtitle_export_enabled": True,
                "timing_issues": [],
            },
        }
        self.save_transcript()

    def tearDown(self):
        self.temp.cleanup()

    def save_transcript(self):
        self.transcript["content_sha256"] = json_sha256(
            transcript_hash_input(self.transcript)
        )
        write_json(
            self.root / "data/transcripts" / (self.transcript["id"] + ".json"),
            self.transcript,
        )

    def test_v3_sqlite_has_four_native_tables_and_lossless_search_text(self):
        from weimingzi_corpus.schema_v3 import write_legacy_dataset

        tables = {
            table: [row for row, _ in iter_records(self.root, table)]
            for table in (*JSONL_TABLES, *JSON_RECORD_TABLES)
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_legacy_dataset(root, tables)
            output = root / "search.sqlite3"
            export_sqlite(root, output)
            with closing(sqlite3.connect(output)) as connection:
                names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                self.assertTrue({"items", "documents", "assets", "annotations"} <= names)
                self.assertTrue(set(JSON_RECORD_TABLES).isdisjoint(names))
                native = json.loads(connection.execute("SELECT record_json FROM documents").fetchone()[0])
                self.assertEqual(native["text"], self.transcript["text"])
                self.assertIn("range", native["blocks"][0])
                self.assertNotIn("segments", native)
                self.assertEqual(connection.execute("SELECT text FROM content_search").fetchone()[0], self.transcript["text"])

    def test_v3_navigation_review_and_coverage_use_native_paths(self):
        from weimingzi_corpus.coverage import CoverageIndex
        from weimingzi_corpus.schema_v3 import write_legacy_dataset

        edited = self.create_edited_transcript()
        edited["paragraphs"][0]["issues"] = [{"note": "按原文回查", "candidate": ""}]
        write_json(self.root / "data/edited_transcripts" / (edited["id"] + ".json"), edited)
        tables = {
            table: [row for row, _ in iter_records(self.root, table)]
            for table in (*JSONL_TABLES, *JSON_RECORD_TABLES)
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_legacy_dataset(root, tables)
            csv_text = render_catalog_csv(root)
            self.assertIn(f"data/documents/{edited['id']}.json", csv_text)
            self.assertNotIn("data/edited_transcripts/", csv_text)
            issue = next(iter_review_issues(edited, root))
            self.assertEqual(issue["record_path"], f"data/documents/{edited['id']}.json")
            self.assertEqual(issue["issue"], edited["paragraphs"][0]["issues"][0])
            generate_catalog_docs(root)
            links = (root / "docs/catalog/reviews.md").read_text(encoding="utf-8")
            self.assertIn(f"../../data/documents/{edited['id']}.json", links)
            report = CoverageIndex(root).report(self.item["id"], include_records=True)
            records = {row["id"]: row for row in report["layers"]["direct"]["records"]}
            self.assertEqual(records[edited["id"]]["record"], edited)
            self.assertEqual(records[edited["id"]]["record_path"], f"data/documents/{edited['id']}.json")

    def test_complete_minimal_corpus_and_unknown_review_status(self):
        self.assertEqual(validate_corpus(self.root)["transcripts"], 1)
        saved = next(iter_records(self.root, "transcripts"))[0]
        self.assertIsNone(saved["quality"]["is_fully_human_reviewed"])
        self.assertIs(saved["quality"]["requires_review"], False)

    def test_changed_content_requires_new_integrity_digest(self):
        path = self.root / "data/transcripts" / (self.transcript["id"] + ".json")
        changed = read_json(path)
        changed["text"] = "改过的正文"
        write_json(path, changed)
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            validate_corpus(self.root)

    def test_bad_timing_is_preserved_and_cannot_be_exported(self):
        self.transcript["segments"].append(
            {"index": 1, "start": 50, "end": 300, "text": "倒退时间"}
        )
        self.transcript["quality"]["timing_issues"] = find_timestamp_issues(
            self.transcript
        )
        self.save_transcript()
        self.assertEqual(validate_corpus(self.root)["timing_issue_transcripts"], 1)
        with self.assertRaisesRegex(ValueError, "starts must not decrease"):
            render_subtitles(self.transcript, "vtt")
        self.assertEqual(self.transcript["segments"][1]["start"], 50)

    def test_unreported_timing_problem_fails_validation(self):
        self.transcript["segments"][0]["end"] = 0
        self.save_transcript()
        with self.assertRaisesRegex(ValueError, "timing issue list"):
            validate_corpus(self.root)

    def test_subtitles_preserve_exact_milliseconds(self):
        self.assertIn(
            "00:00:00,100 --> 00:00:01,500", render_subtitles(self.transcript, "srt")
        )
        self.transcript["time_unit"] = "s"
        self.transcript["segments"][0].update(start=0.1, end=1.5)
        self.assertIn(
            "00:00:00.100 --> 00:00:01.500", render_subtitles(self.transcript, "vtt")
        )

    def test_submillisecond_values_are_not_rounded(self):
        self.transcript["time_unit"] = "s"
        self.transcript["segments"][0].update(start=0.0001, end=1.5)
        with self.assertRaisesRegex(ValueError, "millisecond precision"):
            render_subtitles(self.transcript, "srt")
        self.assertEqual(self.transcript["segments"][0]["start"], 0.0001)

    def test_explicit_disabled_timed_export_is_respected(self):
        self.transcript["quality"]["is_subtitle_export_enabled"] = False
        with self.assertRaisesRegex(ValueError, "disables"):
            render_subtitles(self.transcript, "vtt")

    def test_result_must_reference_existing_item(self):
        self.transcript["item_id"] = make_record_id("i", "missing")
        self.save_transcript()
        with self.assertRaisesRegex(ValueError, "unresolved items"):
            validate_corpus(self.root)

    def test_parent_cycle_is_rejected(self):
        self.item["parent_id"] = self.item["id"]
        write_jsonl(self.root / "data/items.jsonl", [self.item])
        with self.assertRaisesRegex(ValueError, "parent cycle"):
            validate_corpus(self.root)

    def test_boolean_review_flags_cannot_be_strings(self):
        self.transcript["quality"]["is_fully_human_reviewed"] = "false"
        self.save_transcript()
        with self.assertRaisesRegex(ValueError, "boolean or null"):
            validate_corpus(self.root)

    def create_edited_transcript(self):
        r = {
            "schema_version": 2,
            "id": make_record_id("r", "fixture"),
            "kind": "edited_transcript",
            "item_id": self.item["id"],
            "text": "物质世界。",
            "paragraphs": [{"index": 0, "text": "物质世界。"}],
            "time_unit": "ms",
            "model": {"name": "fixture"},
            "notes_markdown": "",
            "is_complete": True,
            "transcript_ids": [self.transcript["id"]],
            "quality": {"is_fully_human_reviewed": False, "requires_review": True},
        }
        write_json(self.root / "data/edited_transcripts" / (r["id"] + ".json"), r)
        return r

    def create_confirmation(self, edited):
        text = edited["paragraphs"][0]["text"]
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        confirmation = {
            "schema_version": 2,
            "id": make_record_id("a", "confirmation"),
            "kind": "confirmation",
            "item_id": self.item["id"],
            "edited_transcript_ids": [edited["id"]],
            "scope": "local_text_or_term",
            "anchor": {"original_text": text, "original_text_sha256": digest},
            "corrected_text": text,
            "corrected_text_sha256": digest,
        }
        write_jsonl(self.root / "data/confirmations.jsonl", [confirmation])
        return confirmation

    def test_local_confirmation_preserves_unknown_or_partial_review_status(self):
        edited = self.create_edited_transcript()
        self.create_confirmation(edited)
        self.assertEqual(validate_corpus(self.root)["confirmations"], 1)
        self.assertEqual(
            read_json(self.root / "data/edited_transcripts" / (edited["id"] + ".json"))[
                "quality"
            ],
            {"is_fully_human_reviewed": False, "requires_review": True},
        )
        self.assertIsNone(
            read_json(self.root / "data/transcripts" / (self.transcript["id"] + ".json"))[
                "quality"
            ]["is_fully_human_reviewed"]
        )

    def test_confirmation_is_located_by_original_text_hash(self):
        r = self.create_edited_transcript()
        text = "物质世界。"
        text_sha256 = hashlib.sha256(text.encode()).hexdigest()
        a = {
            "schema_version": 2,
            "id": make_record_id("a", "confirmation"),
            "kind": "confirmation",
            "item_id": self.item["id"],
            "edited_transcript_ids": [r["id"]],
            "scope": "local_text_or_term",
            "anchor": {"original_text": text, "original_text_sha256": text_sha256},
            "corrected_text": text,
            "corrected_text_sha256": text_sha256,
        }
        write_jsonl(self.root / "data/confirmations.jsonl", [a])
        self.assertEqual(validate_corpus(self.root)["confirmations"], 1)
        a["anchor"]["original_text_sha256"] = "0" * 64
        write_jsonl(self.root / "data/confirmations.jsonl", [a])
        with self.assertRaisesRegex(ValueError, "anchor hash"):
            validate_corpus(self.root)

    def test_confirmation_references_and_text_anchor_remain_required(self):
        edited = self.create_edited_transcript()
        original = self.create_confirmation(edited)
        for changes, message in (
            ({"edited_transcript_ids": []}, "no edited transcript anchor"),
            (
                {"edited_transcript_ids": [make_record_id("r", "missing")]},
                "unresolved edited_transcripts",
            ),
            ({"item_id": make_record_id("i", "missing")}, "unresolved items"),
            ({"corrected_text_sha256": "0" * 64}, "corrected text hash"),
            (
                {
                    "anchor": {
                        "original_text": "未出现的原文",
                        "original_text_sha256": hashlib.sha256(
                            "未出现的原文".encode("utf-8")
                        ).hexdigest(),
                    },
                    "corrected_text": "未出现的修订",
                    "corrected_text_sha256": hashlib.sha256(
                        "未出现的修订".encode("utf-8")
                    ).hexdigest(),
                },
                "confirmation text cannot be located",
            ),
        ):
            with self.subTest(changes=changes):
                row = copy.deepcopy(original)
                row.update(changes)
                write_jsonl(self.root / "data/confirmations.jsonl", [row])
                with self.assertRaisesRegex(ValueError, message):
                    validate_corpus(self.root)

    def test_validation_ignores_optional_projection_configuration(self):
        expected = validate_corpus(self.root)
        self.assertFalse((self.root / "selections").exists())
        for name in (
            "training_entries", "release_items", "release_transcripts",
            "release_paragraphs", "topics", "topic_entries",
        ):
            self.assertNotIn(name, expected)
        for raw in ("{broken json", '{"schema_version": -1, "entries": [null]}'):
            with self.subTest(raw=raw):
                for name in ("training", "release", "topics"):
                    path = self.root / "selections" / (name + ".json")
                    path.parent.mkdir(exist_ok=True)
                    path.write_text(raw, encoding="utf-8")
                self.assertEqual(validate_corpus(self.root), expected)

    def test_import_ignores_broken_optional_projection_configuration(self):
        for name in ("training", "release", "topics"):
            path = self.root / "selections" / (name + ".json")
            path.parent.mkdir(exist_ok=True)
            path.write_text("{broken json", encoding="utf-8")
        new = copy.deepcopy(self.item)
        new["id"] = make_record_id("i", "new")
        new["identifiers"] = {"fixture": ["two"]}
        source = self.root / "incoming.json"
        write_json(source, new)
        self.assertEqual(import_records(self.root, "items", source), 1)
        self.assertEqual(validate_corpus(self.root)["items"], 2)
        invalid = copy.deepcopy(self.transcript)
        invalid["id"] = make_record_id("t", "missing-item")
        invalid["item_id"] = make_record_id("i", "missing")
        invalid["content_sha256"] = json_sha256(transcript_hash_input(invalid))
        write_json(source, invalid)
        before = (self.root / "data/items.jsonl").read_bytes()
        with self.assertRaisesRegex(ValueError, "unresolved items"):
            import_records(self.root, "transcripts", source)
        self.assertEqual((self.root / "data/items.jsonl").read_bytes(), before)
        self.assertEqual(len(list(iter_records(self.root, "transcripts"))), 1)
        for path in (self.root / "selections").iterdir():
            self.assertEqual(path.read_text(encoding="utf-8"), "{broken json")

    def test_canonical_import_is_idempotent(self):
        source = self.root / "incoming.json"
        write_json(source, self.item)
        self.assertEqual(import_records(self.root, "items", source), 0)

    def test_invalid_import_does_not_change_primary_files(self):
        r = self.create_edited_transcript()
        existing = self.root / "data/items.jsonl"
        before = existing.read_bytes()
        r["id"] = make_record_id("r", "new")
        r["item_id"] = make_record_id("i", "missing")
        source = self.root / "incoming.json"
        write_json(source, r)
        with self.assertRaisesRegex(ValueError, "unresolved items"):
            import_records(self.root, "edited_transcripts", source)
        self.assertEqual(existing.read_bytes(), before)
        self.assertFalse(
            (self.root / "data/edited_transcripts" / (r["id"] + ".json")).exists()
        )

    def test_valid_import_adds_one_record(self):
        new = copy.deepcopy(self.item)
        new["id"] = make_record_id("i", "new")
        new["identifiers"] = {"fixture": ["two"]}
        source = self.root / "incoming.json"
        write_json(source, new)
        self.assertEqual(import_records(self.root, "items", source), 1)
        self.assertEqual(validate_corpus(self.root)["items"], 2)

    def test_conflicting_id_import_does_not_overwrite(self):
        modified = copy.deepcopy(self.item)
        modified["title"] = "其他标题"
        source = self.root / "incoming.json"
        write_json(source, modified)
        with self.assertRaisesRegex(ValueError, "overwrite"):
            import_records(self.root, "items", source)
        self.assertEqual(next(iter_records(self.root, "items"))[0]["title"], "测试录音")

    def test_exports_cannot_overwrite_primary_data(self):
        for target in [
            "data/items.jsonl",
            "docs/INDEX.md",
            ".git/config",
            "src/main.py",
        ]:
            with self.subTest(target=target), self.assertRaises(ValueError):
                validate_export_path(self.root, str(self.root / target))

    def create_sqlite_records(self):
        edited = self.create_edited_transcript()
        self.create_confirmation(edited)
        write_jsonl(
            self.root / "data/collections.jsonl",
            [{
                "schema_version": 2,
                "id": make_record_id("c", "fixture"),
                "kind": "video_series",
                "title": "测试集合",
                "members": [{"item_id": self.item["id"], "position": 1}],
            }],
        )
        write_jsonl(
            self.root / "data/audio.jsonl",
            [{
                "schema_version": 2,
                "id": make_record_id("a", "audio"),
                "kind": "audio",
                "sha256": "a" * 64,
                "availability": "unavailable",
                "item_ids": [self.item["id"]],
            }],
        )
        write_jsonl(
            self.root / "data/attributions.jsonl",
            [{
                "schema_version": 2,
                "id": make_record_id("s", "fixture"),
                "kind": "segment_attribution",
                "item_id": self.item["id"],
                "edited_transcript_id": edited["id"],
                "anchor": {
                    "paragraph_index": 0,
                    "paragraph_text_sha256": hashlib.sha256(
                        edited["text"].encode("utf-8")
                    ).hexdigest(),
                    "excerpt": None,
                    "start": None,
                    "end": None,
                    "time_unit": "ms",
                },
                "speaker_role": "primary_speaker",
                "viewpoint": "own_view",
                "review": {
                    "basis": "测试人工归属记录",
                    "reviewer_label": "fixture",
                    "reviewed_on": "2026-11-06",
                    "review_timezone": "Asia/Hong_Kong",
                    "reviewer_reported_watched_original_video": True,
                    "assistant_listened_to_audio": False,
                },
                "status": "human_confirmed",
                "urls": [],
            }],
        )
        for table, prefix, kind, content in (
            ("posts", "p", "post", {"content": {"text": "动态正文"}}),
            ("articles", "w", "article", {"text": "文章正文"}),
        ):
            row = {
                "schema_version": 2,
                "id": make_record_id(prefix, table),
                "kind": kind,
                "item_id": self.item["id"],
                "quality": {"is_fully_human_reviewed": None, "requires_review": False},
                **content,
            }
            write_json(self.root / "data" / table / (row["id"] + ".json"), row)
        validate_corpus(self.root)

    def assert_sqlite_records(self, output):
        with closing(sqlite3.connect(output)) as connection:
            tables = {
                row[0]
                for row in connection.execute("select name from sqlite_master where type='table'")
            }
            self.assertNotIn("selections", tables)
            for table in JSONL_TABLES + JSON_RECORD_TABLES:
                with self.subTest(table=table):
                    expected = {row["id"]: row for row, _ in iter_records(self.root, table)}
                    actual = {
                        record_id: json.loads(raw)
                        for record_id, raw in connection.execute(
                            "select id, record_json from " + table
                        )
                    }
                    self.assertEqual(actual, expected)
            self.assertEqual(
                connection.execute(
                    "select count(*) from content_search where content_search match ?",
                    ('"物质世界"',),
                ).fetchone()[0],
                2,
            )

    def test_sqlite_projection_retains_records_and_searches_chinese(self):
        self.create_sqlite_records()
        self.assertFalse((self.root / "selections").exists())
        output = self.root / ".cache/search.sqlite3"
        export_sqlite(self.root, output)
        self.assert_sqlite_records(output)

    def test_cli_sqlite_export_ignores_broken_projections_but_validates_records(self):
        self.create_sqlite_records()
        for name in ("training", "release", "topics"):
            path = self.root / "selections" / (name + ".json")
            path.parent.mkdir(exist_ok=True)
            path.write_text("{broken json", encoding="utf-8")
        output = self.root / ".cache/search.sqlite3"
        args = ["--root", str(self.root), "export", "--format", "sqlite", "--output", str(output)]
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(main(args), 0)
        self.assert_sqlite_records(output)
        before = output.read_bytes()
        self.transcript["item_id"] = make_record_id("i", "missing")
        self.save_transcript()
        errors = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(errors):
            self.assertEqual(main(args), 1)
        self.assertIn("unresolved items", errors.getvalue())
        self.assertEqual(output.read_bytes(), before)

    def test_cli_generate_without_selections_and_removed_selection_argument(self):
        self.assertFalse((self.root / "selections").exists())
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--root", str(self.root), "generate"]), 0)
            self.assertEqual(main(["--root", str(self.root), "generate", "--check"]), 0)
            with self.assertRaises(SystemExit) as error:
                main(["--root", str(self.root), "export", "--format", "review_issues", "--selection", "training"])
        self.assertEqual(error.exception.code, 2)
        self.assertFalse((self.root / "selections").exists())

    def test_recognition_chunk_tampering_fails_validation(self):
        self.transcript["recognition_chunks"] = [
            {
                "id": make_record_id("x", "word"),
                "time_unit": "ms",
                "sentences": [
                    {"words": [{"text": "物质", "begin_time": 100, "end_time": 400}]}
                ],
            }
        ]
        self.transcript["recognition_chunks_sha256"] = json_sha256(
            self.transcript["recognition_chunks"]
        )
        self.save_transcript()
        self.assertEqual(validate_corpus(self.root)["transcripts"], 1)
        self.transcript["recognition_chunks"][0]["sentences"][0]["words"][0][
            "end_time"
        ] = 700
        self.save_transcript()
        with self.assertRaisesRegex(ValueError, "recognition chunk SHA-256"):
            validate_corpus(self.root)

    def test_edited_transcript_derivation_cycle_fails_validation(self):
        r = self.create_edited_transcript()
        r["derived_from_id"] = r["id"]
        write_json(self.root / "data/edited_transcripts" / (r["id"] + ".json"), r)
        with self.assertRaisesRegex(ValueError, "edited transcript parent cycle"):
            validate_corpus(self.root)

    def test_missing_input_unit_reference_fails_validation(self):
        r = self.create_edited_transcript()
        r["input_units_from_id"] = make_record_id("r", "missing")
        write_json(self.root / "data/edited_transcripts" / (r["id"] + ".json"), r)
        with self.assertRaisesRegex(ValueError, "unresolved edited_transcripts"):
            validate_corpus(self.root)

    def test_issue_evidence_cannot_reference_a_missing_recognition_chunk(self):
        self.transcript["metadata"] = {
            "recognition_issue_intervals": [
                [
                    {
                        "start_seconds": 0,
                        "end_seconds": 1,
                        "reason": "provider_returned_no_words",
                        "evidence": [
                            {
                                "transcript_id": self.transcript["id"],
                                "recognition_chunk_ids": [
                                    make_record_id("x", "missing")
                                ],
                            }
                        ],
                    }
                ]
            ]
        }
        self.save_transcript()
        with self.assertRaisesRegex(
            ValueError, "unresolved recognition chunk evidence"
        ):
            validate_corpus(self.root)

    def test_schema_one_is_rejected(self):
        self.transcript["schema_version"] = 1
        self.save_transcript()
        with self.assertRaisesRegex(ValueError, "schema_version=2"):
            validate_corpus(self.root)

    def test_model_requires_named_object_and_preserves_revision(self):
        self.transcript["model"] = "fixture"
        self.save_transcript()
        with self.assertRaisesRegex(ValueError, "model must be an object"):
            validate_corpus(self.root)
        self.transcript["model"] = {"name": "fixture", "revision": "exact-revision"}
        self.save_transcript()
        validate_corpus(self.root)
        saved = next(iter_records(self.root, "transcripts"))[0]
        self.assertEqual(saved["model"], self.transcript["model"])

    def test_issue_seconds_do_not_inherit_paragraph_milliseconds(self):
        edited = self.create_edited_transcript()
        edited["quality"]["input_quality"] = {
            "recognition_issue_intervals": [
                {
                    "start_seconds": 5040,
                    "end_seconds": 5280,
                    "reason": "unrepresentable_provider_timestamps",
                    "transcript_text_available": True,
                }
            ]
        }
        path = self.root / "data/edited_transcripts" / (edited["id"] + ".json")
        write_json(path, edited)
        validate_corpus(self.root)
        saved = read_json(path)
        self.assertEqual(saved["time_unit"], "ms")
        interval = saved["quality"]["input_quality"]["recognition_issue_intervals"][0]
        self.assertEqual(interval["start_seconds"], 5040)
        self.assertTrue(interval["transcript_text_available"])
        interval["start"] = interval.pop("start_seconds")
        write_json(path, saved)
        with self.assertRaisesRegex(ValueError, "explicit seconds"):
            validate_corpus(self.root)

    def test_catalog_and_navigation_derive_from_same_records(self):
        self.create_edited_transcript()
        self.assertIn(self.transcript["id"], render_catalog_csv(self.root))
        generate_catalog_docs(self.root)
        generate_catalog_docs(self.root, check=True)
        (self.root / "docs/INDEX.md").write_text("stale", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "stale"):
            generate_catalog_docs(self.root, check=True)

    def test_catalog_distinguishes_transcripts_and_identifies_edited_input(self):
        self.transcript["method"] = "asr_local"
        self.transcript["model"] = {"name": "source://production/models/Qwen3-ASR-1.7B-hf"}
        self.save_transcript()
        subtitle = copy.deepcopy(self.transcript)
        subtitle["id"] = make_record_id("t", "platform-subtitle")
        subtitle["method"] = "subtitle_ai"
        subtitle["model"] = None
        subtitle["content_sha256"] = json_sha256(transcript_hash_input(subtitle))
        write_json(self.root / "data/transcripts" / (subtitle["id"] + ".json"), subtitle)
        edited = self.create_edited_transcript()
        counts = generate_catalog_docs(self.root)
        catalog = (self.root / "docs/catalog/audio_recordings.md").read_text(encoding="utf-8")
        self.assertEqual(counts["transcripts"], 2)
        self.assertIn(f"[平台 AI 字幕:{subtitle['id'][2:10]}]", catalog)
        self.assertIn(f"[本地语音转录（Qwen3-ASR-1.7B-hf）:{self.transcript['id'][2:10]}]", catalog)
        self.assertIn(
            f"[整理稿（fixture）:{edited['id'][2:10]}](../../data/edited_transcripts/{edited['id']}.json)"
            f"（输入：`{self.transcript['id'][2:10]}`）",
            catalog,
        )
        self.assertIn("../SCHEMA.md#基础转录与整理稿", catalog)
        generate_catalog_docs(self.root, check=True)

    def test_independent_review_export_retains_additional_notes(self):
        row = self.create_edited_transcript()
        row["review_document_markdown"] = "# 独立参照稿\n\n原有疑点。\n"
        row["notes_markdown"] = "后续人工核对只确认了一个字。"
        before = copy.deepcopy(row)
        exported = render_review_markdown(row, self.item)
        self.assertTrue(exported.startswith(row["review_document_markdown"]))
        self.assertIn(row["notes_markdown"], exported)
        self.assertEqual(row, before)
        row["notes_markdown"] = "原有疑点。"
        self.assertEqual(
            render_review_markdown(row, self.item), row["review_document_markdown"]
        )

    def test_review_issues_preserve_empty_candidates_and_note_only_entries(self):
        row = self.create_edited_transcript()
        issues = [
            {"note": "需要回听", "candidate": "", "evidence_labels": []},
            {"note": "只保留说明"},
            {"note": "候选已用于正文", "candidate": "物质", "evidence_labels": ["s1"]},
        ]
        row["paragraphs"][0]["issues"] = issues
        entries = list(iter_review_issues(row))
        self.assertEqual([entry["issue"] for entry in entries], issues)
        exported = render_review_markdown(row, self.item)
        for issue in issues:
            self.assertIn(issue["note"], exported)
        with self.assertRaisesRegex(ValueError, "edited transcript"):
            list(iter_review_issues(self.transcript))

    def test_review_issues_export_all_and_id_with_exact_locators(self):
        row = self.create_edited_transcript()
        row["paragraphs"][0]["issues"] = [
            {"note": '待回听\n保留原有换行与引号"。'},
            {"note": "候选尚空", "candidate": ""},
        ]
        write_json(self.root / "data/edited_transcripts" / (row["id"] + ".json"), row)
        another = copy.deepcopy(row)
        another["id"] = make_record_id("r", "another-review")
        write_json(
            self.root / "data/edited_transcripts" / (another["id"] + ".json"), another
        )
        for scope, count in (
            ([], 4),
            (["--id", row["id"]], 2),
        ):
            with self.subTest(scope=scope):
                output = self.root / ".cache/issues.jsonl"
                with redirect_stdout(io.StringIO()):
                    result = main(
                        [
                            "--root",
                            str(self.root),
                            "export",
                            "--format",
                            "review_issues",
                            *scope,
                            "--output",
                            str(output),
                        ]
                    )
                self.assertEqual(result, 0)
                entries = [
                    json.loads(line)
                    for line in output.read_text(encoding="utf-8").splitlines()
                ]
                self.assertEqual(len(entries), count)
                for entry in entries:
                    source = read_json(self.root / entry["record_path"])
                    self.assertEqual(source["id"], entry["edited_transcript_id"])
                    self.assertEqual(source["item_id"], entry["item_id"])
                    self.assertEqual(
                        source["paragraphs"][entry["paragraph_index"]]["issues"][
                            entry["issue_index"]
                        ],
                        entry["issue"],
                    )

    def test_review_counts_catalog_and_issue_validation(self):
        row = self.create_edited_transcript()
        row["paragraphs"][0]["issues"] = [
            {"note": "待核对"},
            {"note": "已修改", "candidate": "物质"},
        ]
        path = self.root / "data/edited_transcripts" / (row["id"] + ".json")
        write_json(path, row)
        counts = generate_catalog_docs(self.root)
        self.assertEqual(counts["review_issues"], 2)
        self.assertEqual(counts["paragraphs_with_review_issues"], 1)
        self.assertEqual(counts["edited_transcripts_with_review_issues"], 1)
        self.assertIn(
            row["id"],
            (self.root / "docs/catalog/reviews.md").read_text(encoding="utf-8"),
        )
        for invalid in (
            {"candidate": "没有说明"},
            {"note": "说明", "candidate": None},
            {"note": "说明", "evidence_labels": "s1"},
        ):
            with self.subTest(invalid=invalid):
                row["paragraphs"][0]["issues"] = [invalid]
                write_json(path, row)
                with self.assertRaises(ValueError):
                    validate_corpus(self.root)


if __name__ == "__main__":
    unittest.main()
