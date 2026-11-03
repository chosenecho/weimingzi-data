"""Audio restore tests use temporary files and never access the network."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

SPEC = importlib.util.spec_from_file_location("fetch_media", Path(__file__).resolve().parents[1] / "tools/fetch_media.py")
media = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(media)

class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_root = media.ROOT
        media.ROOT = Path(self.temp.name)
        self.payload = b"verified audio bytes"
        self.row = {
            "path": "data/transcripts/哲学与经典/BVexample/audio/sample.m4a",
            "archive_path": "视频/BVexample/音频/sample.m4a",
            "archive": "audio.zip",
            "bytes": len(self.payload),
            "sha256": hashlib.sha256(self.payload).hexdigest(),
        }

    def tearDown(self):
        media.ROOT = self.original_root
        self.temp.cleanup()

    def bundle(self, entries):
        archive = media.ROOT / "test.zip"
        with ZipFile(archive, "w") as output:
            for name, body in entries:
                output.writestr(name, body)
        return archive

    def test_archive_member_restores_to_content_folder(self):
        archive = self.bundle([(self.row["archive_path"], self.payload)])
        self.assertEqual(media.restore_archive(archive, [self.row]), 1)
        self.assertEqual(media.target_path(self.row["path"]).read_bytes(), self.payload)
        self.assertFalse((media.ROOT / self.row["archive_path"]).exists())

    def test_supplement_restores_inside_content_item(self):
        row = {**self.row, "path": "data/transcripts/哲学与经典/BVexample/补充版本/abcDEF12_-3/audio.opus",
               "archive_path": "视频/BVexample/YouTube/abcDEF12_-3/audio.opus"}
        archive = self.bundle([(row["archive_path"], self.payload)])
        self.assertEqual(media.restore_archive(archive, [row]), 1)
        self.assertEqual(media.target_path(row["path"]).read_bytes(), self.payload)
        self.assertFalse((media.ROOT / row["archive_path"]).exists())

    def test_unexpected_member_is_rejected_before_any_output(self):
        archive = self.bundle([(self.row["archive_path"], self.payload), ("unexpected.bin", b"x")])
        with self.assertRaisesRegex(ValueError, "Unexpected archive members"):
            media.restore_archive(archive, [self.row])
        self.assertFalse(media.target_path(self.row["path"]).exists())

    def test_incorrect_size_is_rejected_before_any_output(self):
        archive = self.bundle([(self.row["archive_path"], b"short")])
        with self.assertRaisesRegex(ValueError, "member size"):
            media.restore_archive(archive, [self.row])
        self.assertFalse(media.target_path(self.row["path"]).exists())

    def test_hash_failure_does_not_overwrite_existing_file(self):
        target = media.target_path(self.row["path"])
        target.parent.mkdir(parents=True)
        target.write_bytes(b"original local file")
        archive = self.bundle([(self.row["archive_path"], b"x" * len(self.payload))])
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            media.restore_archive(archive, [self.row])
        self.assertEqual(target.read_bytes(), b"original local file")

    def test_verified_audio_is_reused(self):
        target = media.target_path(self.row["path"])
        target.parent.mkdir(parents=True)
        target.write_bytes(self.payload)
        stamp = target.stat().st_mtime_ns
        archive = self.bundle([(self.row["archive_path"], self.payload)])
        media.restore_archive(archive, [self.row])
        self.assertEqual(target.stat().st_mtime_ns, stamp)

    def test_absolute_and_traversal_paths_are_rejected(self):
        for path in ["", ".", "../outside", "/outside", "C:/outside", "data\\outside"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                media.target_path(path)

    def test_duplicate_restore_destinations_are_rejected(self):
        manifest = {
            "schema": "weimingzi-media-v2",
            "release_tag": "snapshot",
            "assets": [{"name": "audio.zip", "bytes": 1, "sha256": "0" * 64}],
            "files": [self.row, {**self.row, "archive_path": "other.m4a"}],
        }
        path = media.ROOT / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            media.load_manifest("manifest.json")

if __name__ == "__main__":
    unittest.main()
