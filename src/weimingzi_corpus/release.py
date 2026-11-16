#!/usr/bin/env python3
"""Derive the release view: one head transcript per item, confirmations applied.

The release view is a projection, never a second source. `selections/release.json`
holds only pointers (item -> head edited transcript, applied confirmations,
excluded paragraphs); the paragraph rows are rebuilt from `data/` on every export.

Exit codes: 0 clean, 1 validation errors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from .records import canonical_json, iter_records, json_sha256, read_json

SCHEMA_VERSION = 2
POLICY_VERSION = "release-1"
ROW_SCHEMA_VERSION = 1
SELECTION_PATH = "selections/release.json"
POLICIES = ("clean", "full")
DEFAULT_POLICY = "clean"
REVIEW_BASIS_CLEAN = "model_flagged_clean"
REVIEW_BASIS_CONFIRMED = "human_confirmed_local"
REVIEW_BASIS_FLAGGED = "model_flagged_with_notes"

ERROR_CODES = (
    "HEAD_NOT_UNIQUE",
    "HEAD_MISSING",
    "CONFIRMATION_ORPHAN",
    "CONFIRMATION_NOT_APPLIED",
    "DUPLICATE_ITEM_EDITED",
    "SUPERSEDED_CONFLICT",
)
WARNING_CODES = ("RELEASE_STALE",)


def _error(code, detail, **where):
    row = {"code": code, "detail": detail}
    row.update({key: value for key, value in where.items() if value is not None})
    return row


def load_edited(root: Path) -> dict:
    return {row["id"]: row for row, _ in iter_records(root, "edited_transcripts")}


def load_confirmations(root: Path) -> dict:
    return {row["id"]: row for row, _ in iter_records(root, "confirmations")}


def load_items(root: Path) -> dict:
    return {row["id"]: row for row, _ in iter_records(root, "items")}


def read_selection(root: Path) -> dict:
    path = root / SELECTION_PATH
    if not path.is_file():
        return {"schema_version": SCHEMA_VERSION, "policy_version": POLICY_VERSION, "items": []}
    selection = read_json(path)
    if selection.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"{SELECTION_PATH}: requires schema_version={SCHEMA_VERSION}")
    if not isinstance(selection.get("items"), list):
        raise ValueError(f"{SELECTION_PATH}: items must be an array")
    return selection


def group_edited(edited: dict) -> dict:
    groups = defaultdict(list)
    for record_id, row in edited.items():
        groups[row["item_id"]].append(record_id)
    return {item: sorted(ids) for item, ids in groups.items()}


def select_heads(groups: dict, selection: dict) -> tuple[dict, list, dict]:
    """Return (heads item->edited_id, errors, entries item->entry)."""
    errors = []
    entries = {}
    for entry in selection.get("items", []):
        item = entry.get("item_id")
        if item in entries:
            errors.append(_error("DUPLICATE_ITEM_EDITED", "item listed twice in release.json", item_id=item))
            continue
        entries[item] = entry
    heads = {}
    for item, ids in sorted(groups.items()):
        entry = entries.get(item)
        if entry is None:
            if len(ids) == 1:
                heads[item] = ids[0]
            else:
                errors.append(
                    _error(
                        "HEAD_NOT_UNIQUE",
                        f"{len(ids)} edited transcripts and no release pointer",
                        item_id=item,
                    )
                )
            continue
        head = entry.get("head_edited_id")
        if head not in ids:
            errors.append(
                _error("HEAD_MISSING", "head_edited_id is not an edited transcript of this item", item_id=item)
            )
            continue
        heads[item] = head
    for item in sorted(entries):
        if item not in groups:
            errors.append(_error("HEAD_MISSING", "release entry names an item with no edited transcript", item_id=item))
    used = defaultdict(list)
    for item, head in heads.items():
        used[head].append(item)
    for head, owners in used.items():
        if len(owners) > 1:
            errors.append(
                _error("DUPLICATE_ITEM_EDITED", f"head {head} claimed by {len(owners)} items", item_id=owners[0])
            )
    return heads, errors, entries


def derive_heads(groups: dict, edited: dict) -> tuple[dict, list]:
    """Head rule: the version that carries metadata.revision_id and is not cited by another version's derived_from_id."""
    heads = {}
    errors = []
    for item, ids in sorted(groups.items()):
        if len(ids) == 1:
            heads[item] = ids[0]
            continue
        pointed = {edited[other].get("derived_from_id") for other in ids}
        candidates = [
            record_id
            for record_id in ids
            if (edited[record_id].get("metadata") or {}).get("revision_id") and record_id not in pointed
        ]
        if len(candidates) == 1:
            heads[item] = candidates[0]
        else:
            errors.append(
                _error(
                    "HEAD_NOT_UNIQUE",
                    f"{len(candidates)} head candidates among {len(ids)} edited transcripts",
                    item_id=item,
                )
            )
    return heads, errors


