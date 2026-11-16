"""Focused tests across the public four-entity version seam."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from weimingzi_corpus import schema_v3 as v3


def fixture():
    transcript = {
        "schema_version": 2, "id": "t-example", "kind": "transcript", "item_id": "i-example",
        "audio_ids": [], "method": "asr_cloud", "language": "zh", "model": {"name": "model"},
        "time_unit": "s", "text": "甲😀\n乙", "segments": [
            {"index": 0, "text": "甲😀", "start": 0.0001, "end": 0.0009, "speaker_id": "s1"},
            {"index": 1, "text": "乙", "start": -1, "end": -2, "chunk_offset_seconds": 3}],
        "quality": {"timing_issues": ["segment 1: expected 0 <= start < end", "segment 1: starts must not decrease"], "is_fully_human_reviewed": None},
        "metadata": {"language": ["zh"]},
    }
    transcript["content_sha256"] = v3.json_sha256({k: transcript[k] for k in ("item_id", "method", "language", "model", "time_unit", "text", "segments")})
    edited = {"schema_version": 2, "id": "r-example", "kind": "edited_transcript", "item_id": "i-example",
              "transcript_ids": ["t-example"], "text": "甲😀\n\n改后。\n", "time_unit": "ms", "model": None,
              "paragraphs": [{"index": 0, "text": "甲😀", "start": 0.00001, "end": 0.2, "input_text": "甲😀", "issues": [], "input_unit_labels": []},
                             {"index": 1, "text": "全文外原段", "start": 1, "end": 0, "input_text": "未映射输入", "issues": [{"note": "原样"}]}],
              "paragraphs_match_text": False, "quality": {"input_quality": {"timing_issues": ["historic"], "is_fully_human_reviewed": None}},
              "confirmation_ids": ["a-confirm"], "notes_markdown": "附注", "review_document_markdown": "# 独立稿\r\n😀\n", "is_complete": False}
    return {
        "items": [{"schema_version": 2, "id": "i-example", "kind": "video", "title": "题", "metadata": {"title": ["题"], "pubdate": [1], "published_at_unix_seconds": [1], "created": [1], "ctime": [1], "author": ["A"], "uploader_name": ["B"]}}],
        "collections": [{"schema_version": 2, "id": "c-example", "kind": "video_collection", "members": [{"item_id": "i-example", "position": 1}]}],
        "transcripts": [transcript], "edited_transcripts": [edited],
        "confirmations": [{"schema_version": 2, "id": "a-confirm", "kind": "confirmation", "item_id": "i-example", "edited_transcript_ids": ["r-example"], "scope": "local_text_or_term", "status": "user_confirmed", "confirmation": {"assistant_listened_to_audio": False}}],
        "attributions": [{"schema_version": 2, "id": "s-example", "kind": "segment_attribution", "item_id": "i-example", "edited_transcript_id": "r-example", "anchor": {"paragraph_index": 0}, "viewpoint": "unknown", "speaker_role": "unknown", "status": "human_confirmed"}],
        "audio": [{"schema_version": 2, "id": "m-example", "kind": "audio", "item_ids": ["i-example"], "availability": "available", "sha256": "a" * 64, "downloads": [{"release_tag": "v1", "member_path": "原/成员.m4a", "archive": {"name": "one.zip", "size_bytes": 3, "sha256": "b" * 64, "url": "https://example.org/one.zip"}}]}],
        "articles": [{"schema_version": 2, "id": "a-article", "kind": "article", "item_id": "i-example", "text": "正文", "html": "<p>正文</p>"}],
        "posts": [{"schema_version": 2, "id": "d-post", "kind": "post", "item_id": "i-example", "content": {"rich": ["😀"]}, "article_item_ids": []}],
    }


class SchemaV3Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repository"

    def write(self, tables=None):
        tables = fixture() if tables is None else tables
        v3.write_legacy_dataset(self.root, tables)
        return tables

    def test_all_nine_tables_roundtrip_and_only_four_entities(self):
        original = self.write()
        self.assertTrue(v3.is_v3(self.root))
        self.assertEqual([], v3.validate_native(self.root))
        for table in v3.LEGACY_TABLES:
            self.assertEqual(sorted(original.get(table, []), key=lambda r: r["id"]), [r for r, _ in v3.iter_legacy_records(self.root, table)])
        self.assertEqual({"schema.json", "items.jsonl", "assets.jsonl", "annotations.jsonl", "documents", "artifacts"}, {p.name for p in (self.root / "data").iterdir()})
        for entity in v3.ENTITIES:
            self.assertTrue(all("schema_version" not in r for r, _ in v3.iter_native_records(self.root, entity)))

    def test_unicode_codepoints_literal_and_preserved_timing(self):
        original = self.write()
        doc = dict((r["id"], r) for r, _ in v3.iter_native_records(self.root, "documents"))["r-example"]
        self.assertEqual([0, 2], doc["blocks"][0]["range"])
        self.assertEqual("全文外原段", doc["blocks"][1]["literal"])
        self.assertNotIn("index", doc["blocks"][0])
        self.assertEqual(0.00001, doc["blocks"][0]["start"])
        self.assertEqual(original["edited_transcripts"][0], v3.load_legacy_record(self.root, "r-example"))

    def test_snapshot_and_quality_remain_historical(self):
        tables = fixture()
        edit = tables["edited_transcripts"][0]
        edit["transcript_ids"] = []
        edit["input_units"] = {"base": {"content_sha256": "old external hash", "method": "asr_cloud", "language": "zh", "upstream_transcript_id": "external", "segments": [{"label": "unit-a", "text": "甲😀", "start_ms": -13.5, "end_ms": 0.1, "checkpoint": "chunk"}]}, "unassigned_reference_labels": ["not-assigned"]}
        self.write(tables)
        doc = v3.load_legacy_record(self.root, "r-example")
        self.assertEqual(edit, doc)
        self.assertEqual(-13.5, doc["input_units"]["base"]["segments"][0]["start_ms"])
        native = json.loads((self.root / "data/documents/r-example.json").read_text(encoding="utf-8"))
        self.assertEqual("input_units", native["blocks"][0]["input_text_ref"]["source"])

    def test_annotation_one_way_and_order(self):
        self.write()
        native = json.loads((self.root / "data/documents/r-example.json").read_text(encoding="utf-8"))
        self.assertNotIn("confirmation_ids", native)
        self.assertIn("confirmation_ids", native["_legacy"]["keys"])
        annotations = dict((r["id"], r) for r, _ in v3.iter_native_records(self.root, "annotations"))
        target = annotations["a-confirm"]["targets"][1]
        self.assertEqual({"role": "applies_to", "target_id": "r-example", "confirmation_index": 0}, target)
        self.assertEqual("unknown", annotations["s-example"]["viewpoint"])

    def test_metadata_and_derived_values(self):
        self.write()
        rows = dict((r["id"], r) for r, _ in v3.iter_native_records(self.root, "items"))
        item = rows["i-example"]
        self.assertNotIn("pubdate", item["metadata"])
        self.assertNotIn("title", item["metadata"])
        self.assertEqual([1], item["metadata"]["created"])
        self.assertEqual([1], item["metadata"]["ctime"])
        self.assertEqual(["A"], item["metadata"]["author"])
        self.assertNotIn("position", rows["c-example"]["members"][0])
        transcript = json.loads((self.root / "data/documents/t-example.json").read_text(encoding="utf-8"))
        self.assertNotIn("timing_issues", transcript["quality"])

    def test_unknown_root_and_block_fail_before_writing(self):
        for field in ("root", "block"):
            tables = fixture()
            target = tables["transcripts"][0] if field == "root" else tables["transcripts"][0]["segments"][0]
            target["future_fact"] = {"must": "survive"}
            with self.assertRaisesRegex(ValueError, "unknown fields"):
                self.write(tables)
            self.assertFalse((self.root / "data").exists())

    def test_ambiguous_input_text_is_not_referenced(self):
        tables = fixture()
        transcript = tables["transcripts"][0]
        transcript["text"] = "甲😀甲😀"
        transcript["segments"] = [{"index": 0, "text": "甲😀", "start": 0, "end": 1}, {"index": 1, "text": "甲😀", "start": 1, "end": 2}]
        transcript["content_sha256"] = v3.json_sha256({k: transcript[k] for k in ("item_id", "method", "language", "model", "time_unit", "text", "segments")})
        self.write(tables)
        doc = json.loads((self.root / "data/documents/r-example.json").read_text(encoding="utf-8"))
        self.assertEqual("甲😀", doc["blocks"][0]["input_text"])
        self.assertNotIn("input_text_ref", doc["blocks"][0])

    def test_atomic_upsert_detaches_hardlinks_and_preserves_other_tables(self):
        original = self.write()
        path = self.root / "data/documents/r-example.json"
        linked = Path(self.temp.name) / "original.json"
        os.link(path, linked)
        before = linked.read_bytes()
        edited = copy.deepcopy(original["edited_transcripts"][0])
        edited["notes_markdown"] = "批量更新"
        paths = v3.write_legacy_updates(self.root, {"edited_transcripts": [edited]})
        self.assertIn(Path("data/documents/r-example.json"), paths)
        self.assertTrue(all(not p.is_absolute() for p in paths))
        self.assertEqual(before, linked.read_bytes())
        self.assertEqual(edited, v3.load_legacy_record(self.root, "r-example"))
        self.assertEqual(original["attributions"], [r for r, _ in v3.iter_legacy_records(self.root, "attributions")])

    def test_artifact_byte_hash_separate_from_canonical_json_hash(self):
        self.write()
        assets = [r for r, _ in v3.iter_native_records(self.root, "assets") if r["kind"] == "review_document"]
        asset = assets[0]
        data = (self.root / asset["local_path"]).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), asset["sha256"])
        self.assertNotEqual(v3.json_sha256(data.decode()), asset["sha256"])
        (self.root / asset["local_path"]).write_bytes(b"changed")
        self.assertTrue(any("artifact byte hash mismatch" in e for e in v3.validate_native(self.root)))

    def test_structure_and_unknown_version_fail_closed(self):
        self.write({})
        self.assertTrue((self.root / "data/documents").is_dir())
        schema_path = self.root / "data/schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema["range_unit"] = "utf16"
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        self.assertTrue(any("range contract" in e for e in v3.validate_native(self.root)))
        schema["schema_version"] = 99
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Unsupported schema version"):
            list(v3.iter_legacy_records(self.root, "items"))

    def test_missing_native_index_and_misplaced_entity_detected(self):
        self.write()
        (self.root / "data/items.jsonl").unlink()
        self.assertTrue(any("Missing native storage" in e for e in v3.validate_native(self.root)))
        self.write()
        path = self.root / "data/documents/r-example.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["kind"] = "post"
        path.write_text(json.dumps(doc), encoding="utf-8")
        self.assertTrue(any("table/entity/kind mismatch" in e for e in v3.validate_native(self.root)))

    def test_native_unknown_or_standalone_asset_is_never_dropped_by_updates(self):
        self.write()
        path = self.root / "data/documents/r-example.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["future_fact"] = "preserve me"
        path.write_text(json.dumps(doc), encoding="utf-8")
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            v3.write_legacy_updates(self.root, {})
        self.assertEqual(before, path.read_bytes())
        del doc["future_fact"]
        path.write_text(json.dumps(doc), encoding="utf-8")
        asset_path = self.root / "data/assets.jsonl"
        with asset_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"id": "z-standalone", "kind": "archive", "name": "independent.zip"}) + "\n")
        before = asset_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "standalone native asset"):
            v3.write_legacy_updates(self.root, {})
        self.assertEqual(before, asset_path.read_bytes())

    def test_noop_batch_preserves_document_bytes(self):
        self.write()
        paths = sorted((self.root / "data/documents").glob("*.json"))
        before = {p: p.read_bytes() for p in paths}
        self.assertEqual([], v3.write_legacy_updates(self.root, {}))
        self.assertEqual(before, {p: p.read_bytes() for p in paths})

    def test_scalar_inputs_and_annotation_targets_fail_before_noop_write(self):
        self.write()
        path = self.root / "data/documents/r-example.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document["inputs"].append({"role": "item", "target_id": "c-example"})
        path.write_text(json.dumps(document), encoding="utf-8")
        before = path.read_bytes()
        self.assertTrue(any("scalar input role item" in error for error in v3.validate_native(self.root)))
        with self.assertRaisesRegex(ValueError, "scalar input role item"):
            v3.write_legacy_updates(self.root, {})
        self.assertEqual(before, path.read_bytes())
        document["inputs"].pop()
        path.write_text(json.dumps(document), encoding="utf-8")
        path = self.root / "data/annotations.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        attribution = next(row for row in rows if row["id"] == "s-example")
        attribution["targets"].append({"role": "applies_to", "target_id": "r-example"})
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        before = path.read_bytes()
        self.assertTrue(any("scalar annotation applies_to" in error for error in v3.validate_native(self.root)))
        with self.assertRaisesRegex(ValueError, "scalar annotation applies_to"):
            v3.write_legacy_updates(self.root, {})
        self.assertEqual(before, path.read_bytes())

    def test_confirmation_indices_are_contiguous_and_artifact_extra_facts_fail_closed(self):
        self.write()
        path = self.root / "data/annotations.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        next(row for row in rows if row["id"] == "a-confirm")["targets"][1]["confirmation_index"] = 42
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        before = path.read_bytes()
        self.assertTrue(any("unique and contiguous" in error for error in v3.validate_native(self.root)))
        with self.assertRaisesRegex(ValueError, "unique and contiguous"):
            v3.write_legacy_updates(self.root, {})
        self.assertEqual(before, path.read_bytes())
        self.write()
        path = self.root / "data/assets.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        next(row for row in rows if row["kind"] == "review_document")["url"] = "https://example.org/source.md"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "unknown fields: url"):
            v3.write_legacy_updates(self.root, {})
        self.assertEqual(before, path.read_bytes())

    def test_native_projection_roundtrip_guard_preserves_noncanonical_provenance(self):
        tables = fixture()
        tables["edited_transcripts"][0]["text"] = "甲😀甲😀"
        self.write(tables)
        path = self.root / "data/documents/r-example.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document["blocks"][0]["range"] = [2, 4]
        path.write_text(json.dumps(document), encoding="utf-8")
        self.assertEqual([], v3.validate_native(self.root))
        before = {p: p.read_bytes() for p in (self.root / "data").rglob("*") if p.is_file()}
        with self.assertRaisesRegex(ValueError, "no lossless legacy projection"):
            v3.write_legacy_updates(self.root, {})
        self.assertEqual(before, {p: p.read_bytes() for p in (self.root / "data").rglob("*") if p.is_file()})

    def test_inline_item_references_and_member_shapes_are_checked(self):
        for field in ("parent_id", "members", "relations", "member_shape"):
            with self.subTest(field=field):
                self.write()
                path = self.root / "data/items.jsonl"
                rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
                item = next(row for row in rows if row["id"] == ("c-example" if field in ("members", "member_shape") else "i-example"))
                if field == "parent_id":
                    item[field] = "i-missing"
                elif field == "members":
                    item[field][0]["item_id"] = "i-missing"
                elif field == "relations":
                    item[field] = [{"kind": "related", "target_item_id": "i-missing"}]
                else:
                    item["members"] = ["i-example"]
                if field in ("parent_id", "relations"):
                    item["_legacy"]["keys"].append(field)
                path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
                before = path.read_bytes()
                errors = v3.validate_native(self.root)
                self.assertTrue(any("missing item target" in error or "requires item_id" in error for error in errors), errors)
                with self.assertRaises(ValueError):
                    v3.write_legacy_updates(self.root, {})
                self.assertEqual(before, path.read_bytes())

    def test_stale_content_hash_rejected(self):
        tables = fixture()
        tables["transcripts"][0]["text"] += "different"
        with self.assertRaisesRegex(ValueError, "content hash mismatch"):
            self.write(tables)


if __name__ == "__main__":
    unittest.main()
