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
from weimingzi_corpus.records import ENTITIES, write_json, write_jsonl


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
            "archive": {"id": "z-" + "b" * 64, "kind": "archive",
                        "name": "fixture.zip", "url": "https://example.invalid/fixture.zip",
                        **audit.digest_file(self.archive)},
            "files": [self.row],
        }
        self.download = patch.object(audit.restore_audio, "download_archive", return_value=self.archive)
        self.download_mock = self.download.start()
        self.addCleanup(self.download.stop)
        self.record = {
            "id": "m-" + self.row["sha256"],
            "kind": "audio",
            "inputs": [],
            "availability": "available",
            "local_path": self.row["local_path"],
            "size_bytes": self.row["size_bytes"],
            "sha256": self.row["sha256"],
            "downloads": [{
                "release_tag": self.group["release_tag"],
                "archive_id": self.group["archive"]["id"],
                "member_path": self.row["member_path"],
            }],
        }
        write_json(self.root / "data/schema.json", {
            "schema_version": 3, "entities": list(ENTITIES),
            "range_unit": "unicode_codepoint", "range_end": "exclusive",
        })
        write_jsonl(self.root / "data/assets.jsonl", [self.record, self.group["archive"]])

    def test_archive_member_and_restored_bytes_are_recorded(self):
        result = audit.audit_group(self.key, self.group)
        self.assertTrue(result["ok"])
        entry = result["files"][0]
        self.assertEqual(entry["expected"], entry["observed_member"])
        self.assertEqual(entry["expected"], entry["observed_restored"])

    def test_archive_hash_failure_is_retained_before_restoration(self):
        target = self.root / self.row["local_path"]
        target.parent.mkdir(parents=True)
        target.write_bytes(b"existing audio bytes")
        self.group["archive"]["sha256"] = "0" * 64
        result = audit.audit_group(self.key, self.group)
        self.assertFalse(result["ok"])
        self.assertIn("mismatch", result["error"]["message"])
        self.assertEqual(target.read_bytes(), b"existing audio bytes")

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
            self.assertEqual(report["index"]["path"], "data/assets.jsonl")
            self.assertEqual(report["index_dependencies"], [{
                "path": "data/schema.json", "exists": True,
                **audit.digest_file(self.root / "data/schema.json"),
            }])
            self.assertTrue(report["index_unchanged"])
            self.assertTrue(report["index_dependencies_unchanged"])
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

    def test_native_audit_records_actual_assets_schema_and_original_archive_bytes(self):
        output = "preservation/checks/native-fixture.json"
        self.assertEqual(audit.main(["--output", output]), 0)
        report = json.loads((self.root / output).read_text(encoding="utf-8"))
        self.assertTrue(report["ok"])
        self.assertEqual(report["index"], {
            "path": "data/assets.jsonl", **audit.digest_file(self.root / "data/assets.jsonl")
        })
        self.assertEqual(report["index_dependencies"], [{
            "path": "data/schema.json", "exists": True,
            **audit.digest_file(self.root / "data/schema.json"),
        }])
        self.assertTrue(report["index_dependencies_unchanged"])
        tools_root = Path(audit.__file__).resolve().parent
        source_root = tools_root.parent / "src/weimingzi_corpus"
        self.assertEqual(report["tools"], {
            tool: audit.digest_file(directory / tool)
            for directory, names in (
                (tools_root, ("audit_audio_restore.py", "restore_audio.py")),
                (source_root, ("records.py", "schema_v3.py")),
            )
            for tool in names
        })
        self.assertEqual(report["scope"]["indexed_restorable_archives"], 1)
        archive = report["archives"][0]
        self.assertEqual(archive["archive_key"], self.key)
        self.assertEqual(archive["expected_archive"], self.group["archive"])
        self.assertEqual(archive["observed_archive"], audit.digest_file(self.archive))
        self.assertEqual(archive["files"][0]["member_path"], self.row["member_path"])
        self.assertEqual(archive["files"][0]["observed_restored"]["sha256"], self.row["sha256"])
        part = json.loads((self.root / "preservation/checks/native-fixture.parts/001.json").read_text(encoding="utf-8"))
        self.assertEqual(part["index"], report["index"])
        self.assertEqual(part["index_dependencies"], report["index_dependencies"])
        self.assertEqual(part["tools"], report["tools"])
        self.assertFalse(part["complete"])
        self.assertEqual(part["archive"], archive)

    def test_native_schema_change_during_restore_fails_dependency_integrity(self):
        operation = audit.audit_group

        def change_schema(key, group):
            result = operation(key, group)
            schema = self.root / "data/schema.json"
            schema.write_bytes(schema.read_bytes() + b" ")
            return result

        output = "preservation/checks/native-changed-schema.json"
        with patch.object(audit, "audit_group", side_effect=change_schema):
            self.assertEqual(audit.main(["--output", output]), 1)
        report = json.loads((self.root / output).read_text(encoding="utf-8"))
        self.assertTrue(report["index_unchanged"])
        self.assertFalse(report["index_dependencies_unchanged"])
        self.assertFalse(report["ok"])
        self.assertTrue(report["archives"][0]["ok"])

    def test_native_archive_asset_change_is_covered_by_index_integrity(self):
        operation = audit.audit_group

        def change_assets(key, group):
            result = operation(key, group)
            index = self.root / "data/assets.jsonl"
            index.write_bytes(index.read_bytes() + b"\n")
            return result

        output = "preservation/checks/native-changed-assets.json"
        with patch.object(audit, "audit_group", side_effect=change_assets):
            self.assertEqual(audit.main(["--output", output]), 1)
        report = json.loads((self.root / output).read_text(encoding="utf-8"))
        self.assertFalse(report["index_unchanged"])
        self.assertFalse(report["ok"])

    def test_existing_checkpoint_directory_is_not_overwritten(self):
        output = "preservation/checks/interrupted.json"
        checkpoint = self.root / "preservation/checks/interrupted.parts/001.json"
        checkpoint.parent.mkdir(parents=True)
        checkpoint.write_bytes(b"prior interrupted evidence")
        with self.assertRaises(SystemExit):
            audit.main(["--output", output])
        self.download_mock.assert_not_called()
        self.assertEqual(checkpoint.read_bytes(), b"prior interrupted evidence")
        self.assertFalse((self.root / output).exists())

    def test_unknown_archive_fails_before_download(self):
        with self.assertRaises(SystemExit):
            audit.main(["--archive", "unknown/no.zip", "--output", "preservation/checks/unknown.json"])
        self.download_mock.assert_not_called()

    def test_temporary_cli_restores_each_archive_in_a_separate_directory(self):
        second_payload = b"second archive fixture"
        second_archive = self.root / "second.zip"
        with ZipFile(second_archive, "w") as bundle:
            bundle.writestr("source/second.m4a", second_payload)
        second_asset = {
            "id": "z-" + "c" * 64, "kind": "archive", "name": "second.zip",
            "url": "https://example.invalid/second.zip", **audit.digest_file(second_archive),
        }
        second_audio = {
            "id": "m-" + hashlib.sha256(second_payload).hexdigest(), "kind": "audio", "inputs": [],
            "availability": "available", "local_path": "media/audio/second.m4a",
            "size_bytes": len(second_payload), "sha256": hashlib.sha256(second_payload).hexdigest(),
            "downloads": [{"release_tag": "fixture", "archive_id": second_asset["id"],
                           "member_path": "source/second.m4a"}],
        }
        write_jsonl(self.root / "data/assets.jsonl", [self.record, self.group["archive"], second_audio, second_asset])
        target = self.root / self.row["local_path"]
        target.parent.mkdir(parents=True)
        target.write_bytes(b"existing local bytes")
        roots = []
        operation = audit.audit_group

        def observe(key, group):
            roots.append(audit.restore_audio.ROOT)
            self.assertNotEqual(audit.restore_audio.ROOT, self.root)
            return operation(key, group)

        self.download_mock.side_effect = lambda archive, tag: {
            "fixture.zip": self.archive, "second.zip": second_archive,
        }[archive["name"]]
        output = "preservation/checks/temporary.json"
        with patch.object(audit, "audit_group", side_effect=observe):
            self.assertEqual(audit.main(["--temporary-media", "--workers", "1", "--output", output]), 0)
        report = json.loads((self.root / output).read_text(encoding="utf-8"))
        self.assertEqual(report["scope"]["media_storage"], "temporary_per_archive")
        self.assertEqual(report["scope"]["selected_audio"], 2)
        self.assertEqual(len(set(roots)), 2)
        self.assertTrue(all(not root.exists() for root in roots))
        self.assertEqual(audit.restore_audio.ROOT, self.root)
        self.assertEqual(target.read_bytes(), b"existing local bytes")
        self.assertFalse((self.root / second_audio["local_path"]).exists())

    def test_failed_download_is_preserved_in_report(self):
        self.download_mock.side_effect = OSError("fixture transport failure")
        with patch.object(audit.restore_audio, "load_audio_archive_groups", return_value={self.key: self.group}):
            output = "preservation/checks/failed.json"
            self.assertEqual(audit.main(["--output", output]), 1)
        report = json.loads((self.root / output).read_text(encoding="utf-8"))
        self.assertFalse(report["ok"])
        self.assertIn("completed_at", report)
        self.assertIn("transport failure", report["archives"][0]["error"]["message"])
        checkpoint = self.root / "preservation/checks/failed.parts/001.json"
        part = json.loads(checkpoint.read_text(encoding="utf-8"))
        self.assertEqual(part["archive"], report["archives"][0])
        self.assertEqual(part["index"], report["index"])
        self.assertEqual(part["index_dependencies"], report["index_dependencies"])
        self.assertEqual(part["tools"], report["tools"])
        self.assertFalse((self.root / self.row["local_path"]).exists())


if __name__ == "__main__":
    unittest.main()
