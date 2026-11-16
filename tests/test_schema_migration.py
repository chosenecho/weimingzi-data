"""Exercise the offline transaction through the same interface as its CLI."""

import copy
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from weimingzi_corpus import schema_migration as migration
from weimingzi_corpus import schema_v3


def record_id(prefix, value):
    return prefix + "-" + hashlib.sha256(value.encode()).hexdigest()[:24]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_bytes(root):
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


def fixture(root):
    item = {"schema_version": 2, "id": record_id("i", "item"), "kind": "audio_recording",
            "title": "测试存档", "identifiers": {"fixture": ["one"]}, "urls": [],
            "metadata": {"duration_ms": [1500, [1500]], "observed_at": ["原值"]}, "relations": []}
    transcript = {"schema_version": 2, "id": record_id("t", "transcript"), "kind": "transcript",
                  "item_id": item["id"], "method": "asr", "model": {"name": "fixture", "revision": None},
                  "language": "zh", "text": "甲😀乙。\n原全文独有", "time_unit": "s",
                  "segments": [{"index": 0, "start": 0.0001, "end": 1.5, "text": "甲😀乙。"},
                               {"index": 1, "start": 0.0, "end": 0.25, "text": "全文外分段"}],
                  "quality": {"is_fully_human_reviewed": None, "requires_review": True,
                              "is_subtitle_export_enabled": False, "timing_issues": ["原异常"]},
                  "recognition_chunks": [{"id": "chunk-1", "offset_seconds": 0.25, "duration_seconds": 1.25,
                                           "time_unit": "ms", "text": "原块", "sentences": [{"text": "原块", "start": 1}]}]}
    hash_fields = ("item_id", "method", "language", "model", "time_unit", "text", "segments")
    transcript["content_sha256"] = migration._digest({key: transcript[key] for key in hash_fields})
    transcript["recognition_chunks_sha256"] = migration._digest(transcript["recognition_chunks"])
    edited = {"schema_version": 2, "id": record_id("r", "edited"), "kind": "edited_transcript",
              "item_id": item["id"], "text": "甲😀乙。", "paragraphs": [{"index": 0, "text": "甲😀乙。",
              "input_text": "甲😀乙。", "start": 0.0001, "end": 1.5,
              "input_unit_labels": ["A"], "issues": [{"note": "原注", "candidate": "", "evidence_labels": []}]}],
              "time_unit": "s", "transcript_ids": [transcript["id"]], "model": None,
              "notes_markdown": "附注\n", "review_document_markdown": "# 独立稿\n完整原文\n",
              "is_complete": False, "quality": {"is_fully_human_reviewed": None, "requires_review": True},
              "input_units": {"base": {"upstream_transcript_id": "not-a-live-reference",
              "content_sha256": "f" * 64, "method": "asr", "language": "zh",
              "segments": [{"label": "A", "start_ms": 0.1, "end_ms": 1500, "text": "甲😀乙。"}]},
              "unassigned_reference_labels": []}}
    confirmation = {"schema_version": 2, "id": record_id("c", "confirmation"), "kind": "confirmation",
                    "item_id": item["id"], "edited_transcript_ids": [edited["id"]],
                    "scope": "local_text_or_term", "status": "human_confirmed",
                    "anchor": {"original_text": "甲😀乙。", "original_text_sha256": hashlib.sha256("甲😀乙。".encode()).hexdigest(),
                               "input_unit_label": "A"}, "corrected_text": "甲😀乙。",
                    "corrected_text_sha256": hashlib.sha256("甲😀乙。".encode()).hexdigest(),
                    "term_glosses": {"原词": "原义"},
                    "confirmation": {"excerpt": "甲😀乙。", "resolution": "原话", "reviewer_label": "用户",
                                     "reviewed_on": "2026-11-16", "review_timezone": "Asia/Hong_Kong"}}
    edited["confirmation_ids"] = [confirmation["id"]]
    article = {"schema_version": 2, "id": record_id("a", "article"), "kind": "article",
               "item_id": item["id"], "text": "文章", "html": "<p>文章😀</p>\n",
               "quality": {"has_expand_prompt": None}}
    tables = {table: [] for table in migration.TABLES}
    tables.update(items=[item], transcripts=[transcript], edited_transcripts=[edited],
                  articles=[article], confirmations=[confirmation])
    for table in migration.JSONL_TABLES:
        path = root / "data" / (table + ".jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in tables[table]), encoding="utf-8")
    for table in migration.JSON_TABLES:
        (root / "data" / table).mkdir(parents=True)
        for row in tables[table]:
            write_json(root / "data" / table / (row["id"] + ".json"), row)
    return tables


class SchemaMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.source = self.base / "source"
        self.output = self.base / "output"
        self.tables = fixture(self.source)
        self.original = file_bytes(self.source)

    def tearDown(self):
        self.temp.cleanup()

    def test_roundtrip_report_artifacts_and_independent_read_only_verification(self):
        report = migration.migrate(self.source, self.output)
        self.assertEqual(file_bytes(self.source), self.original)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["source"]["git"]["input"], "working_tree_bytes")
        self.assertEqual(report["source"]["manifest_sha256"], migration._digest(report["source"]["files"]))
        self.assertEqual({row["id"] for row in report["verification"]["records"]},
                         {row["id"] for rows in self.tables.values() for row in rows})
        for table, expected in self.tables.items():
            actual = [row for row, _ in schema_v3.iter_legacy_records(self.output, table)]
            self.assertEqual(sorted(expected, key=lambda row: row["id"]), actual)
        for row in report["verification"]["records"]:
            self.assertEqual(row["legacy_json_sha256"], row["projection_json_sha256"])
            self.assertTrue(all(field["destination"] for field in row["fields"]))
        artifact_kinds = {row["kind"] for row in report["verification"]["new_artifacts"]}
        self.assertIn("review_document", artifact_kinds)
        self.assertIn("html", artifact_kinds)
        self.assertFalse((self.output / "data" / "transcripts").exists())
        self.assertFalse((self.output / "data" / "confirmations.jsonl").exists())
        before = file_bytes(self.output)
        self.assertEqual(migration.migrate(self.source, self.output, verify_only=True), report)
        self.assertEqual(file_bytes(self.output), before)
        self.assertEqual(file_bytes(self.source), self.original)

    def test_two_destinations_are_byte_deterministic_including_report(self):
        migration.migrate(self.source, self.output)
        other = self.base / "other"
        migration.migrate(self.source, other)
        self.assertEqual(file_bytes(self.output), file_bytes(other))

    def test_converter_failure_keeps_source_and_no_complete_destination(self):
        def fail(root, tables):
            write_json(root / "data" / "schema.json", {"schema_version": 3})
            raise ValueError("injected conversion failure")
        with patch.object(schema_v3, "write_legacy_dataset", side_effect=fail):
            with self.assertRaisesRegex(ValueError, "injected conversion failure"):
                migration.migrate(self.source, self.output)
        self.assertEqual(file_bytes(self.source), self.original)
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.base.glob(".output.incomplete-*")), [])

    def _assert_missing_item_reference_fails_closed(self, missing_id):
        for table in migration.JSONL_TABLES:
            path = self.source / "data" / (table + ".jsonl")
            path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n"
                                    for row in self.tables[table]), encoding="utf-8")
        before = file_bytes(self.source)
        with self.assertRaisesRegex(ValueError, "native validation failed") as error:
            migration.migrate(self.source, self.output)
        self.assertIn(missing_id, str(error.exception))
        self.assertEqual(file_bytes(self.source), before)
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.base.glob(".output.incomplete-*")), [])
        self.assertFalse((self.base / ".output.schema-v3.lock").exists())

    def test_missing_inline_parent_id_prevents_publication(self):
        missing_id = record_id("i", "missing-parent")
        self.tables["items"][0]["parent_id"] = missing_id
        self._assert_missing_item_reference_fails_closed(missing_id)

    def test_missing_inline_collection_member_prevents_publication(self):
        missing_id = record_id("i", "missing-member")
        self.tables["collections"] = [{"schema_version": 2,
            "id": record_id("c", "collection"), "kind": "video_collection",
            "title": "成员引用", "identifiers": {}, "metadata": {},
            "members": [{"item_id": missing_id, "position": 1}]}]
        self._assert_missing_item_reference_fails_closed(missing_id)

    def test_missing_inline_relation_target_prevents_publication(self):
        missing_id = record_id("i", "missing-relation")
        self.tables["items"][0]["relations"] = [{"target_item_id": missing_id,
            "kind": "rerecording_of", "evidence": {"note": "原始人工证据"}}]
        self._assert_missing_item_reference_fails_closed(missing_id)

    def test_projection_tampering_prevents_publication(self):
        original = schema_v3.iter_legacy_records
        def altered(root, table):
            for row, path in original(root, table):
                row = copy.deepcopy(row)
                if table == "transcripts":
                    row["segments"][0]["start"] = 0
                yield row, path
        with patch.object(schema_v3, "iter_legacy_records", side_effect=altered):
            with self.assertRaisesRegex(ValueError, "exact legacy JSON mismatch"):
                migration.migrate(self.source, self.output)
        self.assertEqual(file_bytes(self.source), self.original)
        self.assertFalse(self.output.exists())

    def test_numeric_boolean_projection_difference_is_not_python_equality(self):
        original = schema_v3.iter_legacy_records
        def altered(root, table):
            for row, path in original(root, table):
                row = copy.deepcopy(row)
                if table == "transcripts":
                    row["quality"]["requires_review"] = 1
                yield row, path
        with patch.object(schema_v3, "iter_legacy_records", side_effect=altered):
            with self.assertRaisesRegex(ValueError, "exact legacy JSON mismatch"):
                migration.migrate(self.source, self.output)
        self.assertEqual(file_bytes(self.source), self.original)
        self.assertFalse(self.output.exists())

    def test_ambiguous_or_nonfinite_json_is_rejected_without_source_write(self):
        path = self.source / "data" / "items.jsonl"
        original = path.read_bytes()
        for bad in (original.replace(b'"schema_version": 2', b'"schema_version": 2, "schema_version": 2'),
                    original.replace(b'1500', b'NaN', 1)):
            with self.subTest(bad=bad[:60]):
                path.write_bytes(bad)
                before = file_bytes(self.source)
                with self.assertRaisesRegex(ValueError, "duplicate JSON key|non-finite JSON"):
                    migration.migrate(self.source, self.output)
                self.assertEqual(file_bytes(self.source), before)
                self.assertFalse(self.output.exists())
        path.write_bytes(original)

    def test_source_changes_during_conversion_prevent_publication(self):
        original = schema_v3.write_legacy_dataset
        def changing(root, tables):
            result = original(root, tables)
            path = self.source / "data" / "items.jsonl"
            path.write_bytes(path.read_bytes() + b"\n")
            return result
        with patch.object(schema_v3, "write_legacy_dataset", side_effect=changing):
            with self.assertRaisesRegex(ValueError, "source changed"):
                migration.migrate(self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_source_nested_target_and_preexisting_target_are_rejected(self):
        for target in (self.source, self.source / "candidate", self.base):
            with self.subTest(target=target):
                with self.assertRaisesRegex(ValueError, "independent"):
                    migration.migrate(self.source, target)
        self.output.mkdir()
        (self.output / "keep").write_bytes(b"precious")
        with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
            migration.migrate(self.source, self.output)
        self.assertEqual((self.output / "keep").read_bytes(), b"precious")
        self.assertEqual(file_bytes(self.source), self.original)

    def test_existing_empty_destination_is_supported(self):
        self.output.mkdir()
        migration.migrate(self.source, self.output)
        self.assertTrue((self.output / migration.REPORT_NAME).is_file())

    def test_missing_table_and_unknown_files_fail_closed(self):
        (self.source / "data" / "posts").rmdir()
        with self.assertRaisesRegex(ValueError, "missing legacy table"):
            migration.migrate(self.source, self.output)
        (self.source / "data" / "posts").mkdir()
        (self.source / "data" / "extra.bin").write_bytes(b"unmapped")
        with self.assertRaisesRegex(ValueError, "unexpected legacy file"):
            migration.migrate(self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_symlink_source_or_target_ancestor_is_rejected(self):
        link = self.base / "link"
        try:
            link.symlink_to(self.source, target_is_directory=True)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"symlink privilege unavailable: {error}")
        with self.assertRaisesRegex(ValueError, "symlink/junction"):
            migration.migrate(link, self.output)
        with self.assertRaisesRegex(ValueError, "symlink/junction"):
            migration.migrate(self.source, link / "destination")
        link.unlink()
        original_file = self.source / "data" / "items.jsonl"
        original_file.rename(self.base / "items.jsonl")
        original_file.symlink_to(self.base / "items.jsonl")
        with self.assertRaisesRegex(ValueError, "symlink/junction"):
            migration.migrate(self.source, self.output)

    @unittest.skipUnless(os.name == "nt", "Windows junction regression")
    def test_windows_junction_target_ancestor_is_rejected(self):
        link = self.base / "junction"
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(self.source)],
                                capture_output=True, text=True)
        if result.returncode:
            self.skipTest("junction creation unavailable: " + result.stderr)
        try:
            with self.assertRaisesRegex(ValueError, "symlink/junction"):
                migration.migrate(self.source, link / "destination")
            with self.assertRaisesRegex(ValueError, "symlink/junction"):
                migration.migrate(link, self.output)
        finally:
            link.rmdir()

    def test_verify_only_detects_report_or_source_or_target_changes(self):
        migration.migrate(self.source, self.output)
        report_path = self.output / migration.REPORT_NAME
        saved = report_path.read_bytes()
        source_path = self.source / "data" / "items.jsonl"
        source_bytes = source_path.read_bytes()
        source_path.write_bytes(source_bytes + b"\n")
        output_before = file_bytes(self.output)
        with self.assertRaisesRegex(ValueError, "source evidence differs"):
            migration.migrate(self.source, self.output, verify_only=True)
        self.assertEqual(file_bytes(self.output), output_before)
        source_path.write_bytes(source_bytes)
        report = json.loads(saved)
        report["target"]["size_bytes"] += 1
        report["report_sha256"] = migration._digest(
            {key: value for key, value in report.items() if key != "report_sha256"})
        write_json(report_path, report)
        with self.assertRaisesRegex(ValueError, "target file inventory"):
            migration.migrate(self.source, self.output, verify_only=True)
        report = json.loads(saved)
        report["status"] = "forged"
        write_json(report_path, report)
        with self.assertRaisesRegex(ValueError, "report SHA-256"):
            migration.migrate(self.source, self.output, verify_only=True)
        report_path.write_bytes(saved)
        path = self.output / "data" / "items.jsonl"
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "target file inventory"):
            migration.migrate(self.source, self.output, verify_only=True)
        self.assertEqual(file_bytes(self.source), self.original)

    def test_cli_and_verify_only_return_reviewable_machine_result(self):
        output = io.StringIO()
        with redirect_stdout(output):
            result = migration.main(["--source", str(self.source), "--output", str(self.output)])
        self.assertEqual(result, 0, output.getvalue())
        self.assertTrue(json.loads(output.getvalue())["ok"])
        result = subprocess.run([sys.executable, str(ROOT / "tools" / "migrate_schema_v3.py"),
                                 "--source", str(self.source), "--output", str(self.output), "--verify-only"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["verify_only"])


if __name__ == "__main__":
    unittest.main()
