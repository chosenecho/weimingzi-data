import importlib.util
import io
import json
import multiprocessing
import tempfile
import traceback
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "preservation_manifest", ROOT / "tools/preservation_manifest.py"
)
preservation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preservation)


def _create_manifest_after_barrier(root, barrier, results):
    barrier.wait(timeout=15)
    try:
        manifest = preservation.write_manifest(
            Path(root), "preservation/manifests/baseline-2026-01-01.json"
        )
    except Exception as error:
        results.put(("error", type(error).__name__, str(error), traceback.format_exc()))
    else:
        results.put(("created", manifest["manifest_sha256"]))


def _select_manifest_after_barrier(root, relative, barrier, results):
    barrier.wait(timeout=15)
    try:
        pointer = preservation.select_current_manifest(Path(root), relative)
    except Exception as error:
        results.put(("error", type(error).__name__, str(error), traceback.format_exc()))
    else:
        results.put(("selected", pointer["manifest"], pointer["manifest_sha256"]))


class PreservationManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for directory in preservation.CANONICAL_ROOTS:
            (self.root / directory).mkdir(parents=True)
        for relative in preservation.SUPPORT_FILES:
            path = self.root / Path(*Path(relative).parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("support\n", encoding="utf-8")
        (self.root / "data/items.jsonl").write_bytes(b'{"id":"item"}\n')
        (self.root / "selections/topics.json").write_bytes(b'{"entries":[]}\n')

    def tearDown(self):
        self.temp.cleanup()

    def test_manifest_is_sorted_and_covers_canonical_and_context_files(self):
        manifest = preservation.make_manifest(self.root)
        paths = [entry["path"] for entry in manifest["files"]]
        self.assertEqual(paths, sorted(paths, key=lambda value: value.encode("utf-8")))
        self.assertIn("data/items.jsonl", paths)
        self.assertIn("selections/topics.json", paths)
        self.assertIn("docs/SCHEMA.md", paths)
        self.assertEqual(manifest["summary"]["canonical_file_count"], 2)
        self.assertEqual(
            manifest["summary"]["supporting_context_file_count"],
            len(preservation.SUPPORT_FILES),
        )
        self.assertEqual(manifest["errors"], [])

    def test_create_and_verify_succeed_for_unchanged_files(self):
        relative = "preservation/manifests/test.json"
        created = preservation.write_manifest(self.root, relative)
        result = preservation.verify_manifest(self.root, relative)
        self.assertTrue(result["ok"])
        self.assertEqual(result["manifest_sha256"], created["manifest_sha256"])

    def test_verify_reports_changed_added_and_missing_files(self):
        relative = "preservation/manifests/test.json"
        preservation.write_manifest(self.root, relative)
        (self.root / "data/items.jsonl").write_bytes(b"changed\n")
        (self.root / "data/new.json").write_text("new", encoding="utf-8")
        (self.root / "selections/topics.json").unlink()

        result = preservation.verify_manifest(self.root, relative)
        self.assertFalse(result["ok"])
        self.assertEqual(result["added"], ["data/new.json"])
        self.assertEqual(result["missing"], ["selections/topics.json"])
        self.assertEqual(
            [item["path"] for item in result["changed"]], ["data/items.jsonl"]
        )

    def test_read_only_current_check_does_not_change_existing_log(self):
        relative = "preservation/manifests/baseline-2026-01-01.json"
        preservation.write_manifest(self.root, relative)
        preservation.select_current_manifest(self.root, relative)
        preservation.check_current_baseline(self.root)
        log = self.root / "preservation/checks/fixity.jsonl"
        before = log.read_bytes()
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = preservation.main(
                ["check-current", "--root", str(self.root), "--read-only"]
            )
        self.assertEqual(exit_code, 0)
        self.assertTrue(json.loads(output.getvalue())["ok"])
        self.assertNotIn("event_sha256", json.loads(output.getvalue()))
        self.assertEqual(log.read_bytes(), before)

    def test_read_only_failure_does_not_create_a_log(self):
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = preservation.main(
                ["check-current", "--root", str(self.root), "--read-only"]
            )
        self.assertEqual(exit_code, 1)
        self.assertFalse(json.loads(output.getvalue())["ok"])
        self.assertFalse((self.root / "preservation/checks/fixity.jsonl").exists())

    def test_manifest_tampering_is_rejected(self):
        relative = "preservation/manifests/test.json"
        preservation.write_manifest(self.root, relative)
        path = self.root / relative
        value = json.loads(path.read_text(encoding="utf-8"))
        value["files"][0]["sha256"] = "0" * 64
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "manifest SHA-256 mismatch"):
            preservation.verify_manifest(self.root, relative)

    def test_create_rejects_output_outside_manifest_directory(self):
        with self.assertRaisesRegex(ValueError, "under preservation/manifests"):
            preservation.write_manifest(self.root, "docs/fixity.json")

    def test_create_does_not_overwrite_a_prior_baseline(self):
        relative = "preservation/manifests/test.json"
        preservation.write_manifest(self.root, relative)
        with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
            preservation.write_manifest(self.root, relative)

    def test_concurrent_creates_cannot_overwrite_the_same_baseline(self):
        context = multiprocessing.get_context("spawn")
        barrier = context.Barrier(2)
        results = context.Queue()
        processes = [
            context.Process(
                target=_create_manifest_after_barrier,
                args=(str(self.root), barrier, results),
            )
            for _ in range(2)
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=30)
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join()
        self.assertEqual([process.exitcode for process in processes], [0, 0])

        outcomes = [results.get(timeout=5) for _ in processes]
        self.assertEqual(sum(outcome[0] == "created" for outcome in outcomes), 1)
        self.assertEqual(sum(outcome[0] == "error" for outcome in outcomes), 1)
        self.assertTrue(
            any(
                outcome[0] == "error"
                and outcome[1] == "ValueError"
                and "refusing to overwrite" in outcome[2]
                for outcome in outcomes
            ),
            outcomes,
        )
        result = preservation.verify_manifest(
            self.root, "preservation/manifests/baseline-2026-01-01.json"
        )
        self.assertTrue(result["ok"])

    def test_concurrent_current_selections_leave_one_valid_pointer(self):
        relative_manifests = [
            "preservation/manifests/baseline-2026-01-01.json",
            "preservation/manifests/baseline-2026-01-02.json",
        ]
        for relative in relative_manifests:
            preservation.write_manifest(self.root, relative)

        context = multiprocessing.get_context("spawn")
        barrier = context.Barrier(2)
        results = context.Queue()
        processes = [
            context.Process(
                target=_select_manifest_after_barrier,
                args=(str(self.root), relative, barrier, results),
            )
            for relative in relative_manifests
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=30)
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join()
        self.assertEqual([process.exitcode for process in processes], [0, 0])
        outcomes = [results.get(timeout=5) for _ in processes]
        self.assertTrue(
            all(outcome[0] == "selected" for outcome in outcomes), outcomes
        )

        selected, digest = preservation.current_manifest(self.root)
        self.assertIn(selected, relative_manifests)
        manifest = json.loads((self.root / selected).read_text(encoding="utf-8"))
        self.assertEqual(digest, manifest["manifest_sha256"])
        self.assertFalse(
            list((self.root / "preservation").glob(".current-baseline.json.*.part"))
        )

    def test_create_rejects_output_inside_canonical_data(self):
        with self.assertRaisesRegex(ValueError, "under preservation/manifests"):
            preservation.write_manifest(self.root, "data/fixity.json")

    def test_missing_support_file_is_reported(self):
        (self.root / "docs/SCHEMA.md").unlink()
        manifest = preservation.make_manifest(self.root)
        self.assertEqual(
            manifest["errors"],
            [{"path": "docs/SCHEMA.md", "error": "missing_support_file"}],
        )

    def test_duplicate_support_paths_are_reported(self):
        with patch.object(
            preservation,
            "SUPPORT_FILES",
            (*preservation.SUPPORT_FILES, preservation.SUPPORT_FILES[0]),
        ):
            manifest = preservation.make_manifest(self.root)
        self.assertEqual(
            manifest["errors"],
            [{"path": preservation.SUPPORT_FILES[0], "error": "duplicate_support_file"}],
        )

    def test_create_refuses_to_write_an_incomplete_manifest(self):
        (self.root / "docs/SCHEMA.md").unlink()
        relative = "preservation/manifests/incomplete.json"
        with self.assertRaisesRegex(ValueError, "cannot create an incomplete manifest"):
            preservation.write_manifest(self.root, relative)
        self.assertFalse((self.root / relative).exists())

    def test_current_selection_rejects_a_manifest_with_scope_errors(self):
        relative = "preservation/manifests/baseline-2026-01-01.json"
        manifest = preservation.make_manifest(self.root)
        manifest["errors"] = [{"path": "missing", "error": "missing_support_file"}]
        manifest["summary"]["error_count"] = 1
        manifest["manifest_sha256"] = preservation.manifest_digest(manifest)
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "manifest with scope errors"):
            preservation.select_current_manifest(self.root, relative)

    def test_verify_rejects_a_manifest_with_scope_errors(self):
        relative = "preservation/manifests/incomplete.json"
        manifest = preservation.make_manifest(self.root)
        manifest["errors"] = [{"path": "missing", "error": "missing_support_file"}]
        manifest["summary"]["error_count"] = 1
        manifest["manifest_sha256"] = preservation.manifest_digest(manifest)
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "manifest contains scope errors"):
            preservation.verify_manifest(self.root, relative)

    def test_fixity_events_are_chained_and_append_failure_results(self):
        relative = "preservation/manifests/test.json"
        preservation.write_manifest(self.root, relative)
        result = preservation.verify_manifest(self.root, relative)
        log = "preservation/checks/fixity.jsonl"

        first = preservation.append_fixity_event(self.root, log, result)
        (self.root / "data/items.jsonl").write_bytes(b"changed\n")
        failed_result = preservation.verify_manifest(self.root, relative)
        second = preservation.append_fixity_event(self.root, log, failed_result)

        self.assertTrue(first["ok"])
        self.assertFalse(second["ok"])
        self.assertEqual(second["previous_event_sha256"], first["event_sha256"])
        self.assertEqual(
            preservation.read_last_event(self.root / log), second["event_sha256"]
        )

    def test_fixity_event_log_rejects_tampering(self):
        relative = "preservation/manifests/test.json"
        preservation.write_manifest(self.root, relative)
        result = preservation.verify_manifest(self.root, relative)
        log = self.root / "preservation/checks/fixity.jsonl"
        preservation.append_fixity_event(
            self.root, log.relative_to(self.root).as_posix(), result
        )

        lines = log.read_text(encoding="utf-8").splitlines()
        event = json.loads(lines[0])
        event["ok"] = False
        log.write_text(json.dumps(event) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "event SHA-256 mismatch"):
            preservation.read_last_event(log)

    def test_fixity_event_log_path_is_restricted(self):
        result = preservation.verification_failure("baseline.json", ValueError("bad"))
        with self.assertRaisesRegex(ValueError, "under preservation/checks"):
            preservation.append_fixity_event(self.root, "docs/checks.jsonl", result)

    def test_fixity_event_log_can_be_checked_without_appending(self):
        relative = "preservation/manifests/test.json"
        preservation.write_manifest(self.root, relative)
        result = preservation.verify_manifest(self.root, relative)
        log = "preservation/checks/fixity.jsonl"
        event = preservation.append_fixity_event(self.root, log, result)
        checked = preservation.verify_event_log(self.root, log)

        self.assertTrue(checked["ok"])
        self.assertEqual(checked["event_count"], 1)
        self.assertEqual(checked["last_event_sha256"], event["event_sha256"])

    def test_fixity_event_log_detects_incomplete_final_line(self):
        log = self.root / "preservation/checks/fixity.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_bytes(b'{"partial":true}')
        with self.assertRaisesRegex(ValueError, "incomplete final line"):
            preservation.verify_event_log(
                self.root, "preservation/checks/fixity.jsonl"
            )

    def test_verification_failure_can_be_recorded(self):
        result = preservation.verification_failure(
            "preservation/manifests/missing.json", FileNotFoundError("missing")
        )
        event = preservation.append_fixity_event(
            self.root, "preservation/checks/fixity.jsonl", result
        )
        self.assertFalse(event["ok"])
        self.assertIsNone(event["manifest_sha256"])
        self.assertEqual(event["errors"][0]["error"], "missing")

    def test_cli_records_missing_manifest_failure(self):
        output = io.StringIO()
        with redirect_stdout(output):
            status = preservation.main(
                [
                    "verify",
                    "--root",
                    str(self.root),
                    "--manifest",
                    "preservation/manifests/missing.json",
                    "--record",
                ]
            )

        self.assertEqual(status, 1)
        result = json.loads(output.getvalue())
        self.assertFalse(result["ok"])
        self.assertEqual(result["event_log"], "preservation/checks/fixity.jsonl")
        event = json.loads(
            (self.root / result["event_log"]).read_text(encoding="utf-8")
        )
        self.assertIsNone(event["manifest_sha256"])

    def test_current_baseline_is_selected_and_checked(self):
        relative = "preservation/manifests/baseline-2026-01-01.json"
        manifest = preservation.write_manifest(self.root, relative)
        pointer = preservation.select_current_manifest(self.root, relative)
        self.assertEqual(pointer["manifest"], relative)
        self.assertEqual(pointer["manifest_sha256"], manifest["manifest_sha256"])

        result = preservation.check_current_baseline(self.root)
        self.assertTrue(result["ok"])
        self.assertEqual(result["manifest"], relative)
        self.assertEqual(result["manifest_sha256"], manifest["manifest_sha256"])
        self.assertTrue(
            preservation.verify_event_log(
                self.root, "preservation/checks/fixity.jsonl"
            )["ok"]
        )

    def test_current_baseline_rejects_paths_outside_manifest_directory(self):
        with self.assertRaisesRegex(ValueError, "under preservation/manifests"):
            preservation.select_current_manifest(self.root, "data/items.jsonl")

    def test_current_baseline_pointer_tampering_is_recorded(self):
        relative = "preservation/manifests/baseline-2026-01-01.json"
        preservation.write_manifest(self.root, relative)
        preservation.select_current_manifest(self.root, relative)
        pointer_path = self.root / "preservation/current-baseline.json"
        pointer_path.write_text(
            '{"schema_version":1,"manifest":"preservation/manifests/other.json"}\n',
            encoding="utf-8",
        )

        result = preservation.check_current_baseline(self.root)
        self.assertFalse(result["ok"])
        self.assertIn("current-baseline pointer", result["errors"][0]["error"])
        self.assertTrue(
            preservation.verify_event_log(
                self.root, "preservation/checks/fixity.jsonl"
            )["ok"]
        )


if __name__ == "__main__":
    unittest.main()
