"""Preserve original evidence and the scope of a source-backed local correction."""

import copy
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from weimingzi_corpus.exports import render_review_markdown
import test_corpus as fixtures
from weimingzi_corpus.records import (
    content_record_path, iter_records, json_sha256, load_content_record, make_record_id,
    validate_corpus, write_record_updates,
)
from weimingzi_corpus.schema_v3 import is_v3, migrate_v2


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_ID = "r-a2637d3db4784162ccfd1245"
REVISION_ID = "r-97fac763234451df943669a2"
CONFIRMATION_ID = "a-813baf77c7e28b3973cd42e7"
COMMENT_URL = (
    "https://github.com/chosenecho/weimingzi-data/issues/6#issuecomment-6649160627"
)


class RepositoryLocalRevisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not content_record_path(ROOT, "edited_transcripts", REVISION_ID).is_file():
            raise unittest.SkipTest(
                "Canonical corpus is absent from the sparse checkout"
            )
        cls.original = load_content_record(ROOT, ORIGINAL_ID)
        cls.revision = load_content_record(ROOT, REVISION_ID)
        cls.confirmation = next(
            row
            for row, _ in iter_records(ROOT, "confirmations")
            if row["id"] == CONFIRMATION_ID
        )

    def test_original_draft_and_both_transcripts_remain_byte_identical(self):
        digests = {
            "edited_transcripts/r-a2637d3db4784162ccfd1245.json": "40fc8da795b4d322c62b4dc2c0d294caf63185da6d5a461f1a10fbe3bf8abfc1",
            "transcripts/t-3e7e6612744243e2194ce4ea.json": "e0f972590ea637cc84722455d1ab84f1f31b26b06fad85a4afc94aeb8669d3fd",
            "transcripts/t-21876553f63d294a5a66ae8a.json": "8713117db9f292a01e31f232079f0a303bb35151442d3e23b3e3b15631415409",
        }
        semantic_digests = {
            ORIGINAL_ID: "60fbcc62de501da9907abbef7c26c1d8abd3c3834691ca0a570ef80c29a0515c",
            "t-3e7e6612744243e2194ce4ea": "4d024e9dbdc5b1cfdb7983e563eca0c24c992086b8c6d4593562174cc44df619",
            "t-21876553f63d294a5a66ae8a": "3446749d1c887c21dd2996ba396d07ad6b6f9b509fdcaa503fa043cb2ab35401",
        }
        for path, expected in digests.items():
            with self.subTest(path=path):
                record_id = Path(path).stem
                self.assertEqual(
                    json_sha256(load_content_record(ROOT, record_id)),
                    semantic_digests[record_id],
                )
                if not is_v3(ROOT):
                    self.assertEqual(
                        hashlib.sha256((ROOT / "data" / path).read_bytes()).hexdigest(),
                        expected,
                    )

    def test_only_confirmed_clause_changes_and_review_scope_is_preserved(self):
        original, revision = self.original, self.revision
        old = "公益活动、公益小组不是目的，公益活动才是目的。"
        new = "公益小组不是目的，公益活动才是目的。"
        self.assertEqual(revision["derived_from_id"], ORIGINAL_ID)
        self.assertEqual(revision["text"], original["text"].replace(old, new))
        self.assertEqual(len(revision["paragraphs"]), len(original["paragraphs"]))
        for index, (before, after) in enumerate(
            zip(original["paragraphs"], revision["paragraphs"])
        ):
            if index != 48:
                self.assertEqual(after, before)
                continue
            self.assertEqual(after["text"], before["text"].replace(old, new))
            self.assertEqual(
                {k: v for k, v in after.items() if k not in {"text", "issues"}},
                {k: v for k, v in before.items() if k not in {"text", "issues"}},
            )
            self.assertEqual(after["issues"][:-1], before["issues"])
            self.assertIn(COMMENT_URL, after["issues"][-1]["note"])
        for key in ("quality", "is_complete", "model", "transcript_ids", "time_unit"):
            self.assertEqual(revision[key], original[key])
        self.assertTrue(revision["quality"]["requires_review"])
        self.assertFalse(revision["quality"]["is_fully_human_reviewed"])
        self.assertEqual(
            revision["text"],
            "\n\n".join(p["text"] for p in revision["paragraphs"]) + "\n",
        )

    def test_confirmation_links_and_anchors_follow_the_local_revision(self):
        confirmation = self.confirmation
        self.assertEqual(confirmation["scope"], "local_text_or_term")
        self.assertEqual(confirmation["anchor"]["paragraph_index"], 48)
        self.assertEqual(
            confirmation["anchor"]["original_text"],
            self.original["paragraphs"][48]["text"],
        )
        self.assertEqual(
            confirmation["corrected_text"], self.revision["paragraphs"][48]["text"]
        )
        self.assertEqual(
            confirmation["anchor"]["original_text_sha256"],
            "be513b20ddac444ae163c94ef64a4b7f02d5a030d8ea3e579df458bcd04ed070",
        )
        for text, digest in (
            (
                confirmation["anchor"]["original_text"],
                confirmation["anchor"]["original_text_sha256"],
            ),
            (confirmation["corrected_text"], confirmation["corrected_text_sha256"]),
        ):
            self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), digest)
        evidence = confirmation["confirmation"]
        self.assertEqual(evidence["source_url"], COMMENT_URL)
        self.assertTrue(evidence["user_reported_reviewed_original_video"])
        self.assertFalse(evidence["assistant_listened_to_audio"])
        self.assertEqual(evidence["reported_video_position_seconds"], 2032)
        self.assertEqual(self.revision["item_id"], self.original["item_id"])
        self.assertEqual(confirmation["item_id"], self.original["item_id"])
        self.assertIn(ORIGINAL_ID, confirmation["edited_transcript_ids"])
        self.assertIn(REVISION_ID, confirmation["edited_transcript_ids"])
        self.assertEqual(self.revision["confirmation_ids"], [CONFIRMATION_ID])
        review = render_review_markdown(self.revision, {"title": "局部修订核对"})
        self.assertIn(COMMENT_URL, review)
        self.assertIn(confirmation["corrected_text"], review)


