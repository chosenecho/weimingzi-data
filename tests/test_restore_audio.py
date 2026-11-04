"""Immutable ZIP locators restore to the hash-addressed layout; no network calls."""

import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from weimingzi_corpus.records import write_jsonl

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "restore_audio", ROOT / "tools/restore_audio.py"
)
audio = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audio)


class AudioRestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_root = audio.ROOT
        audio.ROOT = Path(self.temp.name)
        self.payload = b"verified audio bytes"
        self.row = {
            "local_path": "media/audio/sample.m4a",
            "member_path": "视频/BVexample/音频/sample.m4a",
            "size_bytes": len(self.payload),
            "sha256": hashlib.sha256(self.payload).hexdigest(),
        }

    def tearDown(self):
        audio.ROOT = self.original_root
        self.temp.cleanup()

    def bundle(self, entries):
        path = audio.ROOT / "test.zip"
        with ZipFile(path, "w") as output:
            for name, body in entries:
                output.writestr(name, body)
        return path

    def test_archive_member_restores_to_hash_addressed_path(self):
        archive = self.bundle([(self.row["member_path"], self.payload)])
        self.assertEqual(audio.restore_audio_archive(archive, [self.row]), 1)
        self.assertEqual(
            audio.resolve_audio_repository_path(self.row["local_path"]).read_bytes(),
            self.payload,
        )
        self.assertFalse((audio.ROOT / self.row["member_path"]).exists())

    def test_unexpected_member_is_rejected_before_output(self):
        archive = self.bundle(
            [(self.row["member_path"], self.payload), ("unexpected", b"x")]
        )
        with self.assertRaisesRegex(ValueError, "Unexpected archive members"):
            audio.restore_audio_archive(archive, [self.row])
        self.assertFalse(
            audio.resolve_audio_repository_path(self.row["local_path"]).exists()
        )

    def test_wrong_size_is_rejected_before_output(self):
        archive = self.bundle([(self.row["member_path"], b"short")])
        with self.assertRaisesRegex(ValueError, "member size"):
            audio.restore_audio_archive(archive, [self.row])
        self.assertFalse(
            audio.resolve_audio_repository_path(self.row["local_path"]).exists()
        )

    def test_hash_failure_preserves_existing_audio(self):
        target = audio.resolve_audio_repository_path(self.row["local_path"])
        target.parent.mkdir(parents=True)
        target.write_bytes(b"original file")
        archive = self.bundle([(self.row["member_path"], b"x" * len(self.payload))])
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            audio.restore_audio_archive(archive, [self.row])
        self.assertEqual(target.read_bytes(), b"original file")

    def test_valid_audio_is_reused(self):
        target = audio.resolve_audio_repository_path(self.row["local_path"])
        target.parent.mkdir(parents=True)
        target.write_bytes(self.payload)
        stamp = target.stat().st_mtime_ns
        audio.restore_audio_archive(
            self.bundle([(self.row["member_path"], self.payload)]), [self.row]
        )
        self.assertEqual(target.stat().st_mtime_ns, stamp)

    def test_traversal_and_absolute_paths_are_rejected(self):
        for name in ["", ".", "../outside", "/outside", "C:/outside", "data\\outside"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                audio.resolve_audio_repository_path(name)

    def index_record(self):
        return {
            "id": "m-" + self.row["sha256"],
            "kind": "audio",
            "sha256": self.row["sha256"],
            "availability": "available",
            "size_bytes": self.row["size_bytes"],
            "local_path": self.row["local_path"],
            "downloads": [
                {
                    "release_tag": "fixture",
                    "archive": {
                        "name": "audio.zip",
                        "size_bytes": 1,
                        "sha256": "0" * 64,
                        "url": "https://example.org/audio.zip",
                    },
                    "member_path": self.row["member_path"],
                }
            ],
        }

    def test_index_uses_original_zip_member_and_new_destination(self):
        write_jsonl(audio.ROOT / "data/audio.jsonl", [self.index_record()])
        group = audio.load_audio_archive_groups()["fixture/audio.zip"]
        self.assertEqual(group["files"], [self.row])

    def test_duplicate_restore_destinations_are_rejected(self):
        one = self.index_record()
        two = {**one, "id": "m-" + "1" * 64, "sha256": "1" * 64}
        write_jsonl(audio.ROOT / "data/audio.jsonl", [one, two])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            audio.load_audio_archive_groups()

    def test_unavailable_audio_does_not_trigger_download(self):
        write_jsonl(
            audio.ROOT / "data/audio.jsonl",
            [{"id": "m-" + "2" * 64, "availability": "unavailable"}],
        )
        self.assertEqual(audio.load_audio_archive_groups(), {})


if __name__ == "__main__":
    unittest.main()
