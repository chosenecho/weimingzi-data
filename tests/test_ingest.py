"""Incremental protocol, protected merges and real temporary Git installations."""

import copy
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from weimingzi_corpus.cli import main
from weimingzi_corpus.exports import generate_catalog_docs
from weimingzi_corpus.ingest import (
    IngestError,
    apply_batch,
    plan_batch,
    validate_repository,
    verify_batch,
)
from weimingzi_corpus.ingest.manifest import strict_json, validate_media
from weimingzi_corpus.ingest.merge import merge_record
from weimingzi_corpus.ingest.policy import (
    FIELDS,
    METADATA,
    POLICY,
    SCOPE,
    TABLES,
    TARGET,
)
from weimingzi_corpus.ingest.planning import control_path, snapshot
from weimingzi_corpus.records import (
    JSONL_TABLES,
    JSON_RECORD_TABLES,
    find_timestamp_issues,
    iter_records,
    json_sha256,
    make_record_id,
    read_json,
    transcript_hash_input,
    validate_corpus,
    write_json,
    write_jsonl,
)


def record_id(prefix, key):
    return make_record_id(prefix, ["ingest-test", key])


def fixture_records():
    video = {
        "schema_version": 2,
        "id": record_id("i", "video"),
        "kind": "video",
        "title": "合成视频",
        "identifiers": {"bilibili_bvid": ["BV1aaaaaaaaa"]},
        "urls": ["https://www.bilibili.com/video/BV1aaaaaaaaa/"],
        "metadata": {"uploader_id": ["23191782"]},
        "relations": [],
    }
    part = copy.deepcopy(video)
    part.update(
        id=record_id("i", "part"),
        kind="video_part",
        parent_id=video["id"],
        part_number=1,
        metadata={"cid": [123], "uploader_id": ["23191782"]},
    )
    part["identifiers"]["bilibili_part"] = ["BV1aaaaaaaaa:P1"]
    audio = {
        "schema_version": 2,
        "id": record_id("m", "audio"),
        "kind": "audio",
        "sha256": "a" * 64,
        "size_bytes": 42,
        "availability": "unavailable",
        "unavailable_reason": "not_distributed",
        "item_ids": [part["id"]],
        "metadata": {},
    }
    transcript = {
        "schema_version": 2,
        "id": record_id("t", "asr"),
        "kind": "transcript",
        "item_id": part["id"],
        "method": "asr",
        "model": {"name": "fixture"},
        "language": "zh",
        "text": "合成测试。",
        "time_unit": "ms",
        "segments": [{"index": 0, "start": 0, "end": 1000, "text": "合成测试。"}],
        "quality": {
            "is_fully_human_reviewed": False,
            "requires_review": False,
            "is_subtitle_export_enabled": True,
            "timing_issues": [],
        },
        "audio_ids": [audio["id"]],
    }
    transcript["content_sha256"] = json_sha256(transcript_hash_input(transcript))
    edited = {
        "schema_version": 2,
        "id": record_id("r", "ai"),
        "kind": "edited_transcript",
        "item_id": part["id"],
        "text": "合成测试。",
        "paragraphs": [{"index": 0, "text": "合成测试。"}],
        "time_unit": "ms",
        "model": {"name": "fixture"},
        "notes_markdown": "",
        "is_complete": True,
        "transcript_ids": [transcript["id"]],
        "quality": {"is_fully_human_reviewed": False, "requires_review": True},
        "metadata": {"upstream_revision_id": ["fixture-revision"]},
    }
    return [
        ("items", video),
        ("items", part),
        ("audio", audio),
        ("transcripts", transcript),
        ("edited_transcripts", edited),
    ]


def source():
    return {
        "source_id": "video:fixture",
        "namespace": "bilibili_bvid",
        "external_id": "BV1aaaaaaaaa",
        "publisher_uid": "23191782",
        "url": "https://www.bilibili.com/video/BV1aaaaaaaaa/?p=1",
        "observed_at": "2026-11-04T20:00:00+08:00",
        "relation": "target_publication",
        "referenced_by": [],
        "cid": "123",
        "part_number": 1,
    }


