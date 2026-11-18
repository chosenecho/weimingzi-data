"""Local human applicability, adoption and whole-graph facts in native records."""

import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from native_fixtures import fixture_records, rid, write_corpus
from weimingzi_corpus.exports import render_review_markdown
from weimingzi_corpus.records import block_text, input_ids, iter_records, load_document, record_path, validate_corpus, write_record_updates

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_ID = "r-a2637d3db4784162ccfd1245"
REVISION_ID = "r-97fac763234451df943669a2"
CONFIRMATION_ID = "a-813baf77c7e28b3973cd42e7"
COMMENT_URL = "https://github.com/chosenecho/weimingzi-data/issues/6#issuecomment-6649160627"


def targets(annotation, role):
    return [edge["target_id"] for edge in annotation["targets"] if edge["role"] == role]


class RepositoryLocalRevisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not record_path(ROOT, "documents", REVISION_ID).is_file():
            raise unittest.SkipTest("Canonical corpus is absent from this checkout")
        cls.original = load_document(ROOT, ORIGINAL_ID)
        cls.revision = load_document(ROOT, REVISION_ID)
        cls.confirmation = next(row for row, _ in iter_records(ROOT, "annotations", kind="confirmation") if row["id"] == CONFIRMATION_ID)

    def test_only_confirmed_clause_changes_with_original_quality_and_time(self):
        original, revision = self.original, self.revision
        old = "公益活动、公益小组不是目的，公益活动才是目的。"
        new = "公益小组不是目的，公益活动才是目的。"
        self.assertEqual(input_ids(revision, "derived_from"), [ORIGINAL_ID])
        self.assertEqual(revision["text"], original["text"].replace(old, new))
        self.assertEqual(len(revision["blocks"]), len(original["blocks"]))
        for index, (before, after) in enumerate(zip(original["blocks"], revision["blocks"])):
            with self.subTest(block=index):
                expected = block_text(original, before)
                self.assertEqual(block_text(revision, after), expected.replace(old, new) if index == 48 else expected)
                # Offsets shift with text length; original timing and input snapshots do not.
                for key in before.keys() - {"range", "literal", "issues"}:
                    self.assertEqual(after[key], before[key])
                if index == 48:
                    self.assertEqual(after["issues"][:-1], before["issues"])
                    self.assertIn(COMMENT_URL, after["issues"][-1]["note"])
                else:
                    self.assertEqual(after.get("issues"), before.get("issues"))
        for key in ("quality", "is_complete", "model", "time_unit"):
            self.assertEqual(revision[key], original[key])
        self.assertEqual(input_ids(revision, "transcript"), input_ids(original, "transcript"))
        self.assertTrue(revision["quality"]["requires_review"])
        self.assertFalse(revision["quality"]["is_fully_human_reviewed"])

    def test_historical_confirmation_retains_applicability_and_adoption(self):
        confirmation = self.confirmation
        self.assertEqual(confirmation["scope"], "local_text_or_term")
        self.assertEqual(confirmation["anchor"]["paragraph_index"], 48)
        self.assertEqual(confirmation["anchor"]["original_text"], block_text(self.original, self.original["blocks"][48]))
        self.assertEqual(confirmation["corrected_text"], block_text(self.revision, self.revision["blocks"][48]))
        self.assertEqual(confirmation["anchor"]["original_text_sha256"], "be513b20ddac444ae163c94ef64a4b7f02d5a030d8ea3e579df458bcd04ed070")
        for text, digest in ((confirmation["anchor"]["original_text"], confirmation["anchor"]["original_text_sha256"]),
                             (confirmation["corrected_text"], confirmation["corrected_text_sha256"])):
            self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), digest)
        self.assertIn(ORIGINAL_ID, targets(confirmation, "applies_to"))
        self.assertIn(REVISION_ID, targets(confirmation, "revision"))
        adoption = next(t for t in confirmation["targets"] if t["role"] == "revision" and t["target_id"] == REVISION_ID)
        self.assertEqual(adoption["order"], 0)
        self.assertEqual(targets(confirmation, "item"), input_ids(self.original, "item"))
        evidence = confirmation["confirmation"]
        self.assertEqual(evidence["source_url"], COMMENT_URL)
        self.assertTrue(evidence["user_reported_reviewed_original_video"])
        self.assertFalse(evidence["assistant_listened_to_audio"])
        self.assertEqual(evidence["reported_video_position_seconds"], 2032)
        review = render_review_markdown(self.revision, {"title": "局部修订核对"}, ROOT)
        self.assertIn(COMMENT_URL, review)
        self.assertIn(confirmation["corrected_text"], review)


class NativeLocalRevisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="native-revision-test-")
        self.root = Path(self.temp.name)
        self.records = write_corpus(self.root)
        validate_corpus(self.root)
        self.original = self.records["documents"][1]
        self.revision = self.records["documents"][2]
        self.confirmation = self.records["annotations"][0]

    def tearDown(self):
        self.temp.cleanup()

    def test_native_fixture_has_separate_applicable_and_adopted_facts(self):
        self.assertEqual(targets(self.confirmation, "applies_to"), [self.original["id"]])
        self.assertEqual(targets(self.confirmation, "revision"), [self.revision["id"]])
        self.assertEqual(input_ids(self.revision, "derived_from"), [self.original["id"]])
        self.assertEqual(input_ids(self.revision, "input_units_from"), [self.original["id"]])
        self.assertFalse(self.revision["quality"]["is_fully_human_reviewed"])
        self.assertTrue(self.revision["quality"]["requires_review"])
        self.assertNotIn("confirmation_ids", self.revision)
        self.assertNotIn("edited_transcript_ids", self.confirmation)

    def test_invalid_local_revisions_fail_before_install(self):
        before = record_path(self.root, "documents", self.revision["id"]).read_bytes()
        for mutate in (
            lambda row: row["targets"][0].update(target_id=rid("another-item")),
            lambda row: row["targets"][1].update(target_id=rid("missing", "r")),
            lambda row: row["anchor"].update(original_text="invented anchor"),
            lambda row: row.update(corrected_text="unrelated correction"),
            lambda row: row["confirmation"].pop("reviewer_label"),
            lambda row: row["targets"][2].update(order=2),
        ):
            with self.subTest(mutate=mutate):
                row = copy.deepcopy(self.confirmation)
                mutate(row)
                with self.assertRaises(ValueError):
                    write_record_updates(self.root, {"annotations": [row]})
                self.assertEqual(record_path(self.root, "documents", self.revision["id"]).read_bytes(), before)
                validate_corpus(self.root)

    def test_changed_adopted_text_cannot_keep_false_evidence(self):
        row = copy.deepcopy(self.revision)
        row["text"] = "完全无关的另一段。"
        row["blocks"] = [{"range": [0, len(row["text"])], "start": 0, "end": 1000}]
        with self.assertRaises(ValueError):
            write_record_updates(self.root, {"documents": [row]})
        self.assertEqual(load_document(self.root, row["id"])["text"], self.revision["text"])

    def test_applicability_does_not_invent_actual_adoption(self):
        row = copy.deepcopy(self.confirmation)
        row["targets"] = [target for target in row["targets"] if target["role"] != "revision"]
        write_record_updates(self.root, {"annotations": [row]})
        validate_corpus(self.root)
        saved = next(r for r, _ in iter_records(self.root, "annotations", kind="confirmation"))
        self.assertEqual(targets(saved, "revision"), [])
        self.assertEqual(input_ids(load_document(self.root, self.revision["id"]), "derived_from"), [self.original["id"]])
        self.assertFalse(load_document(self.root, self.revision["id"])["quality"]["is_fully_human_reviewed"])

    def test_confirmation_does_not_replace_independent_attribution_review(self):
        attribution = copy.deepcopy(self.records["annotations"][1])
        attribution["review"].pop("basis")
        with self.assertRaises(ValueError):
            write_record_updates(self.root, {"annotations": [attribution]})
        self.assertEqual(len(list(iter_records(self.root, "annotations"))), 2)
        validate_corpus(self.root)


if __name__ == "__main__":
    unittest.main()
