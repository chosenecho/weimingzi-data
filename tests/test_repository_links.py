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

    def test_preserved_markdown_is_not_interpreted_as_repository_navigation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifacts = root / "data/artifacts"
            artifacts.mkdir(parents=True)
            content = "[Original source relative link](../../unavailable-original.md)\n"
            (artifacts / "original.md").write_text(content, encoding="utf-8")
            self.assertEqual(repository_checks.check_links(root), 0)
            self.assertEqual((artifacts / "original.md").read_text(encoding="utf-8"), content)

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

    def test_heading_fragments_support_chinese_unicode_and_percent_encoding(self):
        self.assertEqual(self.check_fixture({
            "README.md": "[Guide](docs/guide.md#%E6%AD%A3%E6%96%87%E4%B8%8E%E6%A0%87%E6%B3%A8)\n",
            "docs/guide.md": "## 正文与标注\n",
        }), 1)

    def test_same_document_fragment_is_checked(self):
        self.assertEqual(self.check_fixture({
            "README.md": "# 开始\n[Current](#开始)\n",
        }), 1)
        with self.assertRaisesRegex(ValueError, "broken local anchor.*#missing"):
            self.check_fixture({"README.md": "# 开始\n[Missing](#missing)\n"})

    def test_existing_file_with_missing_heading_fails(self):
        with self.assertRaisesRegex(ValueError, "README.*broken local anchor"):
            self.check_fixture({
                "README.md": "[Wrong](guide.md#old-heading)\n",
                "guide.md": "## Current heading\n",
            })

    def test_reference_destinations_and_optional_titles_are_checked(self):
        self.assertEqual(self.check_fixture({
            "README.md": '[Guide][g]\n[g]: guide.md#current-heading "Guide"\n',
            "guide.md": "## Current heading\n",
        }), 1)
        with self.assertRaisesRegex(ValueError, "broken local anchor"):
            self.check_fixture({
                "README.md": "[Guide][g]\n[g]: guide.md#missing\n",
                "guide.md": "## Present\n",
            })

    def test_angle_destinations_spaces_and_parentheses(self):
        self.assertEqual(self.check_fixture({
            "README.md": '[Guide](<guide (v3).md#api> "Title")\n[Other](guide%20(v3).md#api)\n',
            "guide (v3).md": "## API\n",
        }), 2)

    def test_fenced_code_inline_code_and_comments_are_not_navigation(self):
        self.assertEqual(self.check_fixture({
            "README.md": (
                "```md\n[Wrong](missing.md)\n## Fake\n```\n"
                "~~~md\n[Wrong](missing.md)\n~~~\n"
                "`[Wrong](missing.md)`\n<!-- [Wrong](missing.md) -->\n"
                "# Real\n[Here](#real)\n"
            ),
        }), 1)
        with self.assertRaisesRegex(ValueError, "broken local anchor"):
            self.check_fixture({
                "README.md": "```md\n## Fake\n```\n[Wrong](#fake)\n",
            })

    def test_heading_slug_removes_formatting_and_disambiguates_duplicates(self):
        anchors = repository_checks.markdown_anchors(
            "# Same\n# Same\n# Same-1\n# Same\n"
            "## **API** `field_name` &amp; [Link](somewhere)\n"
            "Setext heading\n==============\n"
        )
        self.assertEqual(anchors, {
            "same", "same-1", "same-1-1", "same-2",
            "api-field_name--link", "setext-heading",
        })

    def test_code_span_heading_keeps_literal_underscores_and_angle_text(self):
        self.assertEqual(
            repository_checks.markdown_anchors("## `input_units.base_source` `<id>`\n"),
            {"input_unitsbase_source-id"},
        )

    def test_literal_underscore_in_identifier_is_preserved(self):
        self.assertEqual(
            repository_checks.markdown_anchors("## some_field_name\n"),
            {"some_field_name"},
        )

    def test_explicit_html_ids_and_named_anchors(self):
        self.assertEqual(self.check_fixture({
            "README.md": '<a name="custom"></a>\n<div id="other"></div>\n[One](#custom)\n<a href="#other">Two</a>\n',
        }), 2)

    def test_external_and_protocol_relative_links_are_not_local(self):
        self.assertEqual(self.check_fixture({
            "README.md": "[Web](https://example.test/x#missing)\n[CDN](//example.test/x#missing)\n[Mail](mailto:help@example.test)\n",
        }), 0)

    def test_root_relative_and_directory_readme_fragments(self):
        self.assertEqual(self.check_fixture({
            "README.md": "[Directory](docs/#guide)\n",
            "docs/README.md": "# Guide\n[Root](/README.md)\n",
        }), 2)

    def test_directory_without_readme_does_not_satisfy_fragment(self):
        with self.assertRaisesRegex(ValueError, "broken local anchor"):
            self.check_fixture({
                "README.md": "[Wrong](docs/#missing)\n",
                "docs/file.txt": "data\n",
            })

    def test_relative_traversal_remains_rejected(self):
        with self.assertRaisesRegex(ValueError, "broken local link"):
            self.check_fixture({"README.md": "[Outside](../README.md)\n"})

    def test_historical_evidence_is_preserved_without_becoming_current_navigation(self):
        self.assertEqual(self.check_fixture({
            "README.md": "[History](docs/SCHEMA-V2.md#original)\n",
            "docs/SCHEMA-V2.md": "# Original\n[Former](removed.md)\n",
            "docs/PRESERVATION-ROADMAP.md": "[Former](removed.md)\n",
            "docs/evidence/issue-5-filler-only.md": "[Former](removed.md)\n",
            "docs/evidence/issue-6-spoken-correction.md": "[Former](removed.md)\n",
        }), 1)

    def test_live_files_near_evidence_directory_are_still_checked(self):
        with self.assertRaisesRegex(ValueError, "broken local anchor"):
            self.check_fixture({"docs/evidence-guide.md": "[Wrong](#missing)\n"})

    def test_missing_file_in_reference_definition_is_reported(self):
        with self.assertRaisesRegex(ValueError, "broken local link.*missing.md"):
            self.check_fixture({"README.md": "[Guide][g]\n[g]: missing.md\n"})

    def check_fixture(self, files):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, text in files.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
            return repository_checks.check_links(root)

    def test_valid_same_file_chinese_anchor_is_checked(self):
        self.assertEqual(self.check_fixture({
            "README.md": "# 查找与引用\n[跳转](#查找与引用)\n",
        }), 1)

    def test_missing_heading_reports_source_and_destination(self):
        with self.assertRaisesRegex(ValueError, r"README.md: broken local anchor guide.md#missing"):
            self.check_fixture({"README.md": "[Guide](guide.md#missing)\n", "guide.md": "# Present\n"})

    def test_encoded_unicode_anchor_and_space_in_path(self):
        self.assertEqual(self.check_fixture({
            "README.md": "[Guide](a%20guide.md#%E5%AD%97%E6%AE%B5%E8%AF%AD%E4%B9%89)\n",
            "a guide.md": "# 字段语义\n",
        }), 1)

    def test_heading_formatting_duplicates_and_setext_anchors(self):
        anchors = repository_checks.markdown_anchors(
            "# Hello, **World**!\n# Hello, World!\n# Hello World-1\n"
            "# Hello World\n\nAPI Details\n-----------\n"
            "# `input_units` 与 `some_field_name`\n"
            "# **Bold** &amp; _italic_\n# <em>HTML</em> 与 `<id>`\n"
        )
        self.assertEqual(anchors, {
            "hello-world", "hello-world-1", "hello-world-1-1", "hello-world-2",
            "api-details", "input_units-与-some_field_name", "bold--italic", "html-与-id",
        })

    def test_explicit_html_anchor_and_href_are_checked(self):
        self.assertEqual(self.check_fixture({
            "README.md": '<a name="CaseSensitive"></a>\n<a href="#CaseSensitive">jump</a>\n',
        }), 1)

    def test_explicit_anchor_is_case_sensitive(self):
        with self.assertRaisesRegex(ValueError, "broken local anchor"):
            self.check_fixture({"README.md": '<a id="Exact"></a>\n[Jump](#exact)\n'})

    def test_explicit_anchor_does_not_change_heading_suffix(self):
        self.assertEqual(repository_checks.markdown_anchors(
            '<a name="example"></a>\n# Example\n# Example\n'
        ), {"example", "example-1"})

    def test_code_blocks_inline_code_and_comments_are_not_navigation(self):
        self.assertEqual(self.check_fixture({"README.md": (
            "```markdown\n# Hidden\n[Missing](absent.md)\n```\n"
            "~~~\n[Missing](absent.md)\n~~~\n"
            "`[Missing](absent.md)` and ``[Missing](absent.md)``\n"
            "<!-- [Missing](absent.md) -->\n"
        )}), 0)
        self.assertNotIn("hidden", repository_checks.markdown_anchors(
            "````\n# Hidden\n```\n# Also hidden\n````\n"
        ))

    def test_reference_destination_and_angle_path_are_checked(self):
        self.assertEqual(self.check_fixture({
            "README.md": '[Guide][g]\n\n[g]: <guide (v3).md#api> "details"\n',
            "guide (v3).md": "# API\n",
        }), 1)

    def test_missing_reference_anchor_fails(self):
        with self.assertRaisesRegex(ValueError, "broken local anchor"):
            self.check_fixture({
                "README.md": "[Guide][g]\n[g]: guide.md#missing\n", "guide.md": "# API\n",
            })

    def test_parentheses_in_inline_destination_and_title(self):
        self.assertEqual(self.check_fixture({
            "README.md": '[Guide](guide(v3).md#api "details")\n',
            "guide(v3).md": "# API\n",
        }), 1)

    def test_external_urls_and_source_file_line_fragments(self):
        self.assertEqual(self.check_fixture({
            "README.md": "[Web](https://example.org/no.md#missing)\n"
                         "[Web](//example.org/no.md#missing)\n"
                         "[Mail](mailto:team@example.org)\n[Source](tool.py#L1)\n",
            "tool.py": "pass\n",
        }), 1)

    def test_repository_root_paths_and_directory_readme_fragments(self):
        self.assertEqual(self.check_fixture({
            "README.md": "# Home\n",
            "docs/README.md": "# API\n[Home](/README.md#home)\n[API](.#api)\n",
        }), 2)

    def test_directory_without_readme_cannot_supply_heading(self):
        with self.assertRaisesRegex(ValueError, "broken local anchor"):
            self.check_fixture({
                "README.md": "[API](docs#api)\n", "docs/entry.md": "# API\n",
            })

    def test_relative_escape_remains_rejected(self):
        with self.assertRaisesRegex(ValueError, "broken local link"):
            self.check_fixture({"README.md": "[Outside](../outside.md#api)\n"})

    def test_new_guides_in_historical_directories_are_still_checked(self):
        for name in (
            "docs/evidence/CURRENT-GUIDE.md",
            "docs/decisions/current.md",
            "preservation/current-guide.md",
        ):
            with self.subTest(path=name):
                with self.assertRaisesRegex(ValueError, "broken local link.*missing.md"):
                    self.check_fixture({name: "[Bad](missing.md#absent)\n"})

    def test_links_to_historical_files_still_validate_headings(self):
        with self.assertRaisesRegex(ValueError, "broken local anchor"):
            self.check_fixture({
                "README.md": "[History](docs/SCHEMA-V2.md#missing)\n",
                "docs/SCHEMA-V2.md": "# Historical schema\n",
            })

    def test_history_exemption_does_not_hide_current_guide_errors(self):
        with self.assertRaisesRegex(ValueError, "broken local anchor"):
            self.check_fixture({"docs/evidence-guide.md": "[Missing](#absent)\n"})


if __name__ == "__main__":
    unittest.main()
