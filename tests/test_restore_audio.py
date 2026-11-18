"""Native audio/archive locators restore exact ZIP bytes without network calls."""
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from weimingzi_corpus.records import ENTITIES, write_json, write_jsonl

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("restore_audio", ROOT / "tools/restore_audio.py")
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

    def write_index(self, extra=()):
        archive = self.bundle([(self.row["member_path"], self.payload)])
        archive_row = {
            "id": "z-" + "b" * 64,
            "kind": "archive",
            "name": "audio.zip",
            "size_bytes": archive.stat().st_size,
            "sha256": audio.file_sha256(archive),
            "url": "https://example.org/audio.zip",
        }
        record = {
            "id": "m-" + self.row["sha256"],
            "kind": "audio",
            "inputs": [],
            "sha256": self.row["sha256"],
            "availability": "available",
            "size_bytes": self.row["size_bytes"],
            "local_path": self.row["local_path"],
            "downloads": [{"release_tag": "fixture", "archive_id": archive_row["id"], "member_path": self.row["member_path"]}],
        }
        write_json(audio.ROOT / "data/schema.json", {"schema_version": 3, "entities": list(ENTITIES), "range_unit": "unicode_codepoint", "range_end": "exclusive"})
        write_jsonl(audio.ROOT / "data/assets.jsonl", [record, archive_row, *extra])
        return archive, record, archive_row

    def test_archive_member_restores_to_hash_addressed_path(self):
        archive = self.bundle([(self.row["member_path"], self.payload)])
        self.assertEqual(audio.restore_audio_archive(archive, [self.row]), 1)
        self.assertEqual(audio.resolve_audio_repository_path(self.row["local_path"]).read_bytes(), self.payload)
        self.assertFalse((audio.ROOT / self.row["member_path"]).exists())

    def test_unexpected_member_is_rejected_before_output(self):
        archive = self.bundle([(self.row["member_path"], self.payload), ("unexpected", b"x")])
        with self.assertRaisesRegex(ValueError, "Unexpected archive members"):
            audio.restore_audio_archive(archive, [self.row])
        self.assertFalse(audio.resolve_audio_repository_path(self.row["local_path"]).exists())

    def test_wrong_size_is_rejected_before_output(self):
        with self.assertRaisesRegex(ValueError, "member size"):
            audio.restore_audio_archive(self.bundle([(self.row["member_path"], b"short")]), [self.row])
        self.assertFalse(audio.resolve_audio_repository_path(self.row["local_path"]).exists())

    def test_hash_failure_preserves_existing_audio(self):
        target = audio.resolve_audio_repository_path(self.row["local_path"])
        target.parent.mkdir(parents=True)
        target.write_bytes(b"original file")
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            audio.restore_audio_archive(self.bundle([(self.row["member_path"], b"x" * len(self.payload))]), [self.row])
        self.assertEqual(target.read_bytes(), b"original file")

    def test_valid_audio_is_reused(self):
        target = audio.resolve_audio_repository_path(self.row["local_path"])
        target.parent.mkdir(parents=True)
        target.write_bytes(self.payload)
        stamp = target.stat().st_mtime_ns
        audio.restore_audio_archive(self.bundle([(self.row["member_path"], self.payload)]), [self.row])
        self.assertEqual(target.stat().st_mtime_ns, stamp)

    def test_traversal_and_absolute_paths_are_rejected(self):
        for name in ["", ".", "../outside", "/outside", "C:/outside", "data\\outside"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                audio.resolve_audio_repository_path(name)

    def test_native_asset_id_resolves_original_zip_and_destination(self):
        archive, _, asset = self.write_index()
        group = audio.load_audio_archive_groups()["fixture/audio.zip"]
        self.assertEqual(group["files"], [self.row])
        self.assertEqual(group["archive"], asset)
        self.assertEqual(group["archive"]["sha256"], audio.file_sha256(archive))
        self.assertEqual(audio.audio_index_context()["path"], (audio.ROOT / "data/assets.jsonl").resolve())

    def test_native_assets_restore_and_verify_without_projection(self):
        archive, _, _ = self.write_index()
        with patch.object(audio, "download_archive", return_value=archive) as download:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(audio.main([]), 0)
                self.assertEqual(audio.main(["--verify-only"]), 0)
            download.assert_called_once()
        self.assertEqual((audio.ROOT / self.row["local_path"]).read_bytes(), self.payload)

    def test_native_list_needs_only_schema_and_assets(self):
        self.write_index()
        for name in ("items.jsonl", "annotations.jsonl"):
            (audio.ROOT / "data" / name).write_text("unrelated invalid JSON", encoding="utf-8")
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(audio.main(["--list"]), 0)
        self.assertEqual(json.loads(output.getvalue())["audio_files"], 1)

    def test_missing_archive_reference_is_rejected(self):
        _, record, _ = self.write_index()
        write_jsonl(audio.ROOT / "data/assets.jsonl", [record])
        with self.assertRaisesRegex(ValueError, "native archive"):
            audio.load_audio_archive_groups()

    def test_duplicate_destinations_are_rejected(self):
        _, one, archive = self.write_index()
        two = {**one, "id": "m-" + "1" * 64, "sha256": "1" * 64}
        write_jsonl(audio.ROOT / "data/assets.jsonl", [one, two, archive])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            audio.load_audio_archive_groups()

    def test_duplicate_asset_ids_are_rejected(self):
        _, one, archive = self.write_index()
        write_jsonl(audio.ROOT / "data/assets.jsonl", [one, archive, archive])
        with self.assertRaisesRegex(ValueError, "Duplicate asset ID"):
            audio.load_audio_archive_groups()

    def test_wrong_schema_fails_before_restore(self):
        self.write_index()
        write_json(audio.ROOT / "data/schema.json", {"schema_version": 99})
        with self.assertRaisesRegex(ValueError, "current native schema"):
            audio.load_audio_archive_groups()

    def test_unavailable_audio_does_not_trigger_download(self):
        self.write_index()
        write_jsonl(audio.ROOT / "data/assets.jsonl", [{"id": "m-" + "2" * 64, "kind": "audio", "availability": "unavailable"}])
        self.assertEqual(audio.load_audio_archive_groups(), {})


if __name__ == "__main__":
    unittest.main()
