"""Immutable ZIP locators restore to the hash-addressed layout; no network calls."""

import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from weimingzi_corpus.data import write_jsonl

SPEC = importlib.util.spec_from_file_location(
    "fetch_media", ROOT / "tools/fetch_media.py"
)
media = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(media)


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_root = media.ROOT
        media.ROOT = Path(self.temp.name)
        self.payload = b"verified audio bytes"
        self.row = {
            "path": "media/audio/sample.m4a",
            "archive_path": "视频/BVexample/音频/sample.m4a",
            "bytes": len(self.payload),
            "sha256": hashlib.sha256(self.payload).hexdigest(),
        }

    def tearDown(self):
        media.ROOT = self.original_root
        self.temp.cleanup()

    def bundle(self, entries):
        path = media.ROOT / "test.zip"
        with ZipFile(path, "w") as output:
            for name, body in entries:
                output.writestr(name, body)
        return path

    def test_archive_member_restores_to_hash_addressed_path(self):
        archive = self.bundle([(self.row["archive_path"], self.payload)])
        self.assertEqual(media.restore_archive(archive, [self.row]), 1)
        self.assertEqual(media.target_path(self.row["path"]).read_bytes(), self.payload)
        self.assertFalse((media.ROOT / self.row["archive_path"]).exists())

    def test_unexpected_member_is_rejected_before_output(self):
        archive = self.bundle(
            [(self.row["archive_path"], self.payload), ("unexpected", b"x")]
        )
        with self.assertRaisesRegex(ValueError, "Unexpected archive members"):
            media.restore_archive(archive, [self.row])
        self.assertFalse(media.target_path(self.row["path"]).exists())

    def test_wrong_size_is_rejected_before_output(self):
        archive = self.bundle([(self.row["archive_path"], b"short")])
        with self.assertRaisesRegex(ValueError, "member size"):
            media.restore_archive(archive, [self.row])
        self.assertFalse(media.target_path(self.row["path"]).exists())

    def test_hash_failure_preserves_existing_audio(self):
        target = media.target_path(self.row["path"])
        target.parent.mkdir(parents=True)
        target.write_bytes(b"original file")
        archive = self.bundle([(self.row["archive_path"], b"x" * len(self.payload))])
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            media.restore_archive(archive, [self.row])
        self.assertEqual(target.read_bytes(), b"original file")

    def test_valid_audio_is_reused(self):
        target = media.target_path(self.row["path"])
        target.parent.mkdir(parents=True)
        target.write_bytes(self.payload)
        stamp = target.stat().st_mtime_ns
        media.restore_archive(
            self.bundle([(self.row["archive_path"], self.payload)]), [self.row]
        )
        self.assertEqual(target.stat().st_mtime_ns, stamp)

    def test_traversal_and_absolute_paths_are_rejected(self):
        for name in ["", ".", "../outside", "/outside", "C:/outside", "data\\outside"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                media.target_path(name)

    def index_record(self):
        return {
            "id": "m-" + self.row["sha256"],
            "kind": "audio",
            "sha256": self.row["sha256"],
            "availability": "release",
            "bytes": self.row["bytes"],
            "path": self.row["path"],
            "downloads": [
                {
                    "release_tag": "fixture",
                    "asset": {
                        "name": "audio.zip",
                        "bytes": 1,
                        "sha256": "0" * 64,
                        "url": "https://example.org/audio.zip",
                    },
                    "member": self.row["archive_path"],
                }
            ],
        }

    def test_index_uses_original_zip_member_and_new_destination(self):
        write_jsonl(media.ROOT / "data/media.jsonl", [self.index_record()])
        group = media.load_media()["fixture/audio.zip"]
        self.assertEqual(group["files"], [self.row])

    def test_duplicate_restore_destinations_are_rejected(self):
        one = self.index_record()
        two = {**one, "id": "m-" + "1" * 64, "sha256": "1" * 64}
        write_jsonl(media.ROOT / "data/media.jsonl", [one, two])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            media.load_media()

    def test_unavailable_audio_does_not_trigger_download(self):
        write_jsonl(
            media.ROOT / "data/media.jsonl",
            [{"id": "m-" + "2" * 64, "availability": "unavailable"}],
        )
        self.assertEqual(media.load_media(), {})


if __name__ == "__main__":
    unittest.main()
