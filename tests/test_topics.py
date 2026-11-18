"""Optional thematic rules select native item records with explicit reasons."""
from pathlib import Path
import tempfile
import unittest

from native_fixtures import fixture_records, rid, write_corpus
from weimingzi_corpus.coverage import CoverageIndex
from weimingzi_corpus.records import validate_corpus, write_json
from weimingzi_corpus.topics import definitions, generate_topic_catalog, normalized, select_topic, topic_report


class TopicTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.records = write_corpus(self.root)
        self.topic = {"id": "fixture", "title": "测试专题", "rules": {"collection_ids": [], "title_prefixes": [], "exact_tags": [], "include_chapter_supplements": False}, "manual_inclusions": []}

    def save_topic(self):
        write_json(self.root / "selections/topics.json", {"format": "thematic-index/v1", "topics": [self.topic]})

    def test_source_collection_uses_items_kind_and_preserves_member_reason(self):
        self.topic["rules"]["collection_ids"] = [rid("collection")]
        rows = select_topic(CoverageIndex(self.root), self.topic)
        self.assertEqual([row["item_id"] for row in rows], [rid("video")])
        self.assertEqual(rows[0]["inclusion_reasons"][0]["member"], {"item_id": rid("video")})
        self.assertEqual(rows[0]["role"], "core")

    def test_normalized_titles_exact_nested_tags_and_no_uploader_inference(self):
        self.records["items"][0].update(title="ＡＢＣ 课程", metadata={"tags": [["专题"], "另一个"], "uploader": "误命中"})
        write_corpus(self.root, self.records)
        self.topic["rules"].update(title_prefixes=["abc"], exact_tags=[" 专 题 ", "误命中"])
        rows = select_topic(CoverageIndex(self.root), self.topic)
        self.assertEqual(len(rows), 1)
        self.assertEqual({reason["rule"] for reason in rows[0]["inclusion_reasons"]}, {"normalized_title_prefix", "exact_tag"})
        self.assertEqual(normalized(" Ａ b C "), "abc")

    def test_parent_deduplicates_part_and_preserves_manual_evidence(self):
        self.topic["rules"]["collection_ids"] = [rid("collection")]
        self.topic["manual_inclusions"] = [{"item_id": rid("part"), "role": "introductory", "evidence": "用户指定首段导入"}]
        rows = select_topic(CoverageIndex(self.root), self.topic)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["item_id"], rid("video"))
        self.assertEqual(rows[0]["role"], "introductory")
        reason = rows[0]["inclusion_reasons"][-1]
        self.assertEqual(reason["evidence"], "用户指定首段导入")
        self.assertEqual(reason["matched_item_id"], rid("part"))
        self.save_topic()
        self.assertEqual(len(definitions(self.root)), 1)
        self.topic["manual_inclusions"][0]["evidence"] = ""
        self.save_topic()
        with self.assertRaisesRegex(ValueError, "evidence"):
            definitions(self.root)

    def test_explicit_chapter_supplement_and_native_record_report(self):
        supplement = {"id": rid("supplement"), "kind": "audio_recording", "title": "补充", "identifiers": {}, "relations": [{"kind": "chapter_supplement_not_audio_identity", "target_item_id": rid("part"), "evidence": "人工关联"}]}
        self.records["items"].append(supplement)
        write_corpus(self.root, self.records)
        self.topic["rules"].update(collection_ids=[rid("collection")], include_chapter_supplements=True)
        index = CoverageIndex(self.root)
        rows = select_topic(index, self.topic)
        self.assertEqual({row["role"] for row in rows}, {"core", "chapter_supplement"})
        report = topic_report(index, self.topic, include_records=True)
        core = next(row for row in report["entries"] if row["role"] == "core")
        self.assertTrue(all("inputs" in row["record"] for row in core["coverage"]["layers"]["direct"]["records"]))

    def test_optional_rules_do_not_gate_native_validation_or_import(self):
        self.assertEqual(generate_topic_catalog(self.root), {})
        self.topic["rules"]["collection_ids"] = [rid("missing")]
        self.save_topic()
        self.assertEqual(validate_corpus(self.root)["documents"], 5)
        with self.assertRaisesRegex(ValueError, "collection"):
            generate_topic_catalog(self.root)

    def test_catalog_rebuild_check_and_topic_definition_failures(self):
        self.topic["rules"]["collection_ids"] = [rid("collection")]
        self.save_topic()
        counts = generate_topic_catalog(self.root)
        self.assertEqual(counts, {"topics": 1, "topic_entries": 1})
        self.assertEqual(generate_topic_catalog(self.root, check=True), counts)
        path = self.root / "docs/catalog/topics.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("data/documents/", text)
        path.write_text("stale", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "stale"):
            generate_topic_catalog(self.root, check=True)
        self.topic["rules"]["include_chapter_supplements"] = None
        self.save_topic()
        with self.assertRaisesRegex(ValueError, "boolean"):
            definitions(self.root)


if __name__ == "__main__":
    unittest.main()
