"""Native protocol, graph permissions, replay evidence and real Git installs."""

import copy
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from native_fixtures import fixture_records, rid, write_corpus
from weimingzi_corpus.ingest import IngestError, apply_batch, plan_batch, validate_repository, verify_batch
from weimingzi_corpus.ingest.manifest import strict_json
from weimingzi_corpus.ingest.merge import merge_record
from weimingzi_corpus.ingest.planning import control_path, snapshot
from weimingzi_corpus.ingest.policy import POLICY, SCOPE, TARGET
from weimingzi_corpus.records import ENTITIES, document_hash_input, iter_records, json_sha256, read_json, validate_corpus, write_json, write_record_updates


def source():
    return {"source_id": "video:fixture", "namespace": "bilibili_bvid", "external_id": "BV1aaaaaaaaa",
            "publisher_uid": "23191782", "url": "https://www.bilibili.com/video/BV1aaaaaaaaa/?p=1",
            "observed_at": "2026-11-04T20:00:00+08:00", "relation": "target_publication", "referenced_by": [], "cid": "123", "part_number": 1}


def ingest_records():
    data = fixture_records()
    rows = {e: [] for e in ENTITIES}
    rows["items"] = copy.deepcopy(data["items"][:2])
    for row in rows["items"]:
        row["identifiers"]["bilibili_bvid"] = ["BV1aaaaaaaaa"]
        row["urls"] = [source()["url"]]
        row["metadata"] = {"uploader_id": ["23191782"]}
        if row["kind"] == "video_part":
            row["identifiers"]["bilibili_part"] = ["BV1aaaaaaaaa:P1"]
            row["metadata"]["cid"] = [123]
    rows["documents"] = copy.deepcopy(data["documents"][:2])
    rows["documents"][1]["model"] = {"name": "fixture-editor"}
    rows["documents"][1]["metadata"] = {"upstream_revision_id": ["fixture-ai-result"]}
    rows["assets"] = copy.deepcopy(data["assets"][:2])
    return rows


def seal(directory, rows, *, sources=None, run="fixture", dependencies=()):
    """Rows are (entity, full native payload, operation, expected SHA, source refs)."""
    directory.mkdir(parents=True, exist_ok=True)
    for previous in directory.glob("records/*/*.json"):
        previous.unlink()
    files, operations = [], []
    for entity, payload, operation, expected, refs in rows:
        path = f"records/{entity}/{payload['id']}.json"
        write_json(directory / path, payload)
        raw = (directory / path).read_bytes()
        files.append({"path": path, "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)})
        operations.append({"op": operation, "entity": entity, "record_id": payload["id"], "path": path,
                           "payload_sha256": json_sha256(payload), "expected_record_sha256": expected, "source_refs": refs})
    value = {"contract_version": 2, "record_schema_version": 3, "kind": "weimingzi_native_increment",
             "target": TARGET, "source_scope": SCOPE, "producer": {"name": "weimingzi-bilibili-ingest", "code_revision": "a" * 40, "run_id": run},
             "base_commit": "b" * 40, "created_at": "2026-11-04T20:00:00+08:00", "sources": [source()] if sources is None else sources,
             "requires_batches": list(dependencies), "files": files, "operations": operations}
    value["batch_id"] = json_sha256(value)
    write_json(directory / "manifest.json", value)
    return value


def inserts(records=None):
    return [(e, r, "insert", None, ["video:fixture"]) for e, rows in (ingest_records() if records is None else records).items() for r in rows]


def rewrite_manifest(directory, mutate):
    path = directory / "manifest.json"
    value = read_json(path)
    mutate(value)
    value.pop("batch_id", None)
    value["batch_id"] = json_sha256(value)
    write_json(path, value)
    return value


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True)
    return result.stdout.decode("utf-8").strip()


def commit(root, message="fixture"):
    git(root, "add", ".")
    git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "-qm", message)


def repository(root, records=None):
    root.mkdir(parents=True, exist_ok=True)
    write_corpus(root, {e: [] for e in ENTITIES} if records is None else records)
    (root / ".gitignore").write_text(".cache/\n", encoding="utf-8")
    git(root, "init", "-q")
    git(root, "remote", "add", "origin", "https://github.com/chosenecho/weimingzi-data.git")
    commit(root)
    return root


class NativeIngestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="native-ingest-test-")
        self.base = Path(self.temp.name)
        self.root = repository(self.base / "repo")
        self.batch = self.base / "batch"

    def tearDown(self):
        self.temp.cleanup()

    def plan(self):
        return plan_batch(self.root, self.batch)

    def apply(self, report=None):
        report = self.plan() if report is None else report
        path = self.base / "plan.json"
        write_json(path, report)
        return apply_batch(self.root, self.batch, path)

    def accept(self):
        seal(self.batch, inserts())
        result = self.apply()
        commit(self.root, "accept native batch")
        return result

    def assert_error(self, code, call):
        with self.assertRaises(IngestError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def test_native_manifest_plan_apply_and_receipt(self):
        manifest = seal(self.batch, inserts())
        self.assertEqual(verify_batch(self.batch).manifest, manifest)
        before = snapshot(self.root)
        report = self.plan()
        self.assertEqual(snapshot(self.root), before)
        self.assertEqual(report["plan_version"], 2)
        self.assertEqual(report["status"], "planned", report)
        self.assertTrue(report["validation"]["valid"], report)
        result = self.apply(report)
        self.assertEqual(result["status"], "applied")
        self.assertEqual({e: validate_corpus(self.root)[e] for e in ENTITIES}, {"items": 2, "documents": 2, "assets": 2, "annotations": 0})
        receipt = read_json(self.root / f"ingest/receipts/{manifest['batch_id']}.json")
        self.assertEqual(receipt["receipt_version"], 2)
        self.assertEqual(receipt["kind"], "weimingzi_native_receipt")
        self.assertTrue(all("entity" in op and "table" not in op for op in receipt["operations"]))
        self.assertFalse(control_path(self.root, "incomplete.json").exists())

    def test_legacy_protocol_and_table_operations_rejected(self):
        seal(self.batch, inserts())
        rewrite_manifest(self.batch, lambda m: m.update(contract_version=1, record_schema_version=2, kind="weimingzi_increment"))
        self.assert_error("UNSUPPORTED_CONTRACT", lambda: verify_batch(self.batch))
        seal(self.batch, inserts())
        rewrite_manifest(self.batch, lambda m: m["operations"][0].update(table=m["operations"][0].pop("entity")))
        self.assert_error("PACKAGE_INTEGRITY_FAILED", lambda: verify_batch(self.batch))

    def test_bounded_strict_json_files_and_inventory(self):
        for raw in (b'{"a":1,"a":2}', b'{"x":NaN}', b'{"x":"\\ud800"}', b'\xff{}'):
            with self.subTest(raw=raw):
                self.assert_error("PACKAGE_INTEGRITY_FAILED", lambda: strict_json(raw))
        seal(self.batch, inserts())
        extra = self.batch / "extra.json"
        extra.write_text("{}", encoding="utf-8")
        self.assert_error("PACKAGE_INTEGRITY_FAILED", lambda: verify_batch(self.batch))
        extra.unlink()
        payload = next((self.batch / "records/items").glob("*.json"))
        payload.write_bytes(payload.read_bytes() + b" ")
        self.assert_error("PACKAGE_INTEGRITY_FAILED", lambda: verify_batch(self.batch))

    def test_limits_paths_target_and_source_scope(self):
        for mutate in (
            lambda m: m["target"].update(repository="elsewhere/repo"),
            lambda m: m["source_scope"].update(target_uid="1"),
            lambda m: m["files"][0].update(path="../outside.json"),
            lambda m: m["operations"][0].update(source_refs=["unknown"]),
            lambda m: m["sources"][0].update(publisher_uid="1"),
        ):
            with self.subTest(mutate=mutate):
                seal(self.batch, inserts())
                rewrite_manifest(self.batch, mutate)
                with self.assertRaises(IngestError):
                    verify_batch(self.batch)
        seal(self.batch, inserts())
        with patch.dict(POLICY["limits"], manifest_bytes=10):
            with self.assertRaises(IngestError):
                verify_batch(self.batch)

    def test_source_binding_and_cid_are_checked_against_native_graph(self):
        rows = ingest_records()
        rows["items"][1]["metadata"]["cid"] = [999]
        seal(self.batch, inserts(rows))
        report = self.plan()
        self.assertEqual(report["status"], "conflict", report)
        self.assertTrue(any(c["code"] == "CID_CHANGED" for c in report["conflicts"]))
        self.assertFalse(report["changes"])

    def test_candidate_whole_graph_validation(self):
        rows = ingest_records()
        rows["documents"][1]["inputs"][1]["target_id"] = rid("missing", "t")
        seal(self.batch, inserts(rows))
        report = self.plan()
        self.assertEqual(report["status"], "conflict", report)
        self.assertFalse(report["changes"])
        self.assertEqual(validate_corpus(self.root)["documents"], 0)

    def test_identity_collision_is_not_duplicate_content_insert(self):
        self.accept()
        row = copy.deepcopy(ingest_records()["items"][0])
        row["id"] = rid("other-video")
        seal(self.batch, [("items", row, "insert", None, ["video:fixture"])], run="duplicate")
        report = self.plan()
        self.assertEqual(report["status"], "conflict", report)
        self.assertEqual(report["conflicts"][0]["code"], "IDENTITY_AMBIGUOUS")

    def test_replace_cas_and_postcondition_precedence(self):
        self.accept()
        row = copy.deepcopy(ingest_records()["items"][0])
        old = json_sha256(row)
        row["metadata"]["observed_at"] = ["2026-11-05T20:00:00+08:00"]
        seal(self.batch, [("items", row, "replace", "0" * 64, ["video:fixture"])], run="stale")
        self.assertEqual(self.plan()["conflicts"][0]["code"], "PRECONDITION_FAILED")
        seal(self.batch, [("items", row, "replace", old, ["video:fixture"])], run="replace")
        self.assertEqual(self.apply()["status"], "applied")
        commit(self.root, "observations")
        # A different batch requesting the already-achieved complete state ignores stale CAS.
        seal(self.batch, [("items", row, "replace", "0" * 64, ["video:fixture"])], run="already")
        report = self.plan()
        self.assertEqual(report["status"], "already_present", report)
        self.assertEqual(report["operations"][0]["outcome"], "unchanged")
        self.assertFalse(report["changes"])

    def test_native_immutable_facts_cannot_be_rewritten(self):
        records = ingest_records()
        for entity, index, mutate in (
            ("items", 0, lambda r: r.update(title="rewritten title")),
            ("documents", 0, lambda r: r["blocks"][0].update(start=10)),
            ("documents", 1, lambda r: r["blocks"][0].update(input_text="invented")),
            ("documents", 1, lambda r: r["quality"].update(requires_review=False)),
            ("items", 1, lambda r: r["metadata"].update(cid=[124])),
        ):
            with self.subTest(entity=entity, mutate=mutate):
                old = records[entity][index]
                row = copy.deepcopy(old)
                mutate(row)
                op = {"entity": entity, "op": "replace", "expected_record_sha256": json_sha256(old)}
                self.assert_error("RECORD_CONFLICT", lambda: merge_record(op, row, old, "fixture"))

    def test_automatic_producer_has_no_human_evidence_permission(self):
        data = fixture_records()
        cases = [("annotations", data["annotations"][0]), ("annotations", data["annotations"][1]),
                 ("documents", data["documents"][2])]
        reviewed = copy.deepcopy(ingest_records()["documents"][0])
        reviewed["quality"]["is_fully_human_reviewed"] = True
        cases.append(("documents", reviewed))
        silent = copy.deepcopy(ingest_records()["documents"][0])
        silent["quality"]["text_status"] = "confirmed_silent"
        cases.append(("documents", silent))
        for entity, row in cases:
            with self.subTest(entity=entity, kind=row["kind"]):
                op = {"entity": entity, "op": "insert", "expected_record_sha256": None}
                self.assert_error("WRITE_PERMISSION_DENIED", lambda: merge_record(op, row, None, "fixture"))

    def test_receipt_replay_reports_current_state_and_preserves_historical_bytes(self):
        self.accept()
        manifest = read_json(self.batch / "manifest.json")
        receipt = self.root / f"ingest/receipts/{manifest['batch_id']}.json"
        historical = receipt.read_bytes()
        self.assertEqual(self.plan()["replay_status"], "accepted_state_present")
        row = next(iter_records(self.root, "items"))[0]
        row["title"] = "later manual observation"
        write_record_updates(self.root, {"items": [row]})
        commit(self.root, "later manual maintenance")
        report = self.plan()
        self.assertEqual(report["status"], "replayed")
        self.assertEqual(report["replay_status"], "accepted_state_changed")
        self.assertEqual(report["accepted_state_changed"][0]["record_id"], row["id"])
        result = self.apply(report)
        self.assertEqual(result["replay_status"], "accepted_state_changed")
        self.assertEqual(result["changed_files"], 0)
        self.assertEqual(receipt.read_bytes(), historical)

    def test_manifest_byte_collision_after_acceptance(self):
        self.accept()
        path = self.batch / "manifest.json"
        path.write_bytes(path.read_bytes() + b"\n")
        self.assert_error("BATCH_ID_COLLISION", self.plan)

    def test_historical_receipts_are_opaque_and_do_not_satisfy_dependencies(self):
        historical_id = "d" * 64
        path = self.root / f"ingest/receipts/{historical_id}.json"
        value = b'{"receipt_version":1,"producer":"retired","operations":[{"table":"retired"}]}\n'
        path.parent.mkdir(parents=True)
        path.write_bytes(value)
        commit(self.root, "historical receipt bytes")
        self.assertEqual(validate_repository(self.root)["historical_receipts"], 1)
        seal(self.batch, inserts(), dependencies=[historical_id])
        self.assert_error("DEPENDENCY_PENDING", self.plan)
        self.assertEqual(path.read_bytes(), value)

    def test_missing_current_dependency_and_fixed_checkout_constraints(self):
        seal(self.batch, inserts(), dependencies=["d" * 64])
        self.assert_error("DEPENDENCY_PENDING", self.plan)
        seal(self.batch, inserts())
        (self.root / "dirty.txt").write_text("dirty", encoding="utf-8")
        self.assert_error("PRECONDITION_FAILED", self.plan)
        (self.root / "dirty.txt").unlink()
        git(self.root, "remote", "set-url", "origin", "https://example.org/other.git")
        self.assert_error("PRECONDITION_FAILED", self.plan)

    def test_plan_binds_snapshot_policy_and_head(self):
        seal(self.batch, inserts())
        report = self.plan()
        with patch.dict(POLICY, policy_version=999):
            self.assert_error("PRECONDITION_FAILED", lambda: self.apply(report))
        (self.root / "observation.txt").write_text("baseline changed", encoding="utf-8")
        commit(self.root, "move baseline")
        self.assert_error("BASE_MOVED", lambda: self.apply(report))

    def test_lock_and_failed_install_leave_incomplete_guard(self):
        seal(self.batch, inserts())
        report = self.plan()
        lock = control_path(self.root, "lock")
        lock.write_text("another installer", encoding="utf-8")
        self.assert_error("PRECONDITION_FAILED", lambda: self.apply(report))
        lock.unlink()
        with patch("weimingzi_corpus.ingest.planning.install_candidate_updates", side_effect=OSError("injected interruption")):
            with self.assertRaisesRegex(OSError, "injected interruption"):
                self.apply(report)
        self.assertTrue(control_path(self.root, "incomplete.json").is_file())
        self.assertFalse(lock.exists())
        self.assert_error("WORKTREE_INCOMPLETE", self.plan)
        self.assert_error("WORKTREE_INCOMPLETE", lambda: validate_repository(self.root))

    def test_postcondition_and_immutable_facts_use_exact_native_json(self):
        for before, after in ((False, 0), (True, 1), (1, 1.0)):
            with self.subTest(before=before, after=after):
                old = copy.deepcopy(ingest_records()["items"][0])
                old["metadata"]["upstream_run_id"] = [before]
                changed = copy.deepcopy(old)
                changed["metadata"]["upstream_run_id"] = [after]
                op = {"entity": "items", "op": "replace", "expected_record_sha256": "0" * 64}
                self.assert_error("PRECONDITION_FAILED", lambda: merge_record(op, changed, old, "fixture"))
                op["expected_record_sha256"] = json_sha256(old)
                self.assert_error("RECORD_CONFLICT", lambda: merge_record(op, changed, old, "fixture"))
                old["opaque_original_fact"] = {"value": before}
                changed = copy.deepcopy(old)
                changed["opaque_original_fact"]["value"] = after
                op["expected_record_sha256"] = json_sha256(old)
                self.assert_error("RECORD_CONFLICT", lambda: merge_record(op, changed, old, "fixture"))

    def test_observation_json_type_changes_fail_without_rewriting_native_bytes(self):
        rows = ingest_records()
        original = rows["items"][0]
        original["metadata"]["upstream_run_id"] = [False, 1, {"flag": True}]
        write_record_updates(self.root, rows)
        commit(self.root, "preserve typed original observations")
        before = snapshot(self.root)
        for observations in ([0, 1, {"flag": True}], [False, 1.0, {"flag": True}], [False, 1, {"flag": 1}]):
            with self.subTest(observations=observations):
                changed = copy.deepcopy(original)
                changed["metadata"]["upstream_run_id"] = observations
                seal(self.batch, [("items", changed, "replace", json_sha256(original), ["video:fixture"])])
                report = self.plan()
                self.assertEqual(report["status"], "conflict", report)
                self.assertEqual(report["conflicts"][0]["code"], "RECORD_CONFLICT")
                self.assertFalse(report["changes"])
                self.assertEqual(snapshot(self.root), before)

    def test_installation_io_failure_uses_shared_rollback_and_keeps_guard(self):
        seal(self.batch, inserts())
        report = self.plan()
        before = snapshot(self.root)
        from weimingzi_corpus.records import install_candidate_updates
        replace = os.replace
        installed = []

        def interrupted_install(root, candidate, paths):
            def interrupt(source_path, target_path):
                installed.append(Path(target_path).relative_to(root).as_posix())
                if len(installed) == 2:
                    raise OSError("injected second-file replacement failure")
                return replace(source_path, target_path)
            with patch("weimingzi_corpus.records.os.replace", side_effect=interrupt):
                install_candidate_updates(root, candidate, paths)

        with patch("weimingzi_corpus.ingest.planning.install_candidate_updates", side_effect=interrupted_install):
            with self.assertRaisesRegex(OSError, "injected second-file replacement failure"):
                self.apply(report)
        self.assertEqual(len(installed), 2)
        self.assertEqual(snapshot(self.root), before)
        self.assertTrue(control_path(self.root, "incomplete.json").is_file())
        self.assert_error("WORKTREE_INCOMPLETE", self.plan)

    def test_hardlinked_package_manifest_and_payload_are_rejected(self):
        for label in ("manifest", "payload"):
            with self.subTest(label=label):
                manifest = seal(self.batch, inserts())
                target = self.batch / ("manifest.json" if label == "manifest" else manifest["files"][0]["path"])
                external = self.base / (label + "-outside.json")
                external.write_bytes(target.read_bytes())
                target.unlink()
                os.link(external, target)
                self.assert_error("PACKAGE_INTEGRITY_FAILED", lambda: verify_batch(self.batch))
                target.unlink()

    def test_installation_readback_fails_closed(self):
        seal(self.batch, inserts())
        report = self.plan()
        with patch("weimingzi_corpus.ingest.planning.install_candidate_updates", return_value=None):
            self.assert_error("WORKTREE_INCOMPLETE", lambda: self.apply(report))
        self.assertTrue(control_path(self.root, "incomplete.json").is_file())

    def test_postcondition_equality_preserves_native_json_types(self):
        for before, after in ((False, 0), (True, 1), (1, 1.0)):
            with self.subTest(before=before, after=after):
                old = copy.deepcopy(ingest_records()["items"][0])
                old["metadata"]["source_observation"] = [before]
                changed = copy.deepcopy(old)
                changed["metadata"]["source_observation"] = [after]
                op = {"entity": "items", "op": "replace", "expected_record_sha256": "0" * 64}
                self.assert_error("PRECONDITION_FAILED", lambda: merge_record(op, changed, old, "fixture"))
                op.update(op="insert", expected_record_sha256=None)
                self.assert_error("RECORD_CONFLICT", lambda: merge_record(op, changed, old, "fixture"))

    def test_observation_prefix_rejects_equal_python_values_without_changing_bytes(self):
        records = ingest_records()
        records["items"][0]["metadata"]["source_observation"] = [False, 1]
        write_record_updates(self.root, records)
        commit(self.root, "preserve original source observations")
        before = snapshot(self.root)
        old = next(row for row, _ in iter_records(self.root, "items") if row["kind"] == "video")
        for observations in ([0, 1], [False, 1.0], [0, 1, "new"], [False, 1.0, "new"]):
            with self.subTest(observations=observations):
                changed = copy.deepcopy(old)
                changed["metadata"]["source_observation"] = observations
                seal(self.batch, [("items", changed, "replace", json_sha256(old), ["video:fixture"])])
                report = self.plan()
                self.assertEqual(report["status"], "conflict", report)
                self.assertEqual(report["conflicts"][0]["code"], "RECORD_CONFLICT", report)
                self.assertFalse(report["changes"])
                self.assertEqual(snapshot(self.root), before)

    def test_immutable_fact_equality_preserves_native_json_types(self):
        for before, after in ((False, 0), (True, 1), (1, 1.0)):
            with self.subTest(before=before, after=after):
                old = copy.deepcopy(ingest_records()["documents"][0])
                old["model"]["original_parameter"] = before
                changed = copy.deepcopy(old)
                changed["model"]["original_parameter"] = after
                op = {"entity": "documents", "op": "replace", "expected_record_sha256": json_sha256(old)}
                self.assert_error("RECORD_CONFLICT", lambda: merge_record(op, changed, old, "fixture"))

    def test_reports_cannot_overwrite_tracked_inputs_or_batch(self):
        seal(self.batch, inserts())
        for output in (self.root / "data/items.jsonl", self.batch / "manifest.json"):
            with self.subTest(output=output):
                self.assert_error("PRECONDITION_FAILED", lambda: plan_batch(self.root, self.batch, output))


if __name__ == "__main__":
    unittest.main()
