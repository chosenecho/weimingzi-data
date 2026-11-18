"""Native kinds, edges, cycles and local confirmation evidence invariants."""
import copy
from pathlib import Path
import tempfile
import unittest

from native_fixtures import fixture_records, rid, text_sha256, write_corpus
from weimingzi_corpus.records import (
    block_text, document_hash_input, json_sha256, load_document,
    validate_corpus, write_json, write_jsonl, write_record_updates,
)
from weimingzi_corpus.schema_v3 import validate_native


class NativeSchemaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "corpus"
        self.rows = fixture_records()
        write_corpus(self.root, self.rows)

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        write_corpus(self.root, self.rows)

    def assert_invalid(self, message):
        self.save()
        with self.assertRaisesRegex(ValueError, message):
            validate_corpus(self.root)

    def test_native_counts_include_independent_assets_and_entity_kinds(self):
        counts = validate_corpus(self.root)
        self.assertEqual({key: counts[key] for key in ("items", "documents", "assets", "annotations", "blocks")}, {"items": 5, "documents": 5, "assets": 3, "annotations": 2, "blocks": 6})
        self.assertEqual(counts["documents_edited_transcript"], 2)
        self.assertEqual(counts["assets_archive"], 2)
        self.assertEqual(validate_native(self.root), [])
        for name in ("transcripts", "edited_transcripts", "articles", "posts", "confirmations", "attributions"):
            self.assertNotIn(name, counts)

    def test_missing_native_storage_and_unknown_schema_fail_closed(self):
        (self.root / "data/annotations.jsonl").unlink()
        self.assertIn("Missing native storage", validate_native(self.root)[0])
        self.save()
        write_json(self.root / "data/schema.json", {"schema_version": 3})
        self.assertIn("native four-entity", validate_native(self.root)[0])

    def test_no_projection_or_reconstruction_fields(self):
        for key, value in (("_legacy", {}), ("schema_version", 2), ("segments", []), ("item_id", self.rows["items"][1]["id"]), ("index_absent", True)):
            with self.subTest(key=key):
                rows = fixture_records()
                rows["documents"][0][key] = value
                write_corpus(self.root, rows)
                with self.assertRaisesRegex(ValueError, "unknown fields"):
                    validate_corpus(self.root)
        self.save()
        self.rows["documents"][0]["blocks"][0]["index"] = 0
        self.assert_invalid("unknown fields")

    def test_document_and_asset_kinds_dispatch_directly(self):
        self.rows["documents"][3]["kind"] = "article"
        self.assert_invalid("unknown fields|wrong-kind item owner")
        self.rows = fixture_records()
        self.rows["assets"][2]["kind"] = "review_document_markdown"
        self.assert_invalid("unexpected assets kind")

    def test_document_owner_cardinality_and_kind(self):
        for edges in ([], [{"role": "item", "target_id": self.rows["items"][0]["id"]}, {"role": "item", "target_id": self.rows["items"][1]["id"]}], [{"role": "item", "target_id": self.rows["items"][2]["id"]}]):
            with self.subTest(edges=edges):
                self.rows = fixture_records()
                self.rows["documents"][0]["inputs"] = edges
                self.rows["documents"][0]["content_sha256"] = json_sha256(document_hash_input(self.rows["documents"][0]))
                self.assert_invalid("exactly one item|wrong-kind item owner")

    def test_unknown_wrong_kind_and_duplicate_edges(self):
        doc = self.rows["documents"][1]
        for edge, message in (({"role": "transcript", "target_id": doc["id"]}, "wrong-kind transcript"), ({"role": "audio", "target_id": self.rows["assets"][0]["id"]}, "invalid inputs role"), ({"role": "transcript", "target_id": rid("missing", "t")}, "unresolved")):
            with self.subTest(edge=edge):
                self.rows = fixture_records()
                self.rows["documents"][1]["inputs"].append(edge)
                self.assert_invalid(message)
        self.rows = fixture_records()
        self.rows["documents"][1]["inputs"].append(copy.deepcopy(self.rows["documents"][1]["inputs"][1]))
        self.assert_invalid("duplicate transcript")

    def test_issue_candidates_keep_absent_null_and_empty_separate(self):
        for candidate in ({}, {"candidate": None}, {"candidate": ""}, {"candidate": "原样候选"}):
            with self.subTest(candidate=candidate):
                self.rows = fixture_records()
                issue = {"note": "待回查，未推断是否采用", **candidate}
                self.rows["documents"][1]["blocks"][0]["issues"] = [issue]
                self.save()
                self.assertEqual(validate_native(self.root), [])
                actual = load_document(self.root, self.rows["documents"][1]["id"])
                self.assertEqual(actual["blocks"][0]["issues"], [issue])
        self.rows["documents"][1]["blocks"][0]["issues"][0]["candidate"] = False
        self.assert_invalid("candidate must be text or null")

    def test_same_item_constraints_for_input_and_annotation(self):
        self.rows["documents"][1]["inputs"][0]["target_id"] = self.rows["items"][0]["id"]
        self.assert_invalid("different item")
        self.rows = fixture_records()
        self.rows["annotations"][0]["targets"][0]["target_id"] = self.rows["items"][0]["id"]
        self.assert_invalid("different item")

    def test_reference_sources_hashes_ranges_and_direct_input_checked(self):
        for name, value, message in (("source", "segments", "invalid input text source"), ("content_sha256", "d" * 64, "hash mismatch"), ("range", [0, 999], "range outside text"), ("range", [False, 1], "invalid Unicode codepoint range")):
            with self.subTest(name=name):
                self.rows = fixture_records()
                self.rows["documents"][1]["blocks"][0]["input_text_ref"][name] = value
                self.assert_invalid(message)
        self.rows = fixture_records()
        self.rows["documents"][1]["inputs"] = self.rows["documents"][1]["inputs"][:1]
        self.assert_invalid("transcript input")

    def test_transcript_hash_native_and_recognition_hash_independent(self):
        transcript = self.rows["documents"][0]
        transcript["recognition_chunks"] = [{"id": "chunk-1", "time_unit": "ms", "sentences": []}]
        transcript["recognition_chunks_sha256"] = json_sha256(transcript["recognition_chunks"])
        self.save()
        self.assertEqual(validate_native(self.root), [])
        transcript["recognition_chunks"][0]["sentences"].append({"text": "未改正文的识别观测", "start": -10, "end": 1})
        self.assert_invalid("recognition chunks SHA-256 mismatch")
        transcript["recognition_chunks_sha256"] = json_sha256(transcript["recognition_chunks"])
        self.save()
        self.assertEqual(validate_native(self.root), [])
        transcript["text"] += "改变正文"
        self.assert_invalid("content SHA-256 mismatch")

    def test_original_time_anomalies_are_preserved(self):
        self.rows["annotations"] = []
        raw, edited, revision = self.rows["documents"][:3]
        raw["blocks"][0].update(start=-4.125, end=-10)
        raw["content_sha256"] = json_sha256(document_hash_input(raw))
        edited["blocks"][0]["input_text_ref"]["content_sha256"] = raw["content_sha256"]
        edited["blocks"][0].update(start=2000, end=1000.125)
        self.save()
        self.assertEqual(validate_native(self.root), [])
        self.assertEqual(load_document(self.root, edited["id"])["blocks"][0]["end"], 1000.125)

    def test_quality_null_false_absence_and_model_observations(self):
        self.rows["documents"][0]["quality"]["is_fully_human_reviewed"] = None
        self.rows["documents"][1]["quality"]["is_fully_human_reviewed"] = False
        self.rows["documents"][2].pop("quality")
        self.save()
        self.assertEqual(validate_native(self.root), [])
        self.rows["documents"][1]["quality"]["is_fully_human_reviewed"] = "true"
        self.assert_invalid("boolean or null")
        self.rows = fixture_records()
        self.rows["documents"][1]["model"] = "made-up-model"
        self.assert_invalid("model must")

    def test_explicit_recognition_issue_seconds_and_evidence(self):
        raw, edited = self.rows["documents"][:2]
        raw["recognition_chunks"] = [{"id": "c1", "time_unit": "ms", "sentences": []}]
        raw["recognition_chunks_sha256"] = json_sha256(raw["recognition_chunks"])
        edited["quality"]["recognition_issue_intervals"] = [{"start_seconds": 1.1, "end_seconds": 2.2, "evidence": {"transcript_id": raw["id"], "recognition_chunk_ids": ["c1"]}}]
        self.save()
        self.assertEqual(validate_native(self.root), [])
        edited["quality"]["recognition_issue_intervals"][0]["evidence"]["recognition_chunk_ids"] = ["missing"]
        self.assert_invalid("recognition chunk evidence")
        edited["quality"]["recognition_issue_intervals"] = [{"start": 1, "end": 2}]
        self.assert_invalid("explicit seconds")

    def test_independent_and_combined_inheritance_cycles(self):
        for first, second in (("derived_from", "derived_from"), ("input_units_from", "input_units_from"), ("derived_from", "input_units_from")):
            with self.subTest(first=first, second=second):
                self.rows = fixture_records()
                self.rows["annotations"] = []
                a, b = self.rows["documents"][1:3]
                a.pop("input_units", None)
                a["inputs"] = a["inputs"][:2] + [{"role": first, "target_id": b["id"]}]
                b["inputs"] = b["inputs"][:2] + [{"role": second, "target_id": a["id"]}]
                self.assert_invalid("cycle")

    def test_diamond_inheritance_is_not_a_cycle(self):
        self.rows["annotations"] = []
        base, revision = self.rows["documents"][1:3]
        branch = copy.deepcopy(base)
        branch["id"] = rid("branch", "r")
        branch.pop("input_units")
        branch["inputs"].append({"role": "derived_from", "target_id": base["id"]})
        revision["inputs"] = revision["inputs"][:2] + [{"role": "derived_from", "target_id": branch["id"]}, {"role": "input_units_from", "target_id": base["id"]}]
        self.rows["documents"].append(branch)
        self.save()
        self.assertEqual(validate_native(self.root), [])

    def test_inline_snapshot_and_inherited_snapshot_mutually_exclusive(self):
        base, revision = self.rows["documents"][1:3]
        revision["input_units"] = copy.deepcopy(base["input_units"])
        self.assert_invalid("mutually exclusive")

    def test_confirmation_requires_actual_corrected_revision_anchor(self):
        self.rows["documents"][2]["text"] = self.rows["documents"][1]["text"]
        self.assert_invalid("confirmation text not located")
        self.rows = fixture_records()
        self.rows["annotations"][0]["anchor"]["paragraph_index"] = 1
        self.assert_invalid("confirmation text not located")

    def test_confirmation_checks_every_target(self):
        foreign = copy.deepcopy(self.rows["documents"][1])
        foreign["id"] = rid("unrelated-same-owner", "r")
        foreign["text"] = "别句😀。\n\n第二段。"
        self.rows["documents"].append(foreign)
        self.rows["annotations"][0]["targets"].append({"role": "applies_to", "target_id": foreign["id"]})
        self.assert_invalid("confirmation text not located")

    def test_confirmation_hash_status_scope_and_evidence(self):
        for change, message in ((lambda a: a["anchor"].update(original_text_sha256="f" * 64), "anchor hash mismatch"), (lambda a: a.update(corrected_text_sha256="f" * 64), "corrected text hash mismatch"), (lambda a: a.update(scope="whole_document"), "local_text_or_term"), (lambda a: a.update(status="model_suggested"), "user_confirmed"), (lambda a: a["confirmation"].pop("reviewer_label"), "missing review evidence")):
            with self.subTest(message=message):
                self.rows = fixture_records()
                change(self.rows["annotations"][0])
                self.assert_invalid(message)

    def test_only_revision_target_has_order_and_orders_contiguous(self):
        annotation = self.rows["annotations"][0]
        annotation["targets"][1]["order"] = 0
        self.assert_invalid("only revision")
        for order in (None, False, -1, 1):
            with self.subTest(order=order):
                self.rows = fixture_records()
                edge = self.rows["annotations"][0]["targets"][2]
                if order is None:
                    edge.pop("order")
                else:
                    edge["order"] = order
                self.assert_invalid("nonnegative order|contiguous")

    def test_revision_order_unique_across_annotations_and_local_review_not_promoted(self):
        second = copy.deepcopy(self.rows["annotations"][0])
        second["id"] = rid("second-confirmation", "a")
        self.rows["annotations"].append(second)
        self.assert_invalid("contiguous")
        second["targets"][2]["order"] = 1
        self.save()
        self.assertEqual(validate_native(self.root), [])
        self.assertFalse(load_document(self.root, self.rows["documents"][2]["id"])["quality"]["is_fully_human_reviewed"])

    def test_audio_restore_edges_and_available_state(self):
        audio = self.rows["assets"][0]
        audio["downloads"][0]["archive_id"] = audio["id"]
        self.assert_invalid("wrong-kind archive")
        self.rows = fixture_records()
        self.rows["assets"][0]["downloads"] = []
        self.assert_invalid("incomplete audio restore locator")
        self.rows = fixture_records()
        self.rows["assets"][0]["availability"] = "unavailable"
        self.rows["assets"][0]["downloads"] = []
        self.save()
        self.assertEqual(validate_native(self.root), [])

    def test_artifact_byte_hash_and_path_are_checked(self):
        artifact = b"<p>original bytes\r\n</p>"
        path = self.root / "data/artifacts/html/fixture.html"
        path.parent.mkdir(parents=True)
        path.write_bytes(artifact)
        html = {"id": rid("html", "h"), "kind": "html", "local_path": "data/artifacts/html/fixture.html", "sha256": __import__("hashlib").sha256(artifact).hexdigest(), "size_bytes": len(artifact)}
        self.rows["assets"].append(html)
        self.rows["documents"][4]["inputs"].append({"role": "html", "target_id": html["id"]})
        self.save()
        self.assertEqual(validate_native(self.root), [])
        path.write_bytes(artifact.replace(b"\r\n", b"\n"))
        self.assertIn("artifact byte hash mismatch", " ".join(validate_native(self.root)))


if __name__ == "__main__":
    unittest.main()
