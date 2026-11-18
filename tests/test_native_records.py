"""Native storage/hash/upsert/install contracts, without projected table fixtures."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from native_fixtures import fixture_records, rid, write_corpus
from weimingzi_corpus import records
from weimingzi_corpus.records import (
    ENTITIES, JSONL_ENTITIES, block_text, canonical_json, document_hash_input,
    input_ids, install_candidate_updates, iter_records, json_sha256,
    load_document, make_record_id, read_json, record_path,
    resolve_input_text, resolve_repository_path, validate_corpus,
    validate_relative_path, write_json, write_record_updates,
)


class NativeRecordsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "corpus"
        self.rows = write_corpus(self.root)
        self.entities = {entity: {row["id"]: row for row in rows} for entity, rows in self.rows.items()}

    def tearDown(self):
        self.temp.cleanup()

    def test_native_entities_and_kind_filters(self):
        self.assertEqual(ENTITIES, ("items", "documents", "assets", "annotations"))
        self.assertEqual(JSONL_ENTITIES, ("items", "assets", "annotations"))
        matches = list(iter_records(self.root, "documents", kind="edited_transcript"))
        self.assertEqual(len(matches), 2)
        for row, path in matches:
            self.assertIn("blocks", row)
            self.assertNotIn("paragraphs", row)
            self.assertEqual(path.parent, self.root / "data/documents")
            self.assertEqual(load_document(self.root, row["id"]), row)
        with self.assertRaisesRegex(ValueError, "Unknown entity"):
            list(iter_records(self.root, "transcripts"))

    def test_missing_or_older_schema_is_not_decoded(self):
        write_json(self.root / "data/schema.json", {"schema_version": 2})
        with self.assertRaisesRegex(ValueError, "native four-entity"):
            list(iter_records(self.root, "items"))
        with self.assertRaisesRegex(ValueError, "native four-entity"):
            load_document(self.root, rid("transcript", "t"))

    def test_document_filename_must_match_record(self):
        doc = self.rows["documents"][0]
        old = record_path(self.root, "documents", doc["id"])
        old.rename(old.with_name(rid("different", "t") + ".json"))
        with self.assertRaisesRegex(ValueError, "filename"):
            validate_corpus(self.root)

    def test_native_hash_explicit_fields_and_absence_null(self):
        doc = self.rows["documents"][0]
        payload = document_hash_input(doc)
        self.assertEqual(set(payload), {"kind", "inputs", "method", "language", "model", "time_unit", "text", "blocks"})
        original = json_sha256(payload)
        for key, value in (("id", rid("changed", "t")), ("quality", {"requires_review": False}), ("metadata", {"source_sha256": "old"}), ("recognition_chunks_sha256", "f" * 64), ("content_sha256", "f" * 64)):
            changed = copy.deepcopy(doc)
            changed[key] = value
            self.assertEqual(json_sha256(document_hash_input(changed)), original)
        changed = copy.deepcopy(doc)
        changed["blocks"][0]["start"] = -1.125
        self.assertNotEqual(json_sha256(document_hash_input(changed)), original)
        self.assertNotEqual(document_hash_input({"kind": "article"}), document_hash_input({"kind": "article", "model": None}))
        self.assertNotIn("segments", canonical_json(payload))
        self.assertEqual(json_sha256(payload), hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest())

    def test_codepoint_ranges_literals_and_joined_block_refs(self):
        raw, edited = self.rows["documents"][:2]
        self.assertEqual(block_text(raw, raw["blocks"][0]), "原句😀。")
        self.assertEqual(block_text({"id": "x"}, {"literal": "\n"}), "\n")
        self.assertEqual(resolve_input_text(edited, edited["blocks"][0], self.entities), "原句😀。")
        self.assertEqual(resolve_input_text(edited, edited["blocks"][1], self.entities), "第二段。")
        raw["text"] = "前😀\n后。"
        raw["blocks"] = [{"range": [0, 2]}, {"literal": "中"}, {"range": [3, 5]}]
        raw["content_sha256"] = json_sha256(document_hash_input(raw))
        block = {"input_text_ref": {"target_id": raw["id"], "content_sha256": raw["content_sha256"], "source": "blocks", "range": [1, 4]}}
        self.assertEqual(resolve_input_text(edited, block, self.entities), "😀中后")
        block["input_text_ref"]["source"] = "text"
        self.assertEqual(resolve_input_text(edited, block, self.entities), "😀\n后")

    def test_input_reference_requires_current_native_hash_and_direct_source(self):
        raw, edited = self.rows["documents"][:2]
        block = copy.deepcopy(edited["blocks"][0])
        block["input_text_ref"]["content_sha256"] = "a" * 64
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            resolve_input_text(edited, block, self.entities)
        block = copy.deepcopy(edited["blocks"][0])
        block["input_text_ref"]["source"] = "segments"
        with self.assertRaisesRegex(ValueError, "Unknown input text source"):
            resolve_input_text(edited, block, self.entities)
        edited["inputs"] = [edge for edge in edited["inputs"] if edge["role"] != "transcript"]
        with self.assertRaisesRegex(ValueError, "transcript input"):
            resolve_input_text(edited, edited["blocks"][0], self.entities)

    def test_absent_null_false_remain_distinct(self):
        _, edited = self.rows["documents"][:2]
        self.assertIsNone(resolve_input_text(edited, {}, self.entities))
        self.assertIsNone(resolve_input_text(edited, {"input_text": None}, self.entities))
        self.assertIsNone(edited["model"])
        self.assertIs(edited["quality"]["is_fully_human_reviewed"], False)
        original = copy.deepcopy(self.rows)
        self.assertEqual(write_record_updates(self.root, self.rows), [])
        for entity in ENTITIES:
            self.assertCountEqual([row for row, _ in iter_records(self.root, entity)], original[entity])
        self.assertEqual(input_ids(edited, "transcript"), [self.rows["documents"][0]["id"]])

    def test_independent_asset_upsert_is_native_and_not_projection_bound(self):
        archive = {"id": rid("new-independent", "z"), "kind": "archive", "name": "other.tar", "url": "https://example.org/other.tar", "size_bytes": 23, "sha256": "d" * 64, "metadata": {"observation": None}}
        before_docs = {path: path.read_bytes() for path in (self.root / "data/documents").glob("*.json")}
        self.assertEqual(write_record_updates(self.root, {"assets": [archive]}), [Path("data/assets.jsonl")])
        self.assertIn(archive, [row for row, _ in iter_records(self.root, "assets")])
        self.assertEqual(before_docs, {path: path.read_bytes() for path in before_docs})
        self.assertEqual(write_record_updates(self.root, {"assets": [archive]}), [])

    def test_invalid_complete_candidate_never_installs_partial_updates(self):
        before = {path: path.read_bytes() for path in (self.root / "data").rglob("*") if path.is_file()}
        edited = copy.deepcopy(self.rows["documents"][1])
        edited["inputs"][0]["target_id"] = rid("other-missing")
        asset = copy.deepcopy(self.rows["assets"][2])
        asset["size_bytes"] = 999
        with self.assertRaisesRegex(ValueError, "Invalid native candidate"):
            write_record_updates(self.root, {"documents": [edited], "assets": [asset]})
        self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_graph_upsert_changes_actual_paths_and_preserves_snapshots(self):
        doc = copy.deepcopy(self.rows["documents"][1])
        doc["notes_markdown"] += "\n新增注记"
        paths = write_record_updates(self.root, {"documents": [doc]})
        self.assertEqual(paths, [Path("data/documents") / (doc["id"] + ".json")])
        actual = load_document(self.root, doc["id"])
        self.assertEqual(actual, doc)
        self.assertEqual(actual["input_units"]["base"]["content_sha256"], "historical-observation")
        self.assertEqual(actual["metadata"]["source_sha256"], "historical-observation")
        self.assertFalse(actual["quality"]["is_fully_human_reviewed"])

    def test_duplicate_incoming_ids_and_cross_entity_ids_are_rejected(self):
        doc = self.rows["documents"][1]
        with self.assertRaisesRegex(ValueError, "Duplicate update ID"):
            write_record_updates(self.root, {"documents": [doc, doc]})
        asset = copy.deepcopy(self.rows["assets"][2])
        asset["id"] = self.rows["items"][0]["id"]
        with self.assertRaisesRegex(ValueError, "Duplicate record ID"):
            write_record_updates(self.root, {"assets": [asset]})
        with self.assertRaisesRegex(ValueError, "Unknown entities"):
            write_record_updates(self.root, {"transcripts": []})

    def test_safe_ids_paths_and_strict_json(self):
        for value in ("../outside", "/absolute", "a/../b", "a//b", "a/./b", "a\\b", "C:/escape", ""):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_relative_path(value)
        for value in ("../escape", "i-not-hex", "x", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                record_path(self.root, "documents", value)
        self.assertEqual(resolve_repository_path(self.root, "data/schema.json"), self.root / "data/schema.json")
        path = self.root / "duplicate.json"
        path.write_text('{"a":1,"a":2}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            read_json(path)
        path.write_text('{"a":NaN}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            read_json(path)
        with self.assertRaises(ValueError):
            canonical_json({"n": float("inf")})
        self.assertEqual(make_record_id("t", "stable"), make_record_id("t", "stable"))

    def test_installer_atomic_failure_rolls_back_and_retains_candidate(self):
        candidate = Path(self.temp.name) / "candidate"
        target_a, target_b = Path("data/a.bin"), Path("data/b.bin")
        for path, content in ((target_a, b"old-a"), (target_b, b"old-b")):
            (self.root / path).write_bytes(content)
            (candidate / path).parent.mkdir(parents=True, exist_ok=True)
            (candidate / path).write_bytes(b"new" + content)
        real_replace = records.os.replace
        calls = []
        def fail_second(source, target):
            calls.append(target)
            if len(calls) == 2:
                raise OSError("injected installation failure")
            return real_replace(source, target)
        with patch.object(records.os, "replace", side_effect=fail_second), self.assertRaisesRegex(OSError, "injected"):
            install_candidate_updates(self.root, candidate, [target_a, target_b])
        self.assertEqual((self.root / target_a).read_bytes(), b"old-a")
        self.assertEqual((self.root / target_b).read_bytes(), b"old-b")
        self.assertEqual((candidate / target_a).read_bytes(), b"newold-a")
        self.assertEqual(list((self.root / "data").glob(".record-install-*")), [])

    def test_installer_deletes_only_explicit_missing_candidate_files(self):
        candidate = Path(self.temp.name) / "candidate"
        candidate.mkdir()
        target = self.root / "data/remove.txt"
        target.write_text("remove", encoding="utf-8")
        install_candidate_updates(self.root, candidate, [Path("data/remove.txt")])
        self.assertFalse(target.exists())
        self.assertTrue((self.root / "data/schema.json").exists())
        with self.assertRaisesRegex(ValueError, "disjoint"):
            install_candidate_updates(self.root, self.root / "candidate", [])
        with self.assertRaises(ValueError):
            install_candidate_updates(self.root, candidate, ["../outside"])


if __name__ == "__main__":
    unittest.main()
