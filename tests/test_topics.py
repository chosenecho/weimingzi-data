"""Thematic membership is derived with evidence, separate from source data."""

import copy
import io
import json
import unittest
from contextlib import redirect_stdout, redirect_stderr

import test_coverage as fixtures
from weimingzi_corpus.cli import main
from weimingzi_corpus.coverage import CoverageIndex
from weimingzi_corpus.exports import generate_catalog_docs
from weimingzi_corpus.records import make_record_id, write_json, write_jsonl
from weimingzi_corpus.topics import definitions, select_topic, topic_report


class TopicTests(unittest.TestCase):
    setUp = fixtures.CoverageTests.setUp
    tearDown = fixtures.CoverageTests.tearDown
    save_transcript = fixtures.CoverageTests.save_transcript
    fixture = fixtures.CoverageTests.fixture
    edited = fixtures.CoverageTests.edited

    def configure(self):
        self.fixture()
        self.video.update(
            title="【我是谁】基本情况", metadata={"tags": [["主义主义", "工益公益"]]}
        )
        self.youtube.update(title="［主义主义］　核心材料")
        self.variant.update(
            title="其他材料",
            metadata={"uploader": "主义主义", "description": "主义主义"},
        )
        self.sibling["title"] = "系列中的一章"
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
        self.collection = {
            "schema_version": 2,
            "kind": "video_series",
            "id": make_record_id("c", "series"),
            "title": "来源系列",
            "members": [{"item_id": self.sibling["id"], "position": 1}],
        }
        write_jsonl(self.root / "data/collections.jsonl", [self.collection])
        self.topic = {
            "id": "ismism",
            "title": "主义主义",
            "rules": {
                "collection_ids": [self.collection["id"]],
                "title_prefixes": ["[主义主义]"],
                "exact_tags": ["主义主义"],
                "include_chapter_supplements": True,
            },
            "manual_inclusions": [
                {
                    "item_id": self.video["id"],
                    "role": "introductory",
                    "evidence": "明确确认的导入材料",
                }
            ],
        }
        self.save_topic()

    def save_topic(self):
        write_json(
            self.root / "selections/topics.json",
            {"format": "thematic-index/v1", "topics": [self.topic]},
        )

    def test_tag_title_collection_manual_and_supplement_have_distinct_evidence(self):
        self.configure()
        sources = {
            name: (self.root / ("data/" + name + ".jsonl")).read_bytes()
            for name in ("items", "collections")
        }
        entries = {
            r["item_id"]: r
            for r in select_topic(CoverageIndex(self.root), definitions(self.root)[0])
        }
        intro = entries[self.video["id"]]
        self.assertEqual(intro["role"], "introductory")
        self.assertEqual(
            {r["rule"] for r in intro["inclusion_reasons"]},
            {"exact_tag", "manual_inclusion", "source_collection"},
        )
        self.assertNotIn(self.sibling["id"], entries)
        self.assertEqual(entries[self.youtube["id"]]["role"], "core")
        self.assertEqual(entries[self.supplement["id"]]["role"], "chapter_supplement")
        self.assertNotIn(self.variant["id"], entries)
        for name, original in sources.items():
            self.assertEqual(
                (self.root / ("data/" + name + ".jsonl")).read_bytes(), original
            )

    def test_tag_only_entry_is_related_and_does_not_require_a_title_match(self):
        self.configure()
        self.topic["manual_inclusions"] = []
        self.topic["rules"]["collection_ids"] = []
        intro = next(
            r
            for r in select_topic(CoverageIndex(self.root), self.topic)
            if r["item_id"] == self.video["id"]
        )
        self.assertEqual(intro["role"], "related")
        self.assertEqual(intro["inclusion_reasons"][0]["observed_tag"], "主义主义")

    def test_export_preserves_variants_review_state_and_all_layers(self):
        self.configure()
        row = self.edited(self.item, "intro")
        self.edited(self.item, "partial", complete=False)
        report = topic_report(
            CoverageIndex(self.root), self.topic, include_records=True
        )
        intro = next(e for e in report["entries"] if e["item_id"] == self.video["id"])
        rows = intro["coverage"]["layers"]["direct"]["records"]
        self.assertEqual(next(r["record"] for r in rows if r["id"] == row["id"]), row)
        self.assertEqual(report["counts"]["direct"]["edited_transcripts"], 2)
        self.assertEqual(report["counts"]["direct"]["complete_text_candidates"], 1)
        self.assertEqual(report["counts"]["direct"]["human_reviewed_complete_texts"], 0)

    def test_invalid_definition_and_unknown_references_fail_closed(self):
        self.configure()
        original = copy.deepcopy(self.topic)
        for bad in (
            {**original, "id": ""},
            {**original, "manual_inclusions": [{}]},
            {**original, "rules": {**original["rules"], "exact_tags": "主义主义"}},
        ):
            self.topic = bad
            self.save_topic()
            with self.assertRaises(ValueError):
                definitions(self.root)
        index = CoverageIndex(self.root)
        for field in ("manual_inclusions", "rules"):
            bad = copy.deepcopy(original)
            if field == "rules":
                bad["rules"]["collection_ids"] = ["missing"]
            else:
                bad["manual_inclusions"][0]["item_id"] = "missing"
            with self.assertRaises(ValueError):
                select_topic(index, bad)

    def test_cli_full_export_and_output_protection(self):
        self.configure()
        row = self.edited(self.item, "intro")
        output = self.root / ".cache/topic.json"
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = main(
                [
                    "--root",
                    str(self.root),
                    "topic",
                    "主义主义",
                    "--include-records",
                    "--output",
                    str(output),
                ]
            )
            denied = main(
                [
                    "--root",
                    str(self.root),
                    "topic",
                    "ismism",
                    "--output",
                    str(self.root / "data/items.jsonl"),
                ]
            )
        self.assertEqual(code, 0)
        self.assertEqual(denied, 1)
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertTrue(
            any(
                r["record"] == row
                for e in report["entries"]
                for r in e["coverage"]["layers"]["direct"]["records"]
            )
        )

    def test_generated_navigation_is_rebuildable(self):
        self.configure()
        generate_catalog_docs(self.root)
        text = (self.root / "docs/catalog/topics.md").read_text(encoding="utf-8")
        self.assertIn("【我是谁】基本情况", text)
        self.assertIn("精确标签：主义主义", text)
        self.assertIn("introductory", text)
        self.assertIn(
            "catalog/topics.md",
            (self.root / "docs/INDEX.md").read_text(encoding="utf-8"),
        )
        generate_catalog_docs(self.root, check=True)


class RepositoryTopicTests(unittest.TestCase):
    def test_issue_three_introduction_is_included_with_original_evidence_and_draft(
        self,
    ):
        index = fixtures.repository_index()
        topic = definitions(index.root)[0]
        entry = next(
            e
            for e in select_topic(index, topic)
            if e["item_id"] == "i-cdcd00c2682b005c40ff7ab3"
        )
        self.assertEqual(entry["role"], "introductory")
        self.assertEqual(
            {r["rule"] for r in entry["inclusion_reasons"]},
            {"exact_tag", "manual_inclusion"},
        )
        rows = index.report(entry["item_id"])["layers"]["direct"]["records"]
        row = next(r for r in rows if r["id"] == "r-3b42fcf5ff4728f644c2b7c5")
        self.assertTrue(row["is_complete"])
        self.assertTrue(row["requires_review"])
        self.assertFalse(row["is_fully_human_reviewed"])


if __name__ == "__main__":
    unittest.main()
