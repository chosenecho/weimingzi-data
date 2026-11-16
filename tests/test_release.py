"""The release view picks one head per item and applies confirmations without editing source data."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from weimingzi_corpus import release
from weimingzi_corpus.records import write_json, write_jsonl


def make_edited(record_id, item_id, texts, revision=True, derived_from=None, superseded_by=None, issues=None):
    issues = issues or {}
    record = {
        "id": record_id,
        "kind": "edited_transcript",
        "schema_version": 2,
        "item_id": item_id,
        "time_unit": "ms",
        "text": "\n\n".join(texts),
        "paragraphs": [
            {
                "index": index,
                "text": text,
                "input_text": text,
                "input_unit_labels": [],
                "issues": issues.get(index, []),
                "start": index * 1000,
                "end": index * 1000 + 900,
            }
            for index, text in enumerate(texts)
        ],
        "metadata": {"revision_id": record_id} if revision else {},
    }
    if derived_from:
        record["derived_from_id"] = derived_from
    if superseded_by:
        record["superseded_by"] = superseded_by
    return record


def make_confirmation(confirmation_id, item_id, original, corrected, edited_ids):
    return {
        "id": confirmation_id,
        "kind": "confirmation",
        "schema_version": 2,
        "item_id": item_id,
        "anchor": {"original_text": original, "original_text_sha256": "x"},
        "corrected_text": corrected,
        "edited_transcript_ids": list(edited_ids),
    }


class HeadRuleTests(unittest.TestCase):
    def test_revision_version_wins_over_derived_base(self):
        newest = make_edited("r-" + "b" * 24, "i-1", ["正文"], derived_from="r-" + "a" * 24)
        oldest = make_edited("r-" + "a" * 24, "i-1", ["正文"], revision=False)
        heads, errors = release.derive_heads({"i-1": sorted([newest["id"], oldest["id"]])}, {
            newest["id"]: newest,
            oldest["id"]: oldest,
        })
        self.assertEqual(errors, [])
        self.assertEqual(heads["i-1"], newest["id"])

    def test_two_candidates_are_not_guessed(self):
        first = make_edited("r-" + "a" * 24, "i-1", ["甲"])
        second = make_edited("r-" + "b" * 24, "i-1", ["乙"])
        heads, errors = release.derive_heads({"i-1": [first["id"], second["id"]]}, {
            first["id"]: first,
            second["id"]: second,
        })
        self.assertEqual(heads, {})
        self.assertEqual([error["code"] for error in errors], ["HEAD_NOT_UNIQUE"])

    def test_single_version_needs_no_pointer(self):
        only = make_edited("r-" + "a" * 24, "i-1", ["正文"])
        heads, errors = release.derive_heads({"i-1": [only["id"]]}, {only["id"]: only})
        self.assertEqual((heads, errors), ({"i-1": only["id"]}, []))


class LocateTests(unittest.TestCase):
    def record(self, texts):
        return make_edited("r-" + "a" * 24, "i-1", texts)

    def test_original_present_is_apply(self):
        record = self.record(["公益小组不是目的"])
        confirmation = make_confirmation("a-1", "i-1", "公益小组不是目的", "公益小组不是目的。", [record["id"]])
        place = release.locate(record, confirmation)
        self.assertEqual((place["state"], place["paragraph_index"]), ("apply", 0))

    def test_corrected_present_counts_as_already_applied(self):
        record = self.record(["公益小组不是目的"])
        confirmation = make_confirmation("a-1", "i-1", "公益活动、公益小组不是目的", "公益小组不是目的", [record["id"]])
        self.assertEqual(release.locate(record, confirmation)["state"], "already_applied")

    def test_identical_text_is_no_change(self):
        record = self.record(["原文"])
        confirmation = make_confirmation("a-1", "i-1", "原文", "原文", [record["id"]])
        self.assertEqual(release.locate(record, confirmation)["state"], "no_change")

    def test_missing_anchor_is_orphan(self):
        record = self.record(["别的正文"])
        confirmation = make_confirmation("a-1", "i-1", "找不到", "改后", [record["id"]])
        self.assertEqual(release.locate(record, confirmation)["state"], "orphan")


class ApplyTextTests(unittest.TestCase):
    def test_replacement_touches_only_targeted_paragraph(self):
        record = make_edited("r-" + "a" * 24, "i-1", ["第一段", "第二段"])
        confirmation = make_confirmation("a-1", "i-1", "第二段", "第二段改", [record["id"]])
        texts = release.apply_text(record["paragraphs"], {"a-1": confirmation}, [
            {"confirmation_id": "a-1", "paragraph_index": 1, "state": "apply"}
        ])
        self.assertEqual(texts[0], "第一段")
        self.assertEqual(texts[1], "第二段改")
        self.assertEqual(record["paragraphs"][1]["text"], "第二段")


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "data" / "edited_transcripts").mkdir(parents=True)
        (self.root / "selections").mkdir()

    def tearDown(self):
        self.directory.cleanup()

    def write_corpus(self):
        head = make_edited("r-" + "b" * 24, "i-1", ["公益小组不是目的"], derived_from="r-" + "a" * 24)
        stale = make_edited("r-" + "a" * 24, "i-1", ["公益活动、公益小组不是目的"], revision=False, superseded_by=head["id"])
        write_json(self.root / "data" / "edited_transcripts" / (head["id"] + ".json"), head)
        write_json(self.root / "data" / "edited_transcripts" / (stale["id"] + ".json"), stale)
        write_jsonl(self.root / "data" / "items.jsonl", [
            {
                "id": "i-1",
                "kind": "video_part",
                "schema_version": 2,
                "title": "示例",
                "urls": ["https://www.bilibili.com/video/BV1"],
            }
        ])
        write_jsonl(self.root / "data" / "confirmations.jsonl", [
            make_confirmation("a-" + "1" * 24, "i-1", "公益活动、公益小组不是目的", "公益小组不是目的", [head["id"], stale["id"]])
        ])
        return head, stale

    def write_selection(self, head_id, confirmation_id=None):
        selection = {
            "schema_version": 2,
            "policy_version": "release-1",
            "generated_from_commit": None,
            "items": [
                {
                    "item_id": "i-1",
                    "head_edited_id": head_id,
                    "applied_confirmation_ids": [confirmation_id] if confirmation_id else [],
                    "excluded_paragraphs": [],
                }
            ],
        }
        (self.root / "selections" / "release.json").write_text(json.dumps(selection), encoding="utf-8")

    def test_projection_uses_head_only(self):
        head, stale = self.write_corpus()
        self.write_selection(head["id"], "a-" + "1" * 24)
        report = release.validate_release(self.root)
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["counts"]["items"], 1)
        self.assertEqual(report["counts"]["paragraphs"], 1)
        built = release.build_release(self.root, release.read_selection(self.root))
        self.assertEqual(built["rows"][0]["text"], "公益小组不是目的")
        self.assertEqual(built["rows"][0]["edited_id"], head["id"])
        self.assertEqual(built["rows"][0]["issue_state"], "clean")
        self.assertEqual(built["rows"][0]["time_unit"], "ms")

    def test_missing_pointer_is_reported(self):
        head, _ = self.write_corpus()
        self.write_selection(head["id"], "a-" + "1" * 24)
        selection = release.read_selection(self.root)
        selection["items"] = []
        (self.root / "selections" / "release.json").write_text(json.dumps(selection), encoding="utf-8")
        report = release.validate_release(self.root)
        self.assertEqual([error["code"] for error in report["errors"]], ["HEAD_NOT_UNIQUE"])

    def write_flagged_corpus(self, with_confirmation=False):
        head = make_edited("r-" + "b" * 24, "i-1", ["干净段", "原文句"], issues={1: [{"note": "疑点"}]})
        write_json(self.root / "data" / "edited_transcripts" / (head["id"] + ".json"), head)
        write_jsonl(
            self.root / "data" / "items.jsonl",
            [{"id": "i-1", "kind": "video_part", "schema_version": 2, "title": "示例", "urls": []}],
        )
        rows = []
        if with_confirmation:
            rows.append(make_confirmation("a-" + "1" * 24, "i-1", "原文句", "原文句改", [head["id"]]))
        write_jsonl(self.root / "data" / "confirmations.jsonl", rows)
        return head

    def test_clean_policy_drops_flagged_paragraph(self):
        head = self.write_flagged_corpus()
        self.write_selection(head["id"])
        report = release.validate_release(self.root)
        self.assertEqual(report["counts"]["paragraphs"], 1)
        self.assertEqual(report["counts"]["dropped_paragraphs"], 1)
        self.assertEqual(report["counts"]["transcripts_included"], 1)
        full = release.build_release(self.root, release.read_selection(self.root), policy="full")
        self.assertEqual(len(full["rows"]), 2)
        self.assertEqual(full["rows"][1]["issue_state"], "flagged")

    def test_confirmed_paragraph_survives_clean_policy(self):
        head = self.write_flagged_corpus(with_confirmation=True)
        self.write_selection(head["id"], "a-" + "1" * 24)
        built = release.build_release(self.root, release.read_selection(self.root))
        self.assertEqual(len(built["rows"]), 2)
        self.assertEqual(built["rows"][1]["issue_state"], "confirmed")
        self.assertEqual(built["rows"][1]["text"], "原文句改")
        self.assertEqual(built["counts"]["confirmed_paragraphs"], 1)

    def test_unlisted_confirmation_is_reported(self):
        head, _ = self.write_corpus()
        self.write_selection(head["id"])
        report = release.validate_release(self.root)
        self.assertEqual([error["code"] for error in report["errors"]], ["CONFIRMATION_ORPHAN"])

    def test_absent_selection_is_skipped(self):
        self.write_corpus()
        self.assertTrue(release.validate_release(self.root)["skipped"])

    def test_export_writes_manifest(self):
        head, _ = self.write_corpus()
        self.write_selection(head["id"], "a-" + "1" * 24)
        selection = release.read_selection(self.root)
        built = release.build_release(self.root, selection)
        output = self.root / "out" / "release_paragraphs.jsonl"
        manifest = release.write_release(self.root, output, built, selection)
        self.assertEqual(manifest["counts"]["paragraphs"], 1)
        self.assertEqual(manifest["policy"], "clean")
        self.assertTrue(output.is_file())
        self.assertEqual(len(manifest["release_paragraphs_sha256"]), 64)
        row = json.loads(output.read_text(encoding="utf-8").strip())
        self.assertEqual(row["paragraph_id"], head["id"] + ":p0")


if __name__ == "__main__":
    unittest.main()
