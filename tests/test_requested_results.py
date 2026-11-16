"""Package integrity, mapping and non-destructive admission."""

import copy
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import test_corpus as fixtures
from weimingzi_corpus.exports import render_subtitles
from weimingzi_corpus.cli import import_records, load_content_record
from weimingzi_corpus.records import (
    install_candidate_updates, iter_records, read_json, validate_corpus, write_json,
    write_jsonl, write_record_updates,
)
from weimingzi_corpus.schema_v3 import migrate_v2
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

    def test_import_ignores_broken_optional_projection_configuration(self):
        source = self.fixture()
        for name in ("training", "release", "topics"):
            path = self.root / "selections" / (name + ".json")
            path.parent.mkdir(exist_ok=True)
            path.write_text("{broken json", encoding="utf-8")
        self.assertEqual(
            import_requested_results(self.root, source)["inserted"],
            {"transcripts": 1, "edited_transcripts": 1},
        )
        for path in (self.root / "selections").iterdir():
            self.assertEqual(path.read_text(encoding="utf-8"), "{broken json")

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


class NativePackageTests(unittest.TestCase):
    tearDown = fixtures.CorpusTests.tearDown
    save_transcript = fixtures.CorpusTests.save_transcript

    def setUp(self):
        fixtures.CorpusTests.setUp(self)
        self.source = PackageTests.fixture(self)
        native = self.root / "native"
        migrate_v2(self.root, native)
        self.root = native

    def snapshot(self):
        return {
            p.relative_to(self.root).as_posix(): p.read_bytes()
            for p in (self.root / "data").rglob("*") if p.is_file()
        }

    def test_native_import_lossless_artifacts_inputs_quality_and_replay(self):
        before = self.snapshot()
        expected = package_records(self.root, self.source)
        self.assertEqual(import_requested_results(self.root, self.source)["inserted"],
                         {"transcripts": 1, "edited_transcripts": 1})
        for table, rows in expected.items():
            projected = {r["id"]: (r, p) for r, p in iter_records(self.root, table)}
            for row in rows:
                actual, path = projected[row["id"]]
                self.assertEqual(actual, row)
                self.assertEqual(load_content_record(self.root, row["id"]), row)
                self.assertEqual(path.parent.name, "documents")
        after = self.snapshot()
        for path, value in before.items():
            if path.startswith("data/documents/"):
                self.assertEqual(after[path], value)
        self.assertTrue(any(path.startswith("data/artifacts/") for path in after))
        self.assertFalse((self.root / "data/transcripts").exists())
        self.assertFalse((self.root / "data/edited_transcripts").exists())
        validate_corpus(self.root)
        self.assertEqual(import_requested_results(self.root, self.source)["inserted"],
                         {"transcripts": 0, "edited_transcripts": 0})
        self.assertEqual(self.snapshot(), after)

    def test_native_rejected_candidate_preserves_every_original_byte(self):
        before = self.snapshot()
        with patch("weimingzi_corpus.requested_results.validate_corpus",
                   side_effect=ValueError("candidate rejected")):
            with self.assertRaisesRegex(ValueError, "candidate rejected"):
                import_requested_results(self.root, self.source)
        self.assertEqual(self.snapshot(), before)

    def test_native_install_failure_restores_existing_and_new_files(self):
        import os
        replace = os.replace
        before = self.snapshot()
        installed = 0
        failed = False

        def fail_during_install(source, destination):
            nonlocal installed, failed
            destination = Path(destination)
            if destination.resolve().is_relative_to((self.root / "data").resolve()) and not failed:
                installed += 1
                if installed == 3:
                    failed = True
                    raise OSError("synthetic install failure")
            return replace(source, destination)

        with patch("weimingzi_corpus.records.os.replace", side_effect=fail_during_install):
            with self.assertRaisesRegex(OSError, "synthetic install failure"):
                import_requested_results(self.root, self.source)
        self.assertTrue(failed)
        self.assertEqual(self.snapshot(), before)
        validate_corpus(self.root)

    def review_update_candidate(self, markdown):
        import_requested_results(self.root, self.source)
        edited = next(iter_records(self.root, "edited_transcripts"))[0]
        if markdown is None:
            edited.pop("review_document_markdown")
        else:
            edited["review_document_markdown"] = markdown
        temporary = tempfile.TemporaryDirectory(dir=self.root.parent)
        self.addCleanup(temporary.cleanup)
        candidate = Path(temporary.name)
        shutil.copytree(self.root / "data", candidate / "data", copy_function=os.link)
        before = self.snapshot()
        paths = write_record_updates(candidate, {"edited_transcripts": [edited]})
        validate_corpus(candidate)
        self.assertEqual(self.snapshot(), before)
        deleted = [path for path in paths if not (candidate / path).exists()]
        self.assertTrue(deleted)
        for path in deleted:
            self.assertEqual(path.parent.as_posix(), "data/artifacts")
            self.assertTrue((self.root / path).is_file())
        return candidate, paths, edited, deleted

    def test_native_review_artifact_rewrite_installs_and_deletes_old_artifact(self):
        candidate, paths, edited, deleted = self.review_update_candidate("更新后的核对稿。\r\n")
        install_candidate_updates(self.root, candidate, paths)
        self.assertEqual(load_content_record(self.root, edited["id"]), edited)
        for path in deleted:
            self.assertFalse((self.root / path).exists())
        self.assertEqual(
            [path.read_bytes() for path in (self.root / "data/artifacts").iterdir()],
            [edited["review_document_markdown"].encode("utf-8")],
        )
        validate_corpus(self.root)

    def test_native_review_artifact_removal_installs(self):
        candidate, paths, edited, deleted = self.review_update_candidate(None)
        install_candidate_updates(self.root, candidate, paths)
        actual = load_content_record(self.root, edited["id"])
        self.assertEqual(actual, edited)
        self.assertNotIn("review_document_markdown", actual)
        for path in deleted:
            self.assertFalse((self.root / path).exists())
        validate_corpus(self.root)

    def test_native_failure_after_artifact_deletion_restores_complete_dataset(self):
        candidate, paths, edited, deleted = self.review_update_candidate("替换工件后模拟安装失败。")
        before = self.snapshot()
        replace = os.replace
        failed = False
        document = (self.root / "data/documents" / (edited["id"] + ".json")).resolve()

        def fail_after_delete(source, destination):
            nonlocal failed
            if Path(destination).resolve() == document and not failed:
                self.assertTrue(all(not (self.root / path).exists() for path in deleted))
                failed = True
                raise OSError("synthetic failure after artifact deletion")
            return replace(source, destination)

        with patch("weimingzi_corpus.records.os.replace", side_effect=fail_after_delete):
            with self.assertRaisesRegex(OSError, "failure after artifact deletion"):
                install_candidate_updates(self.root, candidate, paths)
        self.assertTrue(failed)
        self.assertEqual(self.snapshot(), before)
        validate_corpus(self.root)

    def test_cli_native_import_uses_core_writer_and_validates_candidate(self):
        item = copy.deepcopy(self.item)
        item["id"] = "i-" + "e" * 24
        source = self.root / "new-item.json"
        write_json(source, item)
        self.assertEqual(import_records(self.root, "items", source), 1)
        self.assertEqual(import_records(self.root, "items", source), 0)
        self.assertEqual(len(list(iter_records(self.root, "items"))), 2)
        self.assertFalse((self.root / "data/collections.jsonl").exists())
        before = self.snapshot()
        broken = copy.deepcopy(self.transcript)
        broken["id"] = "t-" + "d" * 24
        broken["item_id"] = "i-" + "f" * 24
        write_json(source, broken)
        with self.assertRaises(ValueError):
            import_records(self.root, "transcripts", source)
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