def superseded_conflicts(groups: dict, heads: dict, edited: dict) -> list:
    errors = []
    for item, head in sorted(heads.items()):
        for other in groups[item]:
            if other == head:
                continue
            pointer = edited[other].get("superseded_by")
            if pointer is not None and pointer != head:
                errors.append(
                    _error(
                        "SUPERSEDED_CONFLICT",
                        f"superseded_by={pointer} but head is {head}",
                        item_id=item,
                        edited_id=other,
                    )
                )
    for record_id, row in sorted(edited.items()):
        pointer = row.get("superseded_by")
        if pointer is None:
            continue
        if pointer not in edited:
            errors.append(_error("SUPERSEDED_CONFLICT", f"superseded_by {pointer} does not exist", edited_id=record_id))
        elif edited[pointer]["item_id"] != row["item_id"]:
            errors.append(
                _error("SUPERSEDED_CONFLICT", "superseded_by belongs to a different item", edited_id=record_id)
            )
    return errors


def locate(record: dict, confirmation: dict) -> dict:
    """Locate the paragraph a confirmation applies to inside one edited transcript."""
    anchor = confirmation["anchor"]
    original = anchor["original_text"]
    corrected = confirmation["corrected_text"]
    paragraphs = record["paragraphs"]
    if original == corrected:
        hits = [p["index"] for p in paragraphs if original in p["text"]]
        return {"state": "no_change" if hits else "orphan", "paragraph_index": hits[0] if hits else None, "occurrences": len(hits)}
    hits = [p["index"] for p in paragraphs if original in p["text"]]
    if len(hits) == 1:
        return {"state": "apply", "paragraph_index": hits[0], "occurrences": 1}
    if len(hits) > 1:
        preferred = anchor.get("paragraph_index")
        if preferred in hits:
            return {"state": "apply", "paragraph_index": preferred, "occurrences": len(hits)}
        return {"state": "ambiguous", "paragraph_index": None, "occurrences": len(hits)}
    already = [p["index"] for p in paragraphs if corrected in p["text"]]
    if len(already) == 1:
        return {"state": "already_applied", "paragraph_index": already[0], "occurrences": 1}
    if len(already) > 1:
        preferred = anchor.get("paragraph_index")
        if preferred in already:
            return {"state": "already_applied", "paragraph_index": preferred, "occurrences": len(already)}
        return {"state": "ambiguous", "paragraph_index": None, "occurrences": len(already)}
    return {"state": "orphan", "paragraph_index": None, "occurrences": 0}


def plan_item(item: str, head: str, entry: dict, record: dict, confirmations: dict) -> tuple[list, list]:
    """Return (errors, applied list of (confirmation_id, paragraph_index, state))."""
    errors = []
    applied_ids = entry.get("applied_confirmation_ids") or []
    if not isinstance(applied_ids, list):
        errors.append(_error("CONFIRMATION_ORPHAN", "applied_confirmation_ids must be an array", item_id=item))
        applied_ids = []
    owned = sorted(cid for cid, row in confirmations.items() if row["item_id"] == item)
    for cid in applied_ids:
        if cid not in confirmations:
            errors.append(_error("CONFIRMATION_ORPHAN", "confirmation id does not exist", item_id=item, confirmation_id=cid))
    for cid in owned:
        if cid not in applied_ids:
            errors.append(
                _error(
                    "CONFIRMATION_ORPHAN",
                    "confirmation exists for this item but is not listed in release.json",
                    item_id=item,
                    confirmation_id=cid,
                )
            )
    applied = []
    for cid in applied_ids:
        row = confirmations.get(cid)
        if row is None or row["item_id"] != item:
            continue
        if head not in row.get("edited_transcript_ids", []):
            errors.append(
                _error("CONFIRMATION_ORPHAN", "head transcript is not listed on the confirmation", item_id=item, edited_id=head, confirmation_id=cid)
            )
            continue
        place = locate(record, row)
        if place["state"] in ("orphan", "ambiguous"):
            errors.append(
                _error(
                    "CONFIRMATION_NOT_APPLIED",
                    f"anchor not located uniquely (state={place['state']}, occurrences={place['occurrences']})",
                    item_id=item,
                    edited_id=head,
                    confirmation_id=cid,
                )
            )
            continue
        applied.append({"confirmation_id": cid, "paragraph_index": place["paragraph_index"], "state": place["state"]})
    return errors, applied


