import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "preservation_script_fixture", ROOT / "tools/preservation_manifest.py"
)
preservation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preservation)
POWERSHELL = shutil.which("powershell.exe") or shutil.which("pwsh")


@unittest.skipUnless(POWERSHELL, "PowerShell is not installed")
class PreservationCheckScriptTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="preservation script ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "archive checkout"
        self.caller = Path(self.temporary.name) / "separate caller"
        self.caller.mkdir()
        for directory in preservation.CANONICAL_ROOTS:
            (self.root / directory).mkdir(parents=True)
        for relative in preservation.SUPPORT_FILES:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("support\n", encoding="utf-8")
        for relative in ("tools/preservation_manifest.py", "tools/preservation_check.ps1"):
            shutil.copyfile(ROOT / relative, self.root / relative)
        (self.root / "data/items.jsonl").write_text("{}\n", encoding="utf-8")
        self.relative = "preservation/manifests/baseline-2026-01-01.json"
        preservation.write_manifest(self.root, self.relative)
        preservation.select_current_manifest(self.root, self.relative)
        self.log = self.root / "preservation/checks/fixity.jsonl"

    def run_check(self, python_path=None):
        return subprocess.run(
            [
                POWERSHELL, "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-File",
                str(self.root / "tools/preservation_check.ps1"),
                "-PythonPath", python_path or sys.executable,
            ],
            cwd=self.caller, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30,
        )

    def events(self):
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def test_success_uses_script_root_from_another_working_directory(self):
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(self.events()), 1)
        self.assertTrue(self.events()[0]["ok"])
        self.assertFalse((self.caller / "preservation").exists())
        self.assertTrue(preservation.verify_event_log(self.root, "preservation/checks/fixity.jsonl")["ok"])

    def test_changed_file_returns_failure_and_records_the_difference(self):
        (self.root / "data/items.jsonl").write_text("changed\n", encoding="utf-8")
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.events()[0]["ok"])
        self.assertEqual([item["path"] for item in self.events()[0]["changed"]], ["data/items.jsonl"])

    def test_missing_baseline_returns_failure_without_replacing_it(self):
        (self.root / self.relative).unlink()
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.events()[0]["ok"])
        self.assertTrue(self.events()[0]["errors"])
        self.assertFalse((self.root / self.relative).exists())

    def test_missing_pointer_returns_failure_and_preserves_the_baseline(self):
        before = (self.root / self.relative).read_bytes()
        (self.root / "preservation/current-baseline.json").unlink()
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.events()[0]["ok"])
        self.assertEqual((self.root / self.relative).read_bytes(), before)

    def test_corrupt_log_returns_failure_without_appending(self):
        self.log.parent.mkdir(parents=True, exist_ok=True)
        damaged = b"{incomplete"
        self.log.write_bytes(damaged)
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.log.read_bytes(), damaged)

    def test_missing_python_returns_failure_without_creating_a_log(self):
        result = self.run_check(str(self.root / "missing interpreter.exe"))
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
