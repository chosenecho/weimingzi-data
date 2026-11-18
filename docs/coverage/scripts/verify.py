#!/usr/bin/env python3
"""Resolve every ID, path and line the M2 detail and samples hand off, then recheck the M4 layer."""
import argparse
from functools import lru_cache
import json
import sys

sys.dont_write_bytecode = True
from inventory import OUT, ROOT, digest, read_json, read_lines
from weimingzi_corpus.records import block_text, iter_records


def index_native():
    items, documents, assets, annotations = {}, {}, {}, {}
    for entity, target in (("items", items), ("documents", documents), ("assets", assets), ("annotations", annotations)):
        for row, path in iter_records(ROOT, entity):
            assert row["id"] not in target, row["id"]
            target[row["id"]] = (row, path.relative_to(ROOT).as_posix())
    return items, documents, assets, annotations


@lru_cache(maxsize=3)
def line_ids(path):
    with path.open(encoding="utf-8-sig") as stream:
        return {line: json.loads(raw)["id"] for line, raw in enumerate(stream, 1) if raw.strip()}


def check_line(path, line, entity_id):
    assert line_ids(path).get(line) == entity_id, f"{path}:{line} does not resolve to {entity_id}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", default="preservation/checks/restore-first-release-full-2026-11-18.json")
    args = parser.parse_args()
    run = read_json(OUT / "run.json")
    for name, sha256 in run["reports_sha256"].items():
        assert digest(OUT / name) == sha256, f"M2 output drifted: {name}"
    items, documents, assets, annotations = index_native()
    detail = read_lines("detail.jsonl")
    assert len(detail) == len({row["item"]["id"] for row in detail}) == run["counts"]["detail"]
    resolved = 0
    for row in detail:
        item_id = row["item"]["id"]
        native, path = items[item_id]
        assert row["item"]["path"] == path and native["kind"] == row["kind"]
        check_line(ROOT / path, row["item"]["line"], item_id)
        assert row["source_identifiers"] == native.get("identifiers", {})
        assert len(row["dimensions"]) == 5
        for document in row["native_direct_documents"]:
            doc, doc_path = documents[document["id"]]
            assert document["path"] == doc_path and doc["kind"] == document["kind"]
            assert any(ref["target_id"] == item_id and ref["role"] == "item" for ref in doc["inputs"])
            resolved += 1
        for asset in row["direct_audio_assets"]:
            record, asset_path = assets[asset["id"]]
            assert asset["path"] == asset_path and record["kind"] == "audio"
            check_line(ROOT / asset_path, asset["line"], asset["id"])
            assert item_id in [ref["target_id"] for ref in record["inputs"] if ref["role"] == "item"]
            resolved += 1
        for note in row["local_annotations"]:
            record, note_path = annotations[note["id"]]
            assert note["path"] == note_path and record["kind"] == note["kind"]
            check_line(ROOT / note_path, note["line"], note["id"])
            assert any(ref["target_id"] == item_id and ref["role"] == "item" for ref in record["targets"])
            resolved += 1
        for artifact in row["document_artifacts"]:
            assert artifact["id"] in assets and assets[artifact["id"]][0]["kind"] in {"html", "review_document"}
            resolved += 1
    for sample in read_json(OUT / "samples.json")["samples"]:
        for reading in sample["body_block_readback"]:
            native = read_json(ROOT / reading["path"])
            block = native["blocks"][0]
            exact = block_text(native, block)
            assert len(exact) == reading["chars"] and digest_text(exact) == reading["sha256_utf8"]
            resolved += 1
    join = read_lines("media-m4-join.jsonl")
    backfill = read_lines("media-m4-backfill.jsonl")
    assert len(join) == run["counts"]["m4_asset_rows"] == len(backfill)
    assert {row["id"] for row in join} == {row["asset_id"] for row in backfill}
    by_asset_id = {row["asset_id"]: row for row in backfill}
    assert len(by_asset_id) == len(backfill)
    report = read_json(ROOT / args.report)
    matched = 0
    for asset in join:
        locator = asset["m4"]["join_key"]
        pointer = by_asset_id[asset["id"]]
        if not locator:
            assert pointer["m4_status"] == "outside_scope_no_locator" and pointer["report_path"] is None
            continue
        node = report
        for step in pointer["report_asset_pointer"].strip("/").split("/"):
            node = node[int(step)] if isinstance(node, list) else node[step]
        assert node["member_path"] == locator["member_path"] and node["local_path"] == locator["local_path"]
        assert node["ok"] is True and node["expected"]["sha256"] == locator["expected_sha256"]
        assert pointer["report_path"] == args.report
        matched += 1
    assert matched == report["scope"]["selected_audio"]
    summary = read_json(OUT / "summary-with-m4.json")
    for group in summary["groups"]:
        for name, entry in group["dimensions"].items():
            assert entry["applicable"] == sum(entry[k] for k in ("present", "partial", "missing", "unknown")), (group["channel"], name)
            if not entry["applicable"]:
                assert entry["coverage_present_only"] is None
    print(f"{len(detail)} units and {resolved} handoff references resolved; "
          f"{matched} M4 asset rows matched by pointer and locator; status sums reproduced")


def digest_text(text):
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()


if __name__ == "__main__":
    main()