def apply_text(paragraphs: list, confirmations: dict, applied: list) -> dict:
    """Apply 1-based/0-indexed paragraph replacements; return index -> new text."""
    texts = {p["index"]: p["text"] for p in paragraphs}
    for step in applied:
        cid = step["confirmation_id"]
        row = confirmations[cid]
        index = step["paragraph_index"]
        original, corrected = row["anchor"]["original_text"], row["corrected_text"]
        if index is None or original == corrected:
            continue
        current = texts.get(index, "")
        if original in current:
            texts[index] = current.replace(original, corrected)
    return texts


def to_ms(value, unit) -> int:
    if unit == "s":
        return value * 1000
    return value


def build_release(root: Path, selection: dict, policy: str = "clean") -> dict:
    """Project the release view.

    policy="clean" keeps only paragraphs without review issues plus paragraphs a
    confirmation settles; policy="full" keeps every head paragraph and marks the
    flagged ones instead of dropping them.
    """
    if policy not in POLICIES:
        raise ValueError(f"unknown release policy: {policy}")
    edited = load_edited(root)
    confirmations = load_confirmations(root)
    items = load_items(root)
    groups = group_edited(edited)
    heads, errors, entries = select_heads(groups, selection)
    errors.extend(superseded_conflicts(groups, heads, edited))

    rows = []
    applied_total = 0
    excluded_total = 0
    dropped_total = 0
    confirmed_paragraphs = 0
    transcripts_included = 0
    for item in sorted(heads):
        head = heads[item]
        record = edited[head]
        entry = entries.get(item, {})
        item_errors, applied = plan_item(item, head, entry, record, confirmations)
        errors.extend(item_errors)
        if item_errors:
            continue
        applied_total += len(applied)
        excluded = set(entry.get("excluded_paragraphs") or [])
        settled = {step["paragraph_index"] for step in applied if step["paragraph_index"] is not None}
        texts = apply_text(record["paragraphs"], confirmations, applied)
        cited = [step["confirmation_id"] for step in applied]
        item_row = items.get(item, {})
        urls = item_row.get("urls") or []
        source_url = urls[0] if urls and isinstance(urls[0], str) else None
        kept_in_item = 0
        for paragraph in record["paragraphs"]:
            index = paragraph["index"]
            if index in excluded:
                excluded_total += 1
                continue
            issues = paragraph.get("issues") or []
            is_settled = index in settled
            if policy == "clean" and issues and not is_settled:
                dropped_total += 1
                continue
            if issues and is_settled:
                confirmed_paragraphs += 1
            kept_in_item += 1
            rows.append(
                {
                    "release_schema_version": ROW_SCHEMA_VERSION,
                    "policy_version": POLICY_VERSION,
                    "policy": policy,
                    "item_id": item,
                    "item_title": item_row.get("title"),
                    "source_url": source_url,
                    "edited_id": head,
                    "paragraph_id": f"{head}:p{index}",
                    "paragraph_index": index,
                    "time_unit": "ms",
                    "start_ms": to_ms(paragraph.get("start"), record.get("time_unit")),
                    "end_ms": to_ms(paragraph.get("end"), record.get("time_unit")),
                    "text": texts[index],
                    "issue_state": "clean" if not issues else ("confirmed" if is_settled else "flagged"),
                    "issue_count": len(issues),
                    "applied_confirmation_ids": cited,
                    "review_basis": (
                        REVIEW_BASIS_CLEAN
                        if not issues
                        else (REVIEW_BASIS_CONFIRMED if is_settled else REVIEW_BASIS_FLAGGED)
                    ),
                }
            )
        if kept_in_item:
            transcripts_included += 1

    counts = {
        "items": len(heads),
        "transcripts_included": transcripts_included,
        "multi_version_items": sum(1 for ids in groups.values() if len(ids) > 1),
        "edited_transcripts": len(edited),
        "confirmations": len(confirmations),
        "paragraphs": len(rows),
        "confirmed_paragraphs": confirmed_paragraphs,
        "dropped_paragraphs": dropped_total,
        "excluded_paragraphs": excluded_total,
        "applied_confirmations": applied_total,
    }
    warnings = []
    return {"rows": rows, "errors": errors, "warnings": warnings, "counts": counts, "policy": policy}