class ConfirmationValidationTests(unittest.TestCase):
    setUp = fixtures.CorpusTests.setUp
    tearDown = fixtures.CorpusTests.tearDown
    save_transcript = fixtures.CorpusTests.save_transcript
    create_edited_transcript = fixtures.CorpusTests.create_edited_transcript

    def confirmation_fixture(self):
        original = self.create_edited_transcript()
        revision = copy.deepcopy(original)
        revision.update(id=make_record_id("r", "corrected"), text="物质的世界。")
        revision["paragraphs"][0]["text"] = revision["text"]
        confirmation = {
            "schema_version": 2, "id": make_record_id("a", "confirmation"),
            "kind": "confirmation", "item_id": self.item["id"],
            "edited_transcript_ids": [original["id"], revision["id"]],
            "anchor": {
                "paragraph_index": 0, "original_text": original["text"],
                "original_text_sha256": hashlib.sha256(original["text"].encode()).hexdigest(),
            },
            "corrected_text": revision["text"],
            "corrected_text_sha256": hashlib.sha256(revision["text"].encode()).hexdigest(),
            "scope": "local_text_or_term", "status": "confirmed",
            "confirmation": {"assistant_listened_to_audio": False},
        }
        revision["confirmation_ids"] = [confirmation["id"]]
        write_record_updates(self.root, {
            "edited_transcripts": [original, revision], "confirmations": [confirmation],
        })
        return original, revision, confirmation

    def test_missing_confirmation_id_is_checked(self):
        row = self.create_edited_transcript()
        row["confirmation_ids"] = [make_record_id("a", "missing")]
        write_record_updates(self.root, {"edited_transcripts": [row]})
        with self.assertRaisesRegex(ValueError, "unresolved confirmations"):
            validate_corpus(self.root)

    def test_each_target_must_have_original_or_corrected_anchor(self):
        original, revision, _ = self.confirmation_fixture()
        revision.update(text="完全无关的另一段。")
        revision["paragraphs"][0]["text"] = revision["text"]
        write_record_updates(self.root, {"edited_transcripts": [revision]})
        with self.assertRaisesRegex(ValueError, "cannot be located.*" + revision["id"]):
            validate_corpus(self.root)
        self.assertEqual(original["quality"]["is_fully_human_reviewed"], False)

    def test_target_from_another_item_is_rejected(self):
        _, revision, _ = self.confirmation_fixture()
        other = copy.deepcopy(self.item)
        other["id"] = make_record_id("i", "other")
        revision["item_id"] = other["id"]
        revision.pop("confirmation_ids")
        revision["transcript_ids"] = []
        write_record_updates(self.root, {"items": [other], "edited_transcripts": [revision]})
        with self.assertRaisesRegex(ValueError, "confirmation target belongs to a different item"):
            validate_corpus(self.root)

    def test_claimed_confirmation_must_apply_to_claiming_revision(self):
        _, revision, confirmation = self.confirmation_fixture()
        confirmation["edited_transcript_ids"] = [make_record_id("r", "fixture")]
        write_record_updates(self.root, {"confirmations": [confirmation]})
        with self.assertRaisesRegex(ValueError, "does not apply"):
            validate_corpus(self.root)

    def test_native_projection_keeps_local_confirmation_scope_and_paths(self):
        original, revision, confirmation = self.confirmation_fixture()
        native_root = self.root / "native"
        migrate_v2(self.root, native_root)
        validate_corpus(native_root)
        for expected in (original, revision):
            self.assertEqual(load_content_record(native_root, expected["id"]), expected)
            self.assertEqual(
                content_record_path(native_root, "edited_transcripts", expected["id"]).parent.name,
                "documents",
            )
        self.assertEqual(next(iter_records(native_root, "confirmations"))[0], confirmation)
        self.assertEqual(next(iter_records(native_root, "edited_transcripts"))[1].parent.name, "documents")
        self.assertTrue(load_content_record(native_root, revision["id"])["quality"]["requires_review"])
        self.assertFalse(load_content_record(native_root, revision["id"])["quality"]["is_fully_human_reviewed"])
        revision["text"] = "完全无关的另一段。"
        revision["paragraphs"][0]["text"] = revision["text"]
        write_record_updates(native_root, {"edited_transcripts": [revision]})
        with self.assertRaisesRegex(ValueError, "cannot be located"):
            validate_corpus(native_root)


if __name__ == "__main__":
    unittest.main()
