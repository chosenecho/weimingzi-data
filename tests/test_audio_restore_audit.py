"""Restore audit reports cover real bytes and retain failures without network."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_audio_restore as audit


class AudioRestoreAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root_patch = patch.object(audit.restore_audio, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.payload = b"audio audit fixture"
        self.row = {
            "local_path": "media/audio/sample.m4a",
            "member_path": "original/audio.m4a",
            "size_bytes": len(self.payload),
            "sha256": hashlib.sha256(self.payload).hexdigest(),
        }
        self.archive = self.root / "fixture.zip"
        with ZipFile(self.archive, "w") as bundle:
            bundle.writestr(self.row["member_path"], self.payload)
        self.key = "fixture/fixture.zip"
        self.group = {
            "release_tag": "fixture",
            "archive": {"name": "fixture.zip", "url": "https://example.invalid/fixture.zip",
                        **audit.digest_file(self.archive)},
            "files": [self.row],
        }
        self.download = patch.object(audit.restore_audio, "download_archive", return_value=self.archive)
        self.download_mock = self.download.start()
        self.addCleanup(self.download.stop)
        (self.root / "data").mkdir()
        (self.root / "data/audio.jsonl").write_text("fixture index", encoding="utf-8")

    def test_archive_member_and_restored_bytes_are_recorded(self):
        result = audit.audit_group(self.key, self.group)
        self.assertTrue(result["ok"])
        entry = result["files"][0]
        self.assertEqual(entry["expected"], entry["observed_member"])
        self.assertEqual(entry["expected"], entry["observed_restored"])

    def test_archive_hash_failure_is_retained_before_restoration(self):
        self.group["archive"]["sha256"] = "0" * 64
        result = audit.audit_group(self.key, self.group)
        self.assertFalse(result["ok"])
        self.assertIn("mismatch", result["error"]["message"])
        self.assertFalse((self.root / self.row["local_path"]).exists())

    def test_restored_corruption_is_not_hidden_by_valid_member(self):
        target = self.root / self.row["local_path"]
        target.parent.mkdir(parents=True)
        target.write_bytes(b"corrupted result")
        with patch.object(audit.restore_audio, "restore_audio_archive"):
            result = audit.audit_group(self.key, self.group)
        self.assertFalse(result["ok"])
        self.assertEqual(result["files"][0]["observed_member"], result["files"][0]["expected"])
        self.assertFalse(result["files"][0]["ok"])

    def test_cli_scope_is_explicit_and_existing_report_is_not_overwritten(self):
        output = "preservation/checks/audit-fixture.json"
        with patch.object(audit.restore_audio, "load_audio_archive_groups", return_value={self.key: self.group}):
            self.assertEqual(audit.main(["--archive", self.key, "--output", output]), 0)
            original = (self.root / output).read_bytes()
            report = json.loads(original)
            self.assertEqual(report["scope"]["selected_audio"], 1)
            self.assertTrue(report["index_unchanged"])
            with self.assertRaises(SystemExit) as stopped:
                audit.main(["--output", output])
            self.assertEqual(stopped.exception.code, 2)
            self.assertEqual((self.root / output).read_bytes(), original)

    def test_cli_rejects_canonical_output_before_download(self):
        with self.assertRaises(SystemExit):
            audit.main(["--output", "data/audit.json"])
        self.download_mock.assert_not_called()

    def test_temporary_mode_does_not_replace_existing_local_audio(self):
        target = self.root / self.row["local_path"]
        target.parent.mkdir(parents=True)
        target.write_bytes(b"existing local bytes")
        result = audit.audit_temporary_group(self.key, self.group)
        self.assertTrue(result["ok"])
        self.assertEqual(target.read_bytes(), b"existing local bytes")
        self.assertEqual(audit.restore_audio.ROOT, self.root)

    def test_temporary_mode_rejects_shared_root_concurrency(self):
        with self.assertRaises(SystemExit):
            audit.main(["--temporary-media", "--workers", "2",
                        "--output", "preservation/checks/no-race.json"])
        self.download_mock.assert_not_called()

    def test_failed_download_is_preserved_in_report(self):
        self.download_mock.side_effect = OSError("fixture transport failure")
        with patch.object(audit.restore_audio, "load_audio_archive_groups", return_value={self.key: self.group}):
            output = "preservation/checks/failed.json"
            self.assertEqual(audit.main(["--output", output]), 1)
        report = json.loads((self.root / output).read_text(encoding="utf-8"))
        self.assertFalse(report["ok"])
        self.assertIn("transport failure", report["archives"][0]["error"]["message"])


if __name__ == "__main__":
    unittest.main()