def git_head(root: Path) -> str | None:
    import subprocess

    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def write_release(root: Path, output: Path, built: dict, selection: dict) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with output.open("w", encoding="utf-8", newline="\n") as stream:
        for row in built["rows"]:
            line = canonical_json(row) + "\n"
            stream.write(line)
            digest.update(line.encode("utf-8"))
    manifest = {
        "schema_version": 1,
        "policy_version": POLICY_VERSION,
        "policy": built.get("policy", DEFAULT_POLICY),
        "generated_from_commit": selection.get("generated_from_commit"),
        "selection_sha256": json_sha256(selection),
        "release_paragraphs_file": output.name,
        "release_paragraphs_sha256": digest.hexdigest(),
        "counts": built["counts"],
        "review_basis": {
            "clean": REVIEW_BASIS_CLEAN,
            "confirmed": REVIEW_BASIS_CONFIRMED,
            "flagged": REVIEW_BASIS_FLAGGED,
            "note": "clean means the model reported no review issue; confirmed means a recorded confirmation settled that paragraph. Neither is human review of the whole transcript; no record in data/ claims is_fully_human_reviewed=true.",
        },
    }
    manifest_path = output.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


def build_selection(root: Path, edited: dict, confirmations: dict, groups: dict, heads: dict) -> dict:
    entries = []
    owned = defaultdict(list)
    for cid, row in confirmations.items():
        owned[row["item_id"]].append(cid)
    for item in sorted(heads):
        head = heads[item]
        record = edited[head]
        applied = []
        for cid in sorted(owned.get(item, [])):
            row = confirmations[cid]
            if head not in row.get("edited_transcript_ids", []):
                continue
            if locate(record, row)["state"] in ("apply", "already_applied", "no_change"):
                applied.append(cid)
        entries.append(
            {
                "item_id": item,
                "head_edited_id": head,
                "applied_confirmation_ids": applied,
                "excluded_paragraphs": [],
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "policy": DEFAULT_POLICY,
        "generated_from_commit": git_head(root),
        "items": entries,
    }


def validate_release(root: Path) -> dict:
    """Validate the release pointer file and its projection; safe when no pointer exists yet."""
    path = root / SELECTION_PATH
    if not path.is_file():
        return {"skipped": True, "errors": [], "warnings": [], "counts": {}}
    built = build_release(root, read_selection(root), policy=DEFAULT_POLICY)
    return {
        "skipped": False,
        "errors": built["errors"],
        "warnings": built["warnings"],
        "counts": built["counts"],
    }


def summarise(built: dict) -> dict:
    seen = {}
    for row in built["errors"]:
        seen[row["code"]] = seen.get(row["code"], 0) + 1
    return {
        "ok": not built["errors"],
        "counts": built["counts"],
        "errors": built["errors"][:50],
        "error_counts": dict(sorted(seen.items())),
        "warnings": built["warnings"],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="validate release.json against data/")
    export = commands.add_parser("export", help="write paragraph-level release rows and a manifest")
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--policy", choices=POLICIES, default=DEFAULT_POLICY)
    init = commands.add_parser("init-selection", help="write selections/release.json for every item")
    init.add_argument("--output", type=Path)
    init.add_argument("--force", action="store_true", help="overwrite an existing selection")
    args = parser.parse_args(argv)
    root = args.root.resolve()

    selection = read_selection(root)
    if args.command == "init-selection":
        destination = (args.output or (root / SELECTION_PATH)).resolve()
        if destination.exists() and not args.force:
            raise SystemExit(f"refusing to overwrite existing selection: {destination}")
        edited = load_edited(root)
        confirmations = load_confirmations(root)
        groups = group_edited(edited)
        heads, errors = derive_heads(groups, edited)
        if errors:
            print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
            return 1
        built_selection = build_selection(root, edited, confirmations, groups, heads)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(built_selection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        print(json.dumps({"ok": True, "selection": str(destination), "entries": len(built_selection["items"])}, ensure_ascii=False))
        return 0

    policy = getattr(args, "policy", DEFAULT_POLICY)
    built = build_release(root, selection, policy=policy)
    if args.command == "check":
        print(json.dumps(summarise(built), ensure_ascii=False, indent=2))
        return 0 if not built["errors"] else 1
    if built["errors"]:
        print(json.dumps(summarise(built), ensure_ascii=False, indent=2))
        return 1
    manifest = write_release(root, args.output.resolve(), built, selection)
    print(json.dumps({"ok": True, "manifest": manifest}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
