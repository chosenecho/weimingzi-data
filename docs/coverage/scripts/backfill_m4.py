#!/usr/bin/env python3
"""Join a completed full-scope M4 audio audit to this M2 inventory without rewriting it."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from inventory import METHOD, OUT, ROOT, digest, dump, read_json, read_lines, summarize, write_lines

TOOL_PATHS = {
    "audit_audio_restore.py": "tools/audit_audio_restore.py",
    "restore_audio.py": "tools/restore_audio.py",
    "records.py": "src/weimingzi_corpus/records.py",
    "schema_v3.py": "src/weimingzi_corpus/schema_v3.py",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def file_state(path):
    return {"size_bytes": path.stat().st_size, "sha256": digest(path)}


def verify_report(path, run):
    before = file_state(path)
    report = read_json(path)
    require(before == file_state(path), "M4 report changed during read")
    require(report["schema"] == "audio-restore-audit/v1", "Expected final M4 report, not a checkpoint")
    for field in ("ok", "index_unchanged", "index_dependencies_unchanged"):
        require(report[field] is True, f"M4 {field} must be true")
    index = "data/assets.jsonl"
    schema = "data/schema.json"
    expect = run["candidate_documents"]
    for source in (index, schema, *TOOL_PATHS.values()):
        if source in expect:
            require(digest(ROOT / source) == expect[source], f"Candidate changed after M2: {source}")
    require(report["index"] == {"path": index, **file_state(ROOT / index)}, "M4 asset index mismatch")
    require(report["index_dependencies"] == [{"path": schema, "exists": True, **file_state(ROOT / schema)}],
            "M4 asset index dependency mismatch")
    require(report["tools"] == {name: file_state(ROOT / file) for name, file in TOOL_PATHS.items()},
            "M4 tool digests do not match candidate")
    audit_start = datetime.fromisoformat(report["started_at"])
    audit_end = datetime.fromisoformat(report["completed_at"])
    inventory_start = datetime.fromisoformat(run["started_at"])
    require(audit_start <= audit_end and audit_end.astimezone(inventory_start.tzinfo).date() == inventory_start.date(),
            "M4 audit is outside this inventory date")
    return report, before


def make_key(archive_key, member_path, local_path):
    return archive_key, member_path, local_path


def observed_files(report, declared):
    archives = {a["m4"]["join_key"]["archive_key"] for a in declared.values()}
    scope = report["scope"]
    require(scope["indexed_restorable_archives"] == len(archives), "M4 indexed archive count mismatch")
    require(scope["selected_archives"] == sorted(archives), "M4 selection differs from full M2 archive scope")
    require(scope["indexed_restorable_audio"] == scope["selected_audio"] == len(declared), "M4 audio scope mismatch")
    require(len(report["archives"]) == len(archives) and {a["archive_key"] for a in report["archives"]} == archives,
            "M4 archive results do not exhaust expected unique archive keys")
    observed = {}
    archive_bytes = audio_bytes = 0
    for ai, archive in enumerate(report["archives"]):
        archive_key = archive["archive_key"]
        expect = archive["expected_archive"]
        require(archive["ok"] is True and archive["observed_archive"] == {k: expect[k] for k in ("size_bytes", "sha256")},
                f"ZIP readback differs from report expectation: {archive_key}")
        archive_bytes += expect["size_bytes"]
        for fi, result in enumerate(archive["files"]):
            key = make_key(archive_key, result["member_path"], result["local_path"])
            require(key not in observed and key in declared, f"Duplicate or unexpected M4 file: {key}")
            locator = declared[key]["m4"]["join_key"]
            require(expect["id"] == locator["archive_asset_id"] and expect["url"] == locator["archive_url"]
                    and expect["size_bytes"] == locator["archive_size_bytes"] and expect["sha256"] == locator["archive_sha256"],
                    f"ZIP expectation differs from M2 locator: {archive_key}")
            expected_file = {"sha256": locator["expected_sha256"], "size_bytes": locator["expected_size_bytes"]}
            require(result["ok"] is True and all(result[k] == expected_file for k in ("expected", "observed_member", "observed_restored")),
                    f"Audio byte readback differs from M2 locator: {key}")
            observed[key] = (f"/archives/{ai}/files/{fi}", f"/archives/{ai}", result)
            audio_bytes += expected_file["size_bytes"]
    require(set(observed) == set(declared), "M4 file results do not exhaust the declared locators")
    return observed, archive_bytes, audio_bytes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Path to the completed audio-restore-audit/v1 report within the candidate")
    args = parser.parse_args()
    path = args.report.resolve()
    report_path = path.relative_to(ROOT).as_posix()
    require(path.parent == ROOT / "preservation/checks", "Use the final M4 report in candidate preservation/checks")
    run = read_json(OUT / "run.json")
    require(run["method"] == METHOD, "Inventory generator and M2 run method differ")
    require(digest(OUT / "inventory.py") == run["inventory_generator_sha256"], "M2 generator digest mismatch")
    for output, sha256 in run["reports_sha256"].items():
        require(digest(OUT / output) == sha256, f"Original M2 output digest mismatch: {output}")
    report, fingerprint = verify_report(path, run)
    assets = read_lines("media-m4-join.jsonl")
    declared = {}
    for asset in assets:
        locator = asset["m4"]["join_key"]
        if locator:
            key = make_key(locator["archive_key"], locator["member_path"], locator["local_path"])
            require(key not in declared, f"Duplicate M2 locator: {key}")
            declared[key] = asset
    checked, archive_bytes, audio_bytes = observed_files(report, declared)

    backfill = []
    for asset in assets:
        locator = asset["m4"]["join_key"]
        record = {"asset_id": asset["id"], "asset_path": asset["path"], "asset_line": asset["line"],
                  "owner_item_ids": asset["owner_item_ids"], "m4_status": "outside_scope_no_locator",
                  "report_path": None, "report_asset_pointer": None}
        if locator:
            key = make_key(locator["archive_key"], locator["member_path"], locator["local_path"])
            pointer, archive_pointer, result = checked[key]
            record.update(m4_status="passed", report_path=report_path, report_asset_pointer=pointer,
                          report_archive_pointer=archive_pointer, archive_asset_id=locator["archive_asset_id"],
                          archive_key=locator["archive_key"], member_path=locator["member_path"],
                          local_path=locator["local_path"], expected=result["expected"],
                          observed_member=result["observed_member"], observed_restored=result["observed_restored"])
        backfill.append(record)
    require(len({row["asset_id"] for row in backfill}) == len(backfill), "Duplicate asset ID in output")
    status_by_asset = {row["asset_id"]: row["m4_status"] for row in backfill}
    detail = read_lines("detail.jsonl")
    groups = summarize(detail)
    old = read_json(OUT / "summary.json")
    require(groups == old["groups"], "M2 summary does not reproduce")
    grouped = defaultdict(list)
    item_status = Counter()
    for row in detail:
        if not row["dimensions"]["media"]["applicable"]:
            continue
        passed_asset_ids = {asset["id"] for asset in row["direct_audio_assets"] if status_by_asset[asset["id"]] == "passed"}
        key = row["channel"], row["kind"]
        entry = (row["item"]["id"], passed_asset_ids)
        grouped[key].append(entry)
        if row["in_first_release_scope"]:
            grouped[row["channel"], "first_release_scope"].append(entry)
            grouped["all", "first_release_scope"].append(entry)
        item_status["passed" if passed_asset_ids else "outside_scope_no_locator"] += 1
    for group in groups:
        candidates = grouped[group["channel"], group["kind"]]
        if not candidates:
            continue
        group["audio"]["current_m4_status"] = "completed_full_locator_scope" if group["audio"]["restorable_units"] else "outside_scope_no_locator"
        group["audio"]["current_m4_passed_units"] = sum(bool(ids) for _, ids in candidates)
        group["audio"]["current_m4_passed_assets"] = len({asset_id for _, ids in candidates for asset_id in ids})
        group["audio"]["outside_m4_scope_no_locator_units"] = sum(not ids for _, ids in candidates)
        require(group["audio"]["current_m4_passed_units"] == group["audio"]["restorable_units"] and
                group["audio"]["current_m4_passed_assets"] == group["audio"]["restorable_assets"],
                "Passed counts differ from the full locator scope")
    write_lines("media-m4-backfill.jsonl", backfill)
    dump("summary-with-m4.json", {**old, "groups": groups, "m4": {
        "report": {"candidate_relative_path": report_path, **fingerprint},
        "filled_at": datetime.now(timezone.utc).isoformat(),
        "m2_summary_sha256": run["reports_sha256"]["summary.json"],
        "m2_detail_sha256": run["reports_sha256"]["detail.jsonl"],
        "m2_media_join_sha256": run["reports_sha256"]["media-m4-join.jsonl"],
        "backfill_generator_sha256": digest(Path(__file__)),
        "backfill_sha256": digest(OUT / "media-m4-backfill.jsonl"),
        "scope": report["scope"], "started_at": report["started_at"], "completed_at": report["completed_at"],
        "index": report["index"], "index_dependencies": report["index_dependencies"], "tools": report["tools"],
        "index_unchanged": True, "index_dependencies_unchanged": True, "ok": True,
        "observed_archive_bytes_total": archive_bytes, "observed_audio_bytes_total": audio_bytes,
        "asset_status_counts": dict(Counter(row["m4_status"] for row in backfill)),
        "applicable_item_status_counts": dict(item_status),
    }})
    print(f"M4 full audit joined to {len(checked)} assets in {len(report['archives'])} ZIP archives. "
          f"{item_status['passed']} inventory units passed. Report SHA-256: {fingerprint['sha256']}")


if __name__ == "__main__":
    main()
