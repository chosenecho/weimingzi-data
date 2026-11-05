"""Preserve original evidence and the scope of a source-backed local correction."""

import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from weimingzi_corpus.exports import render_review_markdown
from weimingzi_corpus.records import read_json, read_jsonl


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
        directory = ROOT / "data/edited_transcripts"
        if not (directory / (REVISION_ID + ".json")).is_file():
            raise unittest.SkipTest(
                "Canonical corpus is absent from the sparse checkout"
            )
        cls.original = read_json(directory / (ORIGINAL_ID + ".json"))
        cls.revision = read_json(directory / (REVISION_ID + ".json"))
        cls.confirmation = next(
            row
            for row in read_jsonl(ROOT / "data/confirmations.jsonl")
            if row["id"] == CONFIRMATION_ID
        )

    def test_original_draft_and_both_transcripts_remain_byte_identical(self):
        digests = {
            "edited_transcripts/r-a2637d3db4784162ccfd1245.json": "40fc8da795b4d322c62b4dc2c0d294caf63185da6d5a461f1a10fbe3bf8abfc1",
            "transcripts/t-3e7e6612744243e2194ce4ea.json": "e0f972590ea637cc84722455d1ab84f1f31b26b06fad85a4afc94aeb8669d3fd",
            "transcripts/t-21876553f63d294a5a66ae8a.json": "8713117db9f292a01e31f232079f0a303bb35151442d3e23b3e3b15631415409",
        }
        for path, expected in digests.items():
            with self.subTest(path=path):
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

    def test_confirmation_and_training_export_follow_the_local_revision(self):
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
        entry = next(
            row
            for row in read_json(ROOT / "selections/training.json")["entries"]
            if row["item_id"] == self.original["item_id"]
        )
        self.assertEqual(entry["edited_transcript_id"], REVISION_ID)
        self.assertEqual(entry["confirmation_ids"], [CONFIRMATION_ID])
        self.assertIn(REVISION_ID, confirmation["edited_transcript_ids"])
        self.assertEqual(self.revision["confirmation_ids"], [CONFIRMATION_ID])
        review = render_review_markdown(self.revision, {"title": "局部修订核对"})
        self.assertIn(COMMENT_URL, review)
        self.assertIn(confirmation["corrected_text"], review)


if __name__ == "__main__":
    unittest.main()
