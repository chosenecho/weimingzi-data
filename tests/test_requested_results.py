"""Package integrity, mapping and non-destructive admission."""

import copy
import hashlib
import json
import sys
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import test_corpus as fixtures
from weimingzi_corpus.exports import render_subtitles
from weimingzi_corpus.records import iter_records, read_json, write_jsonl
from weimingzi_corpus.requested_results import import_requested_results, package_records


class PackageTests(unittest.TestCase):
    setUp = fixtures.CorpusTests.setUp
    tearDown = fixtures.CorpusTests.tearDown
    save_transcript = fixtures.CorpusTests.save_transcript

    def fixture(self, change=None):
        bv = "BVfixture"
        item = copy.deepcopy(self.item)
        item.update(
            kind="video_part",
            part_number=1,
            identifiers={"bilibili_bvid": [bv]},
            metadata={"cid": [123]},
        )
        write_jsonl(self.root / "data/items.jsonl", [item])
        asr = {
            "transcript_id": 1,
            "video_part_id": 2,
            "run_id": "run",
            "content_sha256": "a" * 64,
            "model_id": 999,
            "language": "Chinese",
            "source_kind": "asr-local",
            "segments": [
                {
                    "ordinal": 0,
                    "start_ms": 100,
                    "end_ms": 1500,
                    "text": self.transcript["text"],
                }
            ],
        }
        proof = {
            "base_transcript_id": 1,
            "model": "fixture",
            "revision_id": "revision",
            "quality_status": "needs-review",
            "human_reviewed": False,
            "blocks": [
                {
                    "original_text": self.transcript["text"],
                    "text": "整理正文。",
                    "start_ms": 100,
                    "end_ms": 1500,
                    "segment_ids": ["t1:s0"],
                    "issues": [
                        {
                            "note": "待听音",
                            "candidate": "候选",
                            "evidence_refs": ["t1:s0"],
                        }
                    ],
                }
            ],
        }
        quality = {
            "transcript_id": 1,
            "video_part_id": 2,
            "run_id": "run",
            "content_sha256": "a" * 64,
            "segment_count": 1,
        }
        meta = {
            "bvid": bv,
            "parts": [
                {
                    "page_index": 0,
                    "cid": 123,
                    "asr_transcript_id": 1,
                    "asr_run_id": "run",
                    "asr_segments": 1,
                    "proofread": {
                        **{k: v for k, v in proof.items() if k != "blocks"},
                        "blocks": 1,
                        "issue_blocks": 1,
                    },
                }
            ],
        }
        values = {
            "metadata.json": meta,
            "asr.json": asr,
            "asr-quality.json": quality,
            "proofread.json": proof,
            "asr.txt": self.transcript["text"],
            "asr.srt": render_subtitles(self.transcript, "srt"),
            "asr.vtt": render_subtitles(self.transcript, "vtt"),
            "ai-draft.md": "整理正文。" + chr(10),
            "review.md": "完整参照稿及附注",
        }
        if change:
            change(values)
        payload = {
            bv + "/" + k: (
                json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v
            ).encode("utf-8")
            for k, v in values.items()
        }
        manifest = {
            "format": "requested-video-results/v1",
            "bvids": [bv],
            "video_count": 1,
            "part_count": 1,
            "editorial_model": "fixture",
            "human_reviewed": False,
            "files": [
                {"path": k, "bytes": len(v), "sha256": hashlib.sha256(v).hexdigest()}
                for k, v in payload.items()
            ],
        }
        path = self.root / "package.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("manifest.json", json.dumps(manifest))
            for name, value in payload.items():
                archive.writestr(name, value)
        return path

    def test_import_is_lossless_idempotent_and_independent_of_filename(self):
        source = self.fixture()
        before = read_json(
            self.root / "data/transcripts" / (self.transcript["id"] + ".json")
        )
        result = import_requested_results(self.root, source)
        self.assertEqual(
            result["inserted"], {"transcripts": 1, "edited_transcripts": 1}
        )
        renamed = source.with_name("renamed.zip")
        source.rename(renamed)
        self.assertEqual(
            import_requested_results(self.root, renamed)["inserted"],
            {"transcripts": 0, "edited_transcripts": 0},
        )
        transcript = next(
            r
            for r, _ in iter_records(self.root, "transcripts")
            if r["id"] != before["id"]
        )
        edited = next(iter_records(self.root, "edited_transcripts"))[0]
        self.assertIsNone(transcript["model"])
        self.assertEqual(transcript["metadata"]["upstream"]["model_id"], 999)
        self.assertEqual(edited["transcript_ids"], [transcript["id"]])
        self.assertFalse(edited["quality"]["is_fully_human_reviewed"])
        self.assertTrue(edited["is_complete"])
        self.assertEqual(edited["review_document_markdown"], "完整参照稿及附注")
        self.assertEqual(
            edited["paragraphs"][0]["issues"][0]["evidence_labels"], ["t1:s0"]
        )
        self.assertEqual(
            read_json(self.root / "data/transcripts" / (before["id"] + ".json")), before
        )

    def test_bad_digest_rejects_before_writes(self):
        source = self.fixture()
        with zipfile.ZipFile(source) as archive:
            values = {n: archive.read(n) for n in archive.namelist()}
        values["BVfixture/review.md"] = b"changed"
        with zipfile.ZipFile(source, "w") as archive:
            for name, data in values.items():
                archive.writestr(name, data)
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            import_requested_results(self.root, source)
        self.assertEqual(len(list(iter_records(self.root, "transcripts"))), 1)
        self.assertEqual(list(iter_records(self.root, "edited_transcripts")), [])

    def test_wrong_identity_or_missing_input_is_rejected(self):
        for mutate, message in [
            (lambda v: v["metadata.json"]["parts"][0].update(cid=456), "BVID/page/CID"),
            (
                lambda v: v["proofread.json"]["blocks"][0].update(segment_ids=[]),
                "evidence",
            ),
            (lambda v: v["proofread.json"].update(base_transcript_id=9), "provenance"),
            (
                lambda v: v["asr.json"]["segments"][0].update(start_ms=2000),
                "timestamps",
            ),
        ]:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    package_records(self.root, self.fixture(mutate))

    def test_candidate_validation_failure_cannot_leave_half_package(self):
        source = self.fixture()
        with patch(
            "weimingzi_corpus.requested_results.validate_corpus",
            side_effect=ValueError("candidate rejected"),
        ):
            with self.assertRaisesRegex(ValueError, "candidate rejected"):
                import_requested_results(self.root, source)
        self.assertEqual(len(list(iter_records(self.root, "transcripts"))), 1)
        self.assertEqual(list(iter_records(self.root, "edited_transcripts")), [])


if __name__ == "__main__":
    unittest.main()