def seal(directory, rows, *, sources=None, run="test", dependencies=None):
    directory.mkdir(parents=True, exist_ok=True)
    files, operations = [], []
    for table, payload, kind, rid, expected, refs in rows:
        path = f"{'observations' if kind == 'enrich' else 'records'}/{table}/{rid}.json"
        write_json(directory / path, payload)
        raw = (directory / path).read_bytes()
        files.append(
            {
                "path": path,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
            }
        )
        operations.append(
            {
                "op": kind,
                "table": table,
                "record_id": rid,
                "path": path,
                "payload_sha256": json_sha256(payload),
                "expected_record_sha256": expected,
                "source_refs": refs,
            }
        )
    manifest = {
        "contract_version": 1,
        "kind": "weimingzi_increment",
        "record_schema_version": 2,
        "target": {"repository": "chosenecho/weimingzi-data", "branch": "main"},
        "producer": {
            "name": "weimingzi-bilibili-ingest",
            "code_revision": "0" * 40,
            "run_id": run,
        },
        "source_scope": {"platform": "bilibili", "target_uid": "23191782"},
        "base_commit": "0" * 40,
        "created_at": "2026-11-04T20:00:00+08:00",
        "requires_batches": dependencies or [],
        "sources": sources if sources is not None else [source()],
        "files": files,
        "operations": operations,
    }
    manifest["batch_id"] = json_sha256(manifest)
    write_json(directory / "manifest.json", manifest)
    return manifest


def reseal(directory, mutate):
    manifest = read_json(directory / "manifest.json")
    mutate(manifest)
    manifest.pop("batch_id")
    manifest["batch_id"] = json_sha256(manifest)
    write_json(directory / "manifest.json", manifest)
    return manifest


def asset():
    return {
        "asset_version": 1,
        "kind": "video",
        "sha256": "a" * 64,
        "size_bytes": 42,
        "mime_type": "video/mp4",
        "locator": {
            "storage": "oss",
            "bucket_alias": "archive",
            "object_key": "media/sha256/" + "a" * 64 + ".mp4",
            "version_id": None,
            "access": "authenticated",
        },
        "verification": {
            "mode": "readback_sha256",
            "verified_at": "2026-11-04T20:00:00+08:00",
            "producer_run_id": "test",
        },
    }


class IngestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        for table in JSONL_TABLES:
            write_jsonl(self.root / "data" / (table + ".jsonl"), [])
        for table in JSON_RECORD_TABLES:
            (self.root / "data" / table).mkdir()
        write_json(
            self.root / "selections/training.json", {"schema_version": 2, "entries": []}
        )
        (self.root / ".gitignore").write_text("/.cache/\n", encoding="utf-8")
        generate_catalog_docs(self.root)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Ingest Test")
        self.git("config", "user.email", "ingest-test@example.invalid")
        self.git(
            "remote",
            "add",
            "origin",
            "https://github.com/chosenecho/weimingzi-data.git",
        )
        self.commit()
        self.records = fixture_records()
        self.batch = self.base / "batch"
        self.plan = self.base / "plan.json"
        self.seal()

    def tearDown(self):
        # Windows Git may leave read-only object files; remove just this verified temp tree.
        def writable_remove(func, path, _):
            os.chmod(path, 0o700)
            func(path)

        shutil.rmtree(self.base, onerror=writable_remove)
        self.temp.cleanup()

    def git(self, *args):
        return (
            subprocess.run(
                ["git", "-C", str(self.root), *args], check=True, capture_output=True
            )
            .stdout.decode()
            .strip()
        )

    def commit(self):
        self.git("add", "-A")
        self.git("commit", "--allow-empty", "-m", "synthetic fixture")

    def seal(self):
        if self.batch.exists():
            shutil.rmtree(self.batch)
        return seal(
            self.batch,
            [
                (t, r, "insert", r["id"], None, ["video:fixture"])
                for t, r in self.records
            ],
        )

    def accept(self):
        report = plan_batch(self.root, self.batch, self.plan)
        self.assertEqual(report["status"], "planned", report["conflicts"])
        result = apply_batch(self.root, self.batch, self.plan)
        self.assertEqual(result["status"], "applied")
        self.commit()
        return report

    def enrichment(self, payload, index=0, expected=None):
        table, row = self.records[index]
        return seal(
            self.base / "enrich",
            [
                (
                    table,
                    payload,
                    "enrich",
                    row["id"],
                    expected or json_sha256(row),
                    ["video:fixture"],
                )
            ],
        )

    def assert_error(self, code, callable_, *args):
        with self.assertRaises(IngestError) as found:
            callable_(*args)
        self.assertEqual(found.exception.code, code)

    def test_runtime_protocol_matches_published_schemas(self):
        contracts = Path(__file__).resolve().parents[1] / "docs" / "contracts"
        batch = json.loads((contracts / "ingest-batch-v1.schema.json").read_text())
        self.assertEqual(
            set(batch["required"]),
            {
                "contract_version",
                "kind",
                "record_schema_version",
                "batch_id",
                "target",
                "producer",
                "source_scope",
                "base_commit",
                "created_at",
                "requires_batches",
                "sources",
                "files",
                "operations",
            },
        )
        self.assertEqual(
            batch["properties"]["target"]["properties"]["repository"]["const"],
            TARGET["repository"],
        )
        self.assertEqual(
            batch["properties"]["target"]["properties"]["branch"]["const"],
            TARGET["branch"],
        )
        self.assertEqual(
            batch["properties"]["source_scope"]["properties"]["target_uid"]["const"],
            SCOPE["target_uid"],
        )
        self.assertEqual(batch["$defs"]["table"]["enum"], list(TABLES))
        self.assertEqual(
            set(batch["$defs"]["operation"]["properties"]["op"]["enum"]),
            {"insert", "enrich", "attach_audio_distribution"},
        )
        enrichment = json.loads(
            (contracts / "ingest-enrichment-v1.schema.json").read_text()
        )
        self.assertEqual(
            set(enrichment["properties"]),
            {field for allowed in FIELDS.values() for field in allowed},
        )
        policy_path = contracts.parent / "examples" / "ingest-policy.toml"
        policy = tomllib.loads(policy_path.read_text(encoding="utf-8"))
        self.assertEqual(policy["policy_version"], POLICY["policy_version"])
        self.assertEqual(policy["repository"], TARGET["repository"])
        self.assertEqual(policy["branch"], TARGET["branch"])
        self.assertEqual(
            {"platform": policy["platform"], "target_uid": policy["target_uid"]},
            SCOPE,
        )
        self.assertEqual(policy["allowed_producers"], POLICY["allowed_producers"])
        self.assertEqual(
            {key: policy["limits"][key] for key in POLICY["limits"]}, POLICY["limits"]
        )
        self.assertEqual(
            set(policy["transport"]["allowed_media_bucket_aliases"]),
            set(POLICY["allowed_media_bucket_aliases"]),
        )
        for table in FIELDS:
            self.assertEqual(set(policy["enrich"][table]["fields"]), set(FIELDS[table]))
            self.assertEqual(
                set(policy["enrich"][table]["metadata_keys"]), set(METADATA[table])
            )
        media = json.loads(
            (contracts / "ingest-media-asset-v1.schema.json").read_text()
        )
        self.assertEqual(
            set(media["required"]),
            {
                "asset_version",
                "kind",
                "sha256",
                "size_bytes",
                "mime_type",
                "locator",
                "verification",
            },
        )
        self.assertEqual(
            set(media["properties"]["locator"]["required"]),
            {"storage", "bucket_alias", "object_key", "version_id", "access"},
        )
        self.assertEqual(
            set(media["properties"]["verification"]["required"]),
            {"mode", "verified_at", "producer_run_id"},
        )

    def test_cross_table_install_receipt_readback_and_replay(self):
        original = snapshot(self.root)
        report = plan_batch(self.root, self.batch, self.plan)
        self.assertEqual(snapshot(self.root), original)
        self.assertEqual(len(report["operations"]), 5)
        self.assertTrue(report["validation"]["valid"])
        self.assertEqual(report, plan_batch(self.root, self.batch))
        result = apply_batch(self.root, self.batch, self.plan)
        self.assertTrue(result["publication_ready"])
        self.assertEqual(validate_corpus(self.root)["edited_transcripts"], 1)
        self.assertEqual(
            validate_repository(self.root), {"receipts": 1, "media_assets": 0}
        )
        self.assertEqual(
            read_json(self.root / "selections/training.json"),
            {"schema_version": 2, "entries": []},
        )
        self.commit()
        repeated = plan_batch(self.root, self.batch, self.plan)
        self.assertEqual(repeated["status"], "already_accepted")
        self.assertEqual(
            apply_batch(self.root, self.batch, self.plan)["changed_files"], 0
        )

    def test_prior_receipt_survives_later_human_edits(self):
        self.accept()
        path = (
            self.root / "data/edited_transcripts" / (self.records[4][1]["id"] + ".json")
        )
        edited = read_json(path)
        edited["quality"]["is_fully_human_reviewed"] = True
        edited["quality"]["requires_review"] = False
        write_json(path, edited)
        generate_catalog_docs(self.root)
        self.commit()
        self.assertEqual(
            plan_batch(self.root, self.batch)["status"], "already_accepted"
        )

    def test_equal_records_without_receipt_do_not_create_empty_changes(self):
        self.accept()
        shutil.rmtree(self.root / "ingest")
        self.commit()
        report = plan_batch(self.root, self.batch, self.plan)
        self.assertEqual(report["status"], "already_present")
        self.assertEqual(report["changes"], [])
        self.assertEqual(
            apply_batch(self.root, self.batch, self.plan)["status"], "already_present"
        )

    def test_enrich_retains_old_order_title_and_nested_observations(self):
        self.accept()
        self.enrichment({"metadata": {"title": ["新标题", ["嵌套", "观测"]]}})
        report = plan_batch(self.root, self.base / "enrich", self.plan)
        self.assertEqual(report["operations"][0]["outcome"], "enriched")
        apply_batch(self.root, self.base / "enrich", self.plan)
        row = next(
            r
            for r, _ in iter_records(self.root, "items")
            if r["id"] == self.records[0][1]["id"]
        )
        self.assertEqual(row["title"], "合成视频")
        self.assertEqual(row["metadata"]["title"], ["新标题", ["嵌套", "观测"]])
        self.assertEqual(row["metadata"]["uploader_id"], ["23191782"])

    def test_enrich_postcondition_precedes_stale_compare_and_swap(self):
        self.accept()
        self.enrichment({"metadata": {"title": ["观测"]}})
        plan_batch(self.root, self.base / "enrich", self.plan)
        apply_batch(self.root, self.base / "enrich", self.plan)
        self.commit()
        reseal(self.base / "enrich", lambda m: m["producer"].update(run_id="replay"))
        self.assertEqual(
            plan_batch(self.root, self.base / "enrich")["status"], "already_present"
        )

    def test_stale_record_precondition_reports_conflict_and_writes_nothing(self):
        self.accept()
        self.enrichment({"metadata": {"title": ["观测"]}}, expected="1" * 64)
        before = snapshot(self.root)
        report = plan_batch(self.root, self.base / "enrich", self.plan)
        self.assertEqual(report["status"], "conflict")
        self.assertEqual(report["exit_code"], 4)
        self.assertEqual(report["conflicts"][0]["code"], "PRECONDITION_FAILED")
        self.assertEqual(snapshot(self.root), before)
        self.assert_error(
            "PRECONDITION_FAILED",
            apply_batch,
            self.root,
            self.base / "enrich",
            self.plan,
        )

    def test_same_id_different_record_conflicts(self):
        self.accept()
        self.records[0][1]["title"] = "覆盖标题"
        self.seal()
        report = plan_batch(self.root, self.batch)
        self.assertEqual(report["conflicts"][0]["code"], "RECORD_CONFLICT")

    def test_different_id_same_external_identity_conflicts(self):
        self.accept()
        self.records = [copy.deepcopy(self.records[0])]
        self.records[0][1]["id"] = record_id("i", "duplicate")
        self.seal()
        self.assertEqual(
            plan_batch(self.root, self.batch)["conflicts"][0]["code"],
            "IDENTITY_AMBIGUOUS",
        )

    def test_same_audio_hash_and_same_transcript_hash_are_not_new_identities(self):
        self.accept()
        for index in (2, 3, 4):
            rows = copy.deepcopy(fixture_records())
            rows[index][1]["id"] = record_id("x", "duplicate")
            self.records = [rows[index]]
            self.seal()
            self.assertEqual(
                plan_batch(self.root, self.batch)["conflicts"][0]["code"],
                "IDENTITY_AMBIGUOUS",
            )

    def test_cid_change_is_held(self):
        reseal(self.batch, lambda m: m["sources"][0].update(cid="456"))
        report = plan_batch(self.root, self.batch)
        self.assertEqual(report["conflicts"][0]["code"], "CID_CHANGED")
        self.assertEqual(list(iter_records(self.root, "items")), [])

    def test_dangling_cross_table_reference_is_rejected(self):
        self.records[4][1]["transcript_ids"] = [record_id("t", "missing")]
        self.seal()
        self.assertEqual(plan_batch(self.root, self.batch)["status"], "conflict")

    def test_changed_head_invalidates_saved_plan(self):
        plan_batch(self.root, self.batch, self.plan)
        self.commit()
        self.assert_error("BASE_MOVED", apply_batch, self.root, self.batch, self.plan)

    def test_forged_but_rehashed_plan_is_not_authority(self):
        report = plan_batch(self.root, self.batch, self.plan)
        report["changes"] = []
        report.pop("plan_id")
        report["plan_id"] = json_sha256(report)
        write_json(self.plan, report)
        self.assert_error(
            "PRECONDITION_FAILED", apply_batch, self.root, self.batch, self.plan
        )
        self.assertEqual(validate_corpus(self.root)["items"], 0)

    def test_changed_package_invalidates_plan(self):
        plan_batch(self.root, self.batch, self.plan)
        reseal(self.batch, lambda m: m["producer"].update(run_id="changed"))
        self.assert_error(
            "PRECONDITION_FAILED", apply_batch, self.root, self.batch, self.plan
        )

    def test_dirty_checkout_and_wrong_origin_are_rejected(self):
        (self.root / "untracked.txt").write_text("manual")
        self.assert_error("PRECONDITION_FAILED", plan_batch, self.root, self.batch)
        (self.root / "untracked.txt").unlink()
        self.git("remote", "set-url", "origin", "https://example.invalid/other.git")
        self.assert_error("PRECONDITION_FAILED", plan_batch, self.root, self.batch)

    def test_ignored_untracked_data_cannot_enter_baseline(self):
        with (self.root / ".gitignore").open("a") as stream:
            stream.write("/data/articles/\n")
        item = {
            "schema_version": 2,
            "id": record_id("i", "tracked-baseline"),
            "kind": "audio_recording",
            "title": "Baseline fixture",
            "identifiers": {"fixture": ["baseline"]},
            "urls": [],
            "metadata": {},
            "relations": [],
        }
        write_jsonl(self.root / "data/items.jsonl", [item])
        self.commit()
        article = {
            "schema_version": 2,
            "id": record_id("c", "hidden"),
            "kind": "article",
            "item_id": item["id"],
            "text": "ignored file fixture",
            "quality": {
                "is_fully_human_reviewed": None,
                "requires_review": False,
            },
        }
        write_json(self.root / "data/articles" / (article["id"] + ".json"), article)
        self.assert_error("PRECONDITION_FAILED", plan_batch, self.root, self.batch)

    def test_unknown_dependency_is_pending(self):
        reseal(self.batch, lambda m: m.update(requires_batches=["b" * 64]))
        self.assert_error("DEPENDENCY_PENDING", plan_batch, self.root, self.batch)

    def test_manifest_byte_collision_with_accepted_batch_is_held(self):
        self.accept()
        path = self.batch / "manifest.json"
        path.write_bytes(path.read_bytes() + b"\n")
        self.assert_error("BATCH_ID_COLLISION", plan_batch, self.root, self.batch)

    def test_local_lock_blocks_second_writer(self):
        plan_batch(self.root, self.batch, self.plan)
        lock = control_path(self.root, "lock")
        lock.write_text("another process")
        self.assert_error(
            "PRECONDITION_FAILED", apply_batch, self.root, self.batch, self.plan
        )
        self.assertTrue(lock.exists())

    def test_interrupted_apply_leaves_marker_and_refuses_reuse(self):
        plan_batch(self.root, self.batch, self.plan)
        from weimingzi_corpus.ingest.planning import install_file

        calls = 0

        def fail_second(source, target):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated disk failure")
            install_file(source, target)

        with patch(
            "weimingzi_corpus.ingest.planning.install_file", side_effect=fail_second
        ):
            with self.assertRaisesRegex(OSError, "simulated"):
                apply_batch(self.root, self.batch, self.plan)
        self.assertTrue(control_path(self.root, "incomplete.json").exists())
        self.assertFalse(control_path(self.root, "lock").exists())
        self.assert_error("WORKTREE_INCOMPLETE", plan_batch, self.root, self.batch)

    def test_corrupt_install_is_detected_on_readback(self):
        plan_batch(self.root, self.batch, self.plan)

        def corrupt(_, target):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("{}")

        with patch(
            "weimingzi_corpus.ingest.planning.install_file", side_effect=corrupt
        ):
            self.assert_error(
                "WORKTREE_INCOMPLETE", apply_batch, self.root, self.batch, self.plan
            )
        self.assertTrue(control_path(self.root, "incomplete.json").exists())

    def test_reports_cannot_overwrite_code_or_batch(self):
        self.assert_error(
            "PRECONDITION_FAILED",
            plan_batch,
            self.root,
            self.batch,
            self.root / "data/items.jsonl",
        )
        self.assert_error(
            "PRECONDITION_FAILED",
            plan_batch,
            self.root,
            self.batch,
            self.batch / "manifest.json",
        )
        result = plan_batch(
            self.root, self.batch, self.root / ".cache/ingest/plan.json"
        )
        self.assertEqual(result["status"], "planned")

    def test_typed_media_acceptance_and_rejected_locator(self):
        self.records[0][1]["metadata"]["media_assets"] = [asset()]
        self.seal()
        self.accept()
        self.assertEqual(validate_repository(self.root)["media_assets"], 1)
        bad = asset()
        bad["locator"]["object_key"] = "https://arbitrary.invalid/file"
        self.assert_error("MEDIA_UNVERIFIED", validate_media, bad)

    def test_media_provenance_cannot_claim_another_run(self):
        self.records[0][1]["metadata"]["media_assets"] = [asset()]
        self.records[0][1]["metadata"]["media_assets"][0]["verification"][
            "producer_run_id"
        ] = "other"
        self.seal()
        self.assertEqual(
            plan_batch(self.root, self.batch)["conflicts"][0]["code"],
            "MEDIA_UNVERIFIED",
        )

    def test_unusable_timing_evidence_is_preserved_not_repaired(self):
        row = self.records[3][1]
        row["segments"].append({"index": 1, "start": -1, "end": 2, "text": "原始异常"})
        row["quality"]["timing_issues"] = find_timestamp_issues(row)
        row["quality"]["is_subtitle_export_enabled"] = False
        row["content_sha256"] = json_sha256(transcript_hash_input(row))
        self.seal()
        self.accept()
        saved = read_json(self.root / "data/transcripts" / (row["id"] + ".json"))
        self.assertEqual(saved["segments"][1]["start"], -1)
        self.assertEqual(saved["quality"], row["quality"])

    def test_strict_json_rejects_duplicates_nan_overflow_and_surrogates(self):
        for raw in (
            b'{"x":1,"x":2}',
            b'{"x":NaN}',
            b'{"x":Infinity}',
            b'{"x":1e9999}',
            b'{"x":"\\ud800"}',
        ):
            self.assert_error("PACKAGE_INTEGRITY_FAILED", strict_json, raw)
        self.assertEqual(strict_json(b'\xef\xbb\xbf{"x":1}'), {"x": 1})

    def test_payload_byte_tampering_and_extra_files_are_rejected(self):
        manifest = read_json(self.batch / "manifest.json")
        payload = self.batch / manifest["files"][0]["path"]
        payload.write_bytes(payload.read_bytes() + b"\n")
        self.assert_error("PACKAGE_INTEGRITY_FAILED", verify_batch, self.batch)
        self.seal()
        (self.batch / "extra.txt").write_text("unexpected")
        self.assert_error("PACKAGE_INTEGRITY_FAILED", verify_batch, self.batch)

    def test_malformed_manifest_contract_and_paths_are_rejected(self):
        mutations = [
            lambda m: m.update(contract_version=True),
            lambda m: m["files"][0].update(path="../outside.json"),
            lambda m: m["files"][0].update(path="records\\items\\x.json"),
            lambda m: m["operations"].append(copy.deepcopy(m["operations"][0])),
            lambda m: m["operations"][0].update(payload_sha256="b" * 64),
            lambda m: m["operations"][0].update(expected_record_sha256="b" * 64),
            lambda m: m.update(unknown="forbidden"),
        ]
        for mutate in mutations:
            self.seal()
            reseal(self.batch, mutate)
            with self.assertRaises(IngestError):
                verify_batch(self.batch)

    def test_hardlinked_payload_is_rejected(self):
        manifest = read_json(self.batch / "manifest.json")
        path = self.batch / manifest["files"][0]["path"]
        os.link(path, self.base / "outside-link.json")
        self.assert_error("PACKAGE_INTEGRITY_FAILED", verify_batch, self.batch)

    def test_symlink_payload_is_rejected_where_supported(self):
        manifest = read_json(self.batch / "manifest.json")
        path = self.batch / manifest["files"][0]["path"]
        target = self.base / "outside.json"
        shutil.copyfile(path, target)
        path.unlink()
        try:
            path.symlink_to(target)
        except OSError:
            self.skipTest("Host cannot create symlinks")
        self.assert_error("PACKAGE_INTEGRITY_FAILED", verify_batch, self.batch)

    def test_wrong_owner_url_and_undeclared_operation_source_are_rejected(self):
        for change in (
            lambda m: m["sources"][0].update(publisher_uid="1"),
            lambda m: m["sources"][0].update(
                url="https://www.bilibili.com.evil.invalid/video/BV1aaaaaaaaa/"
            ),
            lambda m: m["sources"][0].update(
                url="https://www.bilibili.com/video/BV1bbbbbbbbb/"
            ),
            lambda m: m["operations"][0].update(source_refs=["missing"]),
        ):
            self.seal()
            reseal(self.batch, change)
            self.assert_error("SOURCE_SCOPE_VIOLATION", verify_batch, self.batch)

    def test_source_declaration_cannot_cover_an_unrelated_record(self):
        self.records[0][1]["identifiers"]["bilibili_bvid"] = ["BV1bbbbbbbbb"]
        self.seal()
        self.assertEqual(plan_batch(self.root, self.batch)["status"], "conflict")

    def test_reference_cycle_is_rejected(self):
        def change(m):
            first = m["sources"][0]
            second = copy.deepcopy(first)
            first.update(relation="referenced_content", referenced_by=["other"])
            second.update(
                source_id="other",
                external_id="BV1bbbbbbbbb",
                url="https://www.bilibili.com/video/BV1bbbbbbbbb/?p=1",
                referenced_by=[first["source_id"]],
            )
            m["sources"].append(second)

        reseal(self.batch, change)
        self.assert_error("SOURCE_SCOPE_VIOLATION", verify_batch, self.batch)

    def test_automatic_payload_cannot_grant_human_review_or_derivative(self):
        for edit in (
            lambda r: r["quality"].update(is_fully_human_reviewed=True),
            lambda r: r["quality"].update(requires_review=False),
            lambda r: r.update(derived_from_id=record_id("r", "human")),
        ):
            self.records = fixture_records()
            edit(self.records[4][1])
            self.seal()
            with self.assertRaises(IngestError):
                verify_batch(self.batch)

    def test_enrich_whitelist_does_not_allow_text_identity_or_quality_changes(self):
        self.accept()
        for payload in (
            {"title": "override"},
            {"quality": {"is_fully_human_reviewed": True}},
            {"metadata": {"cid": [456]}},
            {"metadata": {"uploader_id": ["1"]}},
            {"metadata": {"unknown": ["x"]}},
        ):
            directory = self.base / "enrich"
            if directory.exists():
                shutil.rmtree(directory)
            self.enrichment(payload)
            with self.assertRaises(IngestError):
                verify_batch(directory)

    def test_distribution_attachment_keeps_audio_identity_and_mirrors(self):
        self.accept()
        old = self.records[2][1]
        full = copy.deepcopy(old)
        full.update(
            availability="available",
            local_path="audio/fixture.m4a",
            downloads=[
                {
                    "release_tag": "audio-fixture",
                    "member_path": "fixture.m4a",
                    "archive": {
                        "name": "audio.tar",
                        "sha256": "b" * 64,
                        "size_bytes": 100,
                        "url": "https://github.com/chosenecho/weimingzi-data/releases/download/audio-fixture/audio.tar",
                    },
                }
            ],
        )
        full.pop("unavailable_reason")
        directory = self.base / "distribution"
        seal(
            directory,
            [
                (
                    "audio",
                    full,
                    "attach_audio_distribution",
                    old["id"],
                    json_sha256(old),
                    ["video:fixture"],
                )
            ],
        )
        report = plan_batch(self.root, directory, self.plan)
        self.assertEqual(report["status"], "planned", report["conflicts"])
        apply_batch(self.root, directory, self.plan)
        self.assertEqual(validate_corpus(self.root)["restorable_audio"], 1)
        self.commit()
        op = read_json(directory / "manifest.json")["operations"][0]
        newer = copy.deepcopy(full)
        newer["downloads"].append(copy.deepcopy(full["downloads"][0]))
        newer["downloads"][1]["release_tag"] = "mirror"
        merged, outcome = merge_record(op, full, newer)
        self.assertEqual(outcome, "unchanged")
        self.assertEqual(len(merged["downloads"]), 2)
        full["item_ids"] = [record_id("i", "unrelated")]
        self.assert_error("RECORD_CONFLICT", merge_record, op, full, old)

    def test_cli_structured_exit_codes(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            result = main(
                ["--root", str(self.root), "ingest", "verify", str(self.batch)]
            )
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "verified")
        (self.batch / "manifest.json").write_text("{}")
        with redirect_stderr(err):
            result = main(
                ["--root", str(self.root), "ingest", "verify", str(self.batch)]
            )
        self.assertEqual(result, 2)
        self.assertEqual(json.loads(err.getvalue())["code"], "PACKAGE_INTEGRITY_FAILED")


if __name__ == "__main__":
    unittest.main()
