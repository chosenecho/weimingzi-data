import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from weimingzi_corpus.bundle import create, digest, read_rows, seal, verify, write_bytes, write_rows
from weimingzi_corpus.cli import main
from weimingzi_corpus.pipeline import checkout, freeze, import_local, ingest, merge, project


def delivery(path):
    row = {"record_id": "editorial:123", "kind": "editorial", "text": "保留原来的论述。",
           "source": {"platform": "bilibili", "source_id": "BVexample", "group_id": "bilibili:BVexample"},
           "quality": {"status": "passed", "gate": "production-minimum/v1", "semantic_status": "unverified"},
           "provenance": {"review_file": "bronze/review.md"}, "extensions": {"future": [1, 2]},
           "segments": [{"start_ms": 0, "end_ms": 1000, "text": "保留原来的论述。"}]}
    with create(path) as stage:
        write_rows(stage, "records.jsonl", [row])
        write_bytes(stage, "bronze/review.md", b"pending review\n")
        write_bytes(stage, "attachments/user.json", b'{"unknown":true}')
        manifest = seal(stage, "asr-delivery/v1", records_file="records.jsonl", record_count=1)
    return row, manifest


class CorpusTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.row, self.manifest = delivery(self.root / "delivery")
        self.silver = self.root / "silver"
        ingest(self.root / "delivery", self.silver)

    def tearDown(self):
        self.temporary.cleanup()

    def test_bronze_and_unknown_fields_are_retained(self):
        directory = self.silver / "bronze" / self.manifest["bundle_id"]
        self.assertEqual(verify(directory)["bundle_id"], self.manifest["bundle_id"])
        self.assertEqual(read_rows(self.silver / "records.jsonl")[0]["extensions"], {"future": [1, 2]})
        self.assertEqual((directory / "attachments/user.json").read_bytes(), b'{"unknown":true}')

    def test_edit_and_freeze_does_not_reuse_producer_approval(self):
        working = self.root / "working"
        checkout(self.silver, working)
        rows = read_rows(working / "records.jsonl")
        rows[0]["text"] = "用户独立修改的论述。"
        rows[0]["training"] = {"argument": "new arbitrary field"}
        rows[0]["_lineage"] = {"producer_receipt_applies": True}
        (working / "records.jsonl").write_text(json.dumps(rows[0], ensure_ascii=False) + "\n", encoding="utf-8")
        freeze(working, self.root / "edited")
        edited = read_rows(self.root / "edited/records.jsonl")[0]
        self.assertFalse(edited["_lineage"]["producer_receipt_applies"])
        self.assertEqual(edited["quality"]["status"], "downstream-edited")
        self.assertEqual(edited["training"], rows[0]["training"])
        self.assertEqual(verify(self.root / "delivery")["bundle_id"], self.manifest["bundle_id"])
        self.assertEqual(read_rows(self.silver / "records.jsonl")[0]["text"], self.row["text"])
        checkout(self.root / "edited", self.root / "working2")
        freeze(self.root / "working2", self.root / "edited2")
        self.assertFalse(read_rows(self.root / "edited2/records.jsonl")[0]["_lineage"]["producer_receipt_applies"])

    def test_independent_gold_contracts_and_preflight(self):
        repo = Path(__file__).resolve().parents[1]
        cpt = json.loads((repo / "profiles/cpt.json").read_text("utf-8"))
        kb = json.loads((repo / "profiles/knowledge.json").read_text("utf-8"))
        project(self.silver, cpt, self.root / "cpt")
        project(self.silver, kb, self.root / "kb")
        self.assertEqual(set(read_rows(self.root / "cpt/records.jsonl")[0]), {"id", "text", "group_id"})
        self.assertIn("body", read_rows(self.root / "kb/records.jsonl")[0])
        lineage = read_rows(self.root / "cpt/lineage.jsonl")[0]
        self.assertEqual(lineage["output_sha256"], digest(read_rows(self.root / "cpt/records.jsonl")[0]))
        bad = copy.deepcopy(cpt)
        bad["fields"]["speaker"] = "missing.speaker"
        with self.assertRaisesRegex(ValueError, "missing field"):
            project(self.silver, bad, self.root / "bad")
        self.assertFalse((self.root / "bad").exists())

    def test_refuse_corruption_overwrite_and_traversal(self):
        with self.assertRaisesRegex(ValueError, "already exists"):
            ingest(self.root / "delivery", self.silver)
        (self.root / "delivery/records.jsonl").write_text("{}\n", encoding="utf-8")
        self.assertEqual(main(["verify", "--directory", str(self.root / "delivery")]), 1)
        with self.assertRaises(ValueError):
            with create(self.root / "traversal") as stage:
                write_bytes(stage, "../escape", b"no")
        self.assertFalse((self.root / "escape").exists())

    def test_unmodified_freeze_keeps_exact_receipt_scope(self):
        checkout(self.silver, self.root / "working")
        freeze(self.root / "working", self.root / "frozen")
        self.assertTrue(read_rows(self.root / "frozen/records.jsonl")[0]["_lineage"]["producer_receipt_applies"])

    def test_review_and_user_files_can_be_edited_without_touching_bronze(self):
        checkout(self.silver, self.root / "working")
        assets = self.root / "working/assets" / self.manifest["bundle_id"]
        (assets / "bronze/review.md").write_text("用户自己维护的复核记录。\n", encoding="utf-8")
        (assets / "attachments/user.json").write_text('{"new_user_field":42}', encoding="utf-8")
        freeze(self.root / "working", self.root / "frozen")
        self.assertEqual((self.root / "frozen/assets" / self.manifest["bundle_id"] / "attachments/user.json").read_text("utf-8"),
                         '{"new_user_field":42}')
        self.assertEqual(verify(self.root / "delivery")["bundle_id"], self.manifest["bundle_id"])
        checkout(self.root / "frozen", self.root / "working2")
        self.assertEqual((self.root / "working2/assets" / self.manifest["bundle_id"] / "bronze/review.md").read_text("utf-8"),
                         "用户自己维护的复核记录。\n")

    def test_user_content_and_multiple_deliveries_need_no_production_database(self):
        user = {"record_id": "article:one", "text": "独立维护的专栏。",
                "source": {"platform": "user", "source_id": "one", "group_id": "article:one"},
                "tags": ["new"], "quality": {"status": "passed"}}
        write_rows(self.root, "user.jsonl", [user])
        import_local(self.root / "user.jsonl", self.root / "article")
        merge([self.silver, self.root / "article"], self.root / "combined")
        rows = read_rows(self.root / "combined/records.jsonl")
        self.assertEqual(len(rows), 2)
        article = next(row for row in rows if row["record_id"] == "article:one")
        self.assertFalse(article["_lineage"]["producer_receipt_applies"])
        self.assertEqual(article["quality"]["status"], "downstream-imported")
        self.assertEqual(article["tags"], ["new"])
        merge([self.silver, self.silver], self.root / "deduped")
        self.assertEqual(len(read_rows(self.root / "deduped/records.jsonl")), 1)


if __name__ == "__main__":
    unittest.main()
