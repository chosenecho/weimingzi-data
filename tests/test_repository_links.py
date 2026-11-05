import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "repository_checks", ROOT / "tools/check_repository.py"
)
repository_checks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(repository_checks)


class RepositoryLinkTests(unittest.TestCase):
    def test_nested_source_markdown_links_are_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "docs").mkdir()
            (root / "functions/probe").mkdir(parents=True)
            (root / "docs/context.md").write_text("context\n", encoding="utf-8")
            (root / "functions/probe/README.md").write_text(
                "[Context](../../docs/context.md)\n",
                encoding="utf-8",
            )

            self.assertEqual(repository_checks.check_links(root), 1)

    def test_broken_nested_source_markdown_link_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "workers/probe").mkdir(parents=True)
            (root / "workers/probe/README.md").write_text(
                "[Missing](../../missing.md)\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "workers.*broken local link"):
                repository_checks.check_links(root)

    def test_runtime_markdown_directories_are_skipped(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = root / "workers/probe/.venv-workers"
            runtime.mkdir(parents=True)
            (runtime / "README.md").write_text(
                "[Missing](../../../../missing.md)\n",
                encoding="utf-8",
            )

            self.assertEqual(repository_checks.check_links(root), 0)


if __name__ == "__main__":
    unittest.main()
