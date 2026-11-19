"""Native command and derived-output behavior, exercised through public interfaces."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from native_fixtures import rid, write_corpus
from weimingzi_corpus.cli import import_records, main, validate_export_path
from weimingzi_corpus.exports import (
    export_sqlite, extract_text, generate_catalog_docs, iter_review_issues,
    render_catalog_csv, render_markdown, render_review_markdown, render_subtitles,
)
from weimingzi_corpus.records import ENTITIES, canonical_json, iter_records, write_json


class CorpusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.records = write_corpus(self.root)
        self.raw, self.edited, self.revised = self.records["documents"][:3]
        self.item = self.records["items"][1]

    def command(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--root", str(self.root), *map(str, args)])
        return code, out.getvalue(), err.getvalue()

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in (self.root / "data").rglob("*") if p.is_file()}

    def test_native_entity_json_and_jsonl_roundtrip(self):
        for entity in ENTITIES:
            output = self.root / ".cache" / (entity + ".json")
            self.assertEqual(self.command("export", "--format", "json", "--entity", entity, "--output", output)[0], 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), [row for row, _ in iter_records(self.root, entity)])
        output = self.root / ".cache" / "one.jsonl"
        self.assertEqual(self.command("export", "--format", "jsonl", "--entity", "documents", "--id", self.raw["id"], "--output", output)[0], 0)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), self.raw)
        self.assertNotEqual(self.command("export", "--format", "json", "--id", self.raw["id"], "--output", output)[0], 0)
        self.assertNotEqual(self.command("export", "--format", "txt", "--entity", "assets", "--id", self.raw["id"], "--output", output)[0], 0)

    def test_import_idempotence_conflicts_and_new_native_row(self):
        source = self.root / ".cache" / "incoming.json"
        write_json(source, self.raw)
        self.assertEqual(import_records(self.root, "documents", source), 0)
        before = self.snapshot()
        changed = {**self.raw, "metadata": {"new": True}}
        write_json(source, changed)
        with self.assertRaisesRegex(ValueError, "overwrite"):
            import_records(self.root, "documents", source)
        self.assertEqual(self.snapshot(), before)
        new = {"id": rid("new-article", "a"), "kind": "article", "inputs": [{"role": "item", "target_id": rid("article")}], "text": "新增文章"}
        write_json(source, new)
        self.assertEqual(self.command("import", "--entity", "documents", source)[0], 0)
        self.assertEqual(import_records(self.root, "documents", source), 0)

    def test_import_conflicts_distinguish_json_boolean_integer_and_float_facts(self):
        source = self.root / ".cache" / "incoming.json"
        before = self.snapshot()
        cases = []
        for original, key, value in ((self.raw, "requires_review", 1), (self.edited, "is_fully_human_reviewed", 0)):
            changed = copy.deepcopy(original)
            changed["quality"][key] = value
            cases.append((original, changed))
        for key, value in (("start", 0.0), ("end", 1000.0)):
            changed = copy.deepcopy(self.raw)
            changed["blocks"][0][key] = value
            cases.append((self.raw, changed))
        for case_index, (original, changed) in enumerate(cases):
            with self.subTest(case=case_index):
                # Python considers these values equal; native JSON facts differ.
                self.assertEqual(original, changed)
                self.assertNotEqual(canonical_json(original), canonical_json(changed))
                write_json(source, changed)
                with self.assertRaisesRegex(ValueError, "overwrite a different record"):
                    import_records(self.root, "documents", source)
                self.assertEqual(self.snapshot(), before)

    def test_import_rejects_duplicate_cross_entity_and_invalid_candidate_without_mutation(self):
        source = self.root / ".cache" / "incoming.json"
        before = self.snapshot()
        for incoming in ([self.raw, self.raw], {"id": rid("video"), "kind": "article", "inputs": [{"role": "item", "target_id": rid("article")}], "text": "重复ID"}, {"id": rid("invalid", "a"), "kind": "article", "inputs": [{"role": "item", "target_id": rid("missing")}], "text": "悬空输入"}):
            write_json(source, incoming)
            with self.assertRaises(ValueError):
                import_records(self.root, "documents", source)
            self.assertEqual(self.snapshot(), before)

    def test_failed_candidate_install_preserves_original_bytes(self):
        source = self.root / ".cache" / "incoming.json"
        write_json(source, {"id": rid("new", "a"), "kind": "article", "inputs": [{"role": "item", "target_id": rid("article")}], "text": "新增"})
        before = self.snapshot()
        with patch("weimingzi_corpus.records.install_candidate_updates", side_effect=OSError("install failed")):
            with self.assertRaisesRegex(OSError, "install failed"):
                import_records(self.root, "documents", source)
        self.assertEqual(self.snapshot(), before)

    def test_output_path_protection_including_symlink(self):
        for directory in ("data", "selections", "src", "tools", "tests", "docs", ".git"):
            with self.assertRaises(ValueError):
                validate_export_path(self.root, str(self.root / directory / "output.txt"))
        tracked = self.root / "README.md"
        tracked.write_text("kept", encoding="utf-8")
        with self.assertRaises(ValueError):
            validate_export_path(self.root, str(tracked))
        output = self.root / ".cache/out"
        self.assertEqual(validate_export_path(self.root, str(output)), output.resolve())
        try:
            (self.root / "alias").symlink_to(self.root / "data", target_is_directory=True)
        except OSError:
            return
        with self.assertRaises(ValueError):
            validate_export_path(self.root, str(self.root / "alias/out"))

    def test_subtitles_exact_milliseconds_and_stored_block_order(self):
        before = copy.deepcopy(self.raw)
        srt = render_subtitles(self.raw, "srt")
        self.assertIn("00:00:00,000 --> 00:00:01,000\n原句😀。", srt)
        self.assertIn("00:00:01,000 --> 00:00:02,000\n第二段。", srt)
        self.assertTrue(render_subtitles(self.raw, "vtt").startswith("WEBVTT\n"))
        seconds = copy.deepcopy(self.raw)
        seconds.update(time_unit="s")
        for block in seconds["blocks"]:
            block["start"] /= 1000
            block["end"] /= 1000
        self.assertEqual(render_subtitles(seconds, "srt"), srt)
        self.assertEqual(self.raw, before)

    def test_subtitle_failures_leave_source_and_plain_text_usable(self):
        cases = []
        for bounds in ((-1, 1000), (1000, 1000), (0, 0.1), (0, float("nan"))):
            row = copy.deepcopy(self.raw)
            row["blocks"][0].update(start=bounds[0], end=bounds[1])
            cases.append(row)
        reversed_blocks = copy.deepcopy(self.raw)
        reversed_blocks["blocks"].reverse()
        cases.append(reversed_blocks)
        unsafe = copy.deepcopy(self.raw)
        unsafe["blocks"][0] = {"literal": "bad --> cue", "start": 0, "end": 1000}
        cases.append(unsafe)
        disabled = copy.deepcopy(self.raw)
        disabled["quality"]["is_subtitle_export_enabled"] = False
        cases.append(disabled)
        for row in cases:
            with self.assertRaises(ValueError):
                render_subtitles(row, "srt")
            self.assertEqual(extract_text(row), self.raw["text"])
        with self.assertRaises(ValueError):
            render_subtitles(self.edited, "srt")

    def test_review_text_reference_issues_and_independent_artifact_bytes(self):
        self.edited["blocks"][0]["issues"] = [{"type": "candidate", "candidate": "", "explanation": "原样保留"}]
        write_corpus(self.root, self.records)
        text = render_review_markdown(self.edited, self.item, self.root)
        self.assertIn("输入文字：原句😀。", text)
        self.assertIn(self.edited["notes_markdown"], text)
        issue = list(iter_review_issues(self.edited, self.root))[0]
        self.assertEqual(set(issue), {"document_id", "block_index", "issue_index", "path", "issue"})
        self.assertEqual(issue["issue"]["candidate"], "")
        self.assertEqual(issue["block_index"], 0)
        payload = b"# independent\r\n\r\noriginal bytes\r\n"
        digest = hashlib.sha256(payload).hexdigest()
        artifact = self.root / "data/artifacts" / (digest + ".md")
        artifact.parent.mkdir(parents=True)
        artifact.write_bytes(payload)
        asset = {"id": rid("review", "m"), "kind": "review_document", "sha256": digest, "size_bytes": len(payload), "local_path": artifact.relative_to(self.root).as_posix()}
        self.records["assets"].append(asset)
        self.edited["inputs"].append({"role": "review_document_markdown", "target_id": asset["id"]})
        self.edited.pop("notes_markdown")
        write_corpus(self.root, self.records)
        output = self.root / ".cache/review.md"
        self.assertEqual(self.command("export", "--format", "review_markdown", "--id", self.edited["id"], "--output", output)[0], 0)
        self.assertEqual(output.read_bytes(), payload)
        self.edited["notes_markdown"] = "独立附注"
        self.assertIn("独立附注", render_review_markdown(self.edited, self.item, self.root))
        artifact.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "hash"):
            render_review_markdown(self.edited, self.item, self.root)

    def test_native_sqlite_and_literal_chinese_search(self):
        database = self.root / ".cache/corpus.sqlite3"
        export_sqlite(self.root, database)
        with contextlib.closing(sqlite3.connect(database)) as db:
            self.assertEqual(json.loads(db.execute("SELECT record_json FROM documents WHERE id=?", (self.raw["id"],)).fetchone()[0]), self.raw)
            names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue(set(ENTITIES) <= names)
            self.assertFalse({"transcripts", "edited_transcripts", "collections", "audio"} & names)
        for query in ("第二段", "原句", '" OR *'):
            code, output, _ = self.command("search", query, "--database", database)
            self.assertEqual(code, 0)
            rows = json.loads(output)
            if query != '" OR *':
                self.assertTrue(any(row["id"] == self.raw["id"] for row in rows))
        self.assertNotEqual(self.command("search", "原句", "--database", database, "--limit", "0")[0], 0)

    def test_native_catalog_rebuild_and_post_author_text(self):
        counts = generate_catalog_docs(self.root)
        self.assertEqual(counts["documents"], 5)
        self.assertEqual(generate_catalog_docs(self.root, check=True), counts)
        index = (self.root / "docs/INDEX.md").read_text(encoding="utf-8")
        self.assertIn("documents", index)
        self.assertNotIn("data/transcripts", index)
        csv = render_catalog_csv(self.root)
        self.assertIn("data/documents/", csv)
        post = self.records["documents"][3]
        self.assertEqual(extract_text(post), "动态正文")
        post["content"] = {"modules": {"module_dynamic": {"desc": {"text": "作者说明"}}}, "orig": {"text": "转发正文"}}
        self.assertEqual(extract_text(post), "作者说明")
        self.assertIn("转发正文", render_markdown(post, self.records["items"][2]))
        (self.root / "docs/INDEX.md").write_text("stale", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "stale"):
            generate_catalog_docs(self.root, check=True)


if __name__ == "__main__":
    unittest.main()
