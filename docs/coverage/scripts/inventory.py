#!/usr/bin/env python3
"""Build or independently recount the SOP M1/M2 inventory for this candidate."""
import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import sys

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
START = OUT.parent
ROOT = START / "candidate"
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]
from weimingzi_corpus.coverage import text_status
from weimingzi_corpus.records import block_text, input_ids, iter_records
import restore_audio

METHOD = "sop-m1-m2-inventory/1.1"
DIMENSIONS = ("metadata", "base_transcript", "edited_transcript", "media", "human_review")
STATES = ("present", "partial", "missing", "unknown", "not_applicable")
VIDEO = {"video", "video_part"}
COLLECTIONS = {"video_collection", "video_series", "article_collection"}
AV = {"video_part", "audio_recording"}
TEXT = {"post", "article"}
DOC_KINDS = {"transcript", "edited_transcript", "post", "article"}
SOURCE_FIELDS = {
    "bilibili_bvid": "bilibili", "bilibili_part": "bilibili",
    "bilibili_dynamic": "bilibili", "bilibili_cvid": "bilibili", "bilibili_uid": "bilibili",
    "bilibili_season": "bilibili", "bilibili_series": "bilibili", "bilibili_article_list": "bilibili",
    "youtube_video": "youtube", "youtube_part": "youtube", "audio_sha256": "user_supplied_audio",
}
TIME_FIELDS = {
    "video": ("published_at_unix_seconds", "published_at", "pubdate", "created", "ctime", "date", "observed_at"),
    "video_part": ("published_at_unix_seconds", "published_at", "pubdate", "date_as_recorded"),
    "post": ("published_at_unix_seconds", "observed_at"),
    "article": ("publish_time", "ctime", "observed_at", "observed_at_unix_seconds"),
    "audio_recording": (),
    "video_collection": ("ptime",), "video_series": ("ctime", "mtime", "last_update_ts"),
    "article_collection": ("ctime", "publish_time", "update_time"), "person": ("observed_at_unix_seconds",),
}
SOURCE_BOUNDS = {
    "bilibili": "现存 BV／分 P、动态、专栏、集合与来源人物。未核实账号或平台完整列表、已删除或不可见内容、未识别分 P、列举时间外活跃记录与当前源站状态。",
    "youtube": "现存 YouTube 视频和分 P。B 站参照仅作跨源证据。未核实完整频道、转载名单、未识别分 P 和源站状态。",
    "user_supplied_audio": "现存用户提供独立录音，以资产 SHA-256 为入口。未核实供应清单、原录制或首发时间、未提交文件。",
}
RELATION_LAYERS = {
    "references": "cross_source", "references_video": "cross_source",
    "audible_rerecording_of": "cross_source",
    "chapter_supplement_not_audio_identity": "chapter_supplement",
    "has_full_text": "linked_article_body",
}


def dump(name, payload):
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def write_lines(name, rows):
    with (OUT / name).open("w", encoding="utf-8", newline="\n") as file:
        for row in rows:
            print(json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False), file=file)


def read_lines(name):
    with (OUT / name).open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def read_json(path):
    # PowerShell Out-File and native Python both appear in the surrounding SOP evidence.
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return json.loads(data.decode("utf-16"))
    return json.loads(data.decode("utf-8-sig"))


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_candidate(source_head, started_at):
    fix = read_json(START / "candidate-fixity.json")
    chain = read_json(START / "candidate-chain.json")
    manifest = read_json(ROOT / fix["manifest"])
    selector = read_json(ROOT / "preservation/current-baseline.json")
    if fix["ok"] is not True or chain["ok"] is not True:
        raise ValueError("Both candidate receipts must have passed")
    # The preserved manifest self-digest has a documented canonical-JSON boundary.
    if fix["manifest_sha256"] != manifest["manifest_sha256"] or fix["manifest_sha256"] != selector["manifest_sha256"]:
        raise ValueError("Candidate fixity receipt does not match current baseline")
    return {
        "method": METHOD, "started_at": started_at,
        "source_git_head_at_snapshot": source_head,
        "candidate_version_type": "dirty_worktree_snapshot_without_own_git_checkout",
        "candidate_root": "../candidate",
        "candidate_fixity_receipt": {"path": "../candidate-fixity.json", **fix},
        "candidate_event_chain_receipt": {"path": "../candidate-chain.json", **chain},
        "candidate_documents": {name: digest(ROOT / name) for name in (
            "AGENTS.md", "docs/SOP.md", "docs/PDR.md", "docs/SCHEMA.md", "docs/DATA-CARD.md",
            "src/weimingzi_corpus/records.py", "src/weimingzi_corpus/coverage.py", "tools/restore_audio.py",
            "tools/audit_audio_restore.py", "data/items.jsonl", "data/assets.jsonl", "data/annotations.jsonl",
            "data/schema.json", "uv.lock",
        )},
        "inventory_generator_sha256": digest(Path(__file__)),
        "runtime": {"python": platform.python_version(), "os": platform.platform()},
    }


def evidence(row, path, line=None, **fields):
    return {"id": row["id"], "path": path, **({"line": line} if line else {}), **fields}


def native_rows(entity):
    for ordinal, (row, path) in enumerate(iter_records(ROOT, entity), 1):
        # The native JSONL files for this candidate have one JSON object on each line.
        yield row, path.relative_to(ROOT).as_posix(), None if entity == "documents" else ordinal


def field_state(row, field):
    if field not in row:
        return {"present": False}
    return {"present": True, "value": row[field]}


def source_info(item):
    identifiers = item.get("identifiers", {})
    channels = {SOURCE_FIELDS[key] for key in identifiers if key in SOURCE_FIELDS and identifiers[key]}
    if len(channels) != 1:
        raise ValueError(f"Unclassified or mixed source {item['id']}: {channels}")
    return next(iter(channels))


def record_times(item):
    metadata = item.get("metadata", {})
    return {key: metadata[key] for key in TIME_FIELDS[item["kind"]] if key in metadata}


def norm_time(field, value):
    if not isinstance(value, (str, int, float)) or type(value) is bool:
        return None
    if field in {"date", "date_as_recorded"} and isinstance(value, str):
        # Only a full year-month-day value or the recorded visibility prefix establishes the year.
        value = value.removeprefix("仅自己可见 · ")
    try:
        if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return date.fromisoformat(value).isoformat()
        if isinstance(value, (int, float)) or re.fullmatch(r"\d+", value):
            # Zero publication seconds is a platform sentinel. Keep raw, exclude from date bounds.
            return datetime.fromtimestamp(float(value), timezone.utc).isoformat() if float(value) > 0 else None
        parsed = datetime.fromisoformat(value)
        return parsed.astimezone(timezone.utc).isoformat() if parsed.tzinfo else parsed.isoformat()
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def document_info(row, path):
    kind = row["kind"]
    owners = input_ids(row, "item")
    if len(owners) != 1 or kind not in DOC_KINDS:
        raise ValueError(f"Invalid document owner or kind {row['id']}")
    quality = row.get("quality", {})
    info = evidence(row, path, kind=kind, ownership_field="inputs[role=item]",
                    input_transcript_ids=input_ids(row, "transcript"),
                    input_audio_ids=input_ids(row, "audio"),
                    full_review=field_state(quality, "is_fully_human_reviewed"),
                    requires_review=field_state(quality, "requires_review"))
    if kind != "post":
        info["text_status"] = text_status(row["text"])
        info["text_char_count"] = len(row["text"])
        info["is_complete"] = field_state(row, "is_complete")
        info["block_count"] = len(row.get("blocks", []))
        if "content_sha256" in row:
            info["content_sha256"] = row["content_sha256"]
        if "time_unit" in row:
            info["time_unit"] = row["time_unit"]
        for field in ("method", "model"):
            if field in row:
                info[field] = row[field]
        for field in ("status", "content_assessment", "audio_assessment", "has_expand_prompt"):
            if field in quality:
                info[field] = quality[field]
        intervals = quality.get("recognition_issue_intervals", [])
        info["recognition_intervals_explicitly_without_text"] = [
            index for index, interval in enumerate(intervals) if interval.get("transcript_text_available") is False
        ]
    else:
        content = row["content"]
        dynamic = content.get("modules", {}).get("module_dynamic", {})
        major = dynamic.get("major") or {}
        opus = major.get("opus") or {}
        fulltext = content.get("_archive_fulltext") or {}
        text_fields = []
        own_text_fields = (
            ("content.modules.module_dynamic.desc", dynamic.get("desc")),
            ("content.modules.module_dynamic.major.opus.summary", opus.get("summary")),
        )
        for field, value in own_text_fields:
            if not isinstance(value, dict) or not any(value.get(key) for key in ("text", "rich_text_nodes", "paragraphs")):
                continue
            article_preview = content.get("type") == "DYNAMIC_TYPE_ARTICLE" and field.endswith(".opus.summary")
            text_fields.append({"field": field, "role": "article_preview" if article_preview else "own_text",
                                "has_more": field_state(value, "has_more")})
        info.update(post_type=content.get("type"), post_text_evidence=text_fields,
                    post_reshare_present=bool(content.get("orig")), post_major_type=major.get("type"),
                    post_linked_fulltext_present=bool(fulltext.get("text")),
                    post_linked_fulltext_evidence={f"content._archive_fulltext.{key}": fulltext[key]
                        for key in ("article_id", "dynamic_id", "source_sha256", "source_observed_at", "source_url", "source_table", "backend") if key in fulltext},
                    input_article_item_ids=input_ids(row, "article_item"))
    info["artifact_input_ids"] = {role: input_ids(row, role) for role in ("html", "review_document_markdown") if input_ids(row, role)}
    return owners[0], info


def status(value, reason):
    return {"applicable": value != "not_applicable", "status": value, "basis": reason}


def metadata_status(item, channel, children, items):
    reasons = []
    if not item.get("identifiers") or not item.get("title", "").strip():
        reasons.append("missing_source_identity_or_title")
    if item["kind"] in VIDEO | TEXT | {"person"} and not item.get("urls"):
        reasons.append("missing_platform_entry_url")
    if item["kind"] in COLLECTIONS and "members" not in item:
        reasons.append("missing_member_list_field")
    if item["kind"] == "video_part":
        parent = items.get(item.get("parent_id"))
        if not parent or parent["kind"] != "video" or source_info(parent) != channel or not item.get("part_number"):
            reasons.append("missing_or_invalid_video_parent_or_part_number")
    return status("partial", reasons) if reasons else status("present", "native_item_identity_and_kind_specific_entry")


def manuscript_status(docs, kind, applicable, na_reason):
    if not applicable:
        return status("not_applicable", na_reason)
    if not docs:
        return status("missing", "no_native_direct_document_with_kind_and_item_role")
    if kind == "transcript":
        adequate = any(doc["text_status"] == "text_present_unverified" and not doc["recognition_intervals_explicitly_without_text"] for doc in docs)
        return status("present", "at_least_one_direct_non_filler_text_without_explicit_no_text_intervals") if adequate else status("partial", "direct_transcript_record_exists_but_empty_filler_or_explicitly_untranscribed_interval")
    adequate = any(doc["text_status"] == "text_present_unverified" and doc["is_complete"].get("value") is True for doc in docs)
    return status("present", "at_least_one_direct_non_filler_edited_result_marked_complete") if adequate else status("partial", "direct_edited_result_exists_but_no_complete_non_filler_result")


def review_status(docs, annotations, applicable, na_reason):
    if not applicable:
        return status("not_applicable", na_reason)
    accepted_local = any(a["native_status"] in {"user_confirmed", "human_confirmed"} for a in annotations)
    values = [doc["full_review"].get("value") for doc in docs]
    if any(value is True for value in values):
        return status("present", "at_least_one_direct_document_explicitly_full_review")
    if accepted_local:
        return status("partial", "confirmed_local_annotation_without_any_explicit_full_review")
    if values and all(value is False for value in values):
        return status("missing", "all_direct_document_full_review_flags_explicitly_false_no_local_evidence")
    return status("unknown", "no_direct_document_or_at_least_one_full_review_flag_null_or_absent_no_local_evidence")


def media_status(assets, applicable, na_reason):
    if not applicable:
        return status("not_applicable", na_reason)
    if any(a["m4"]["join_key"] for a in assets):
        return status("present", "native_audio_archive_locator_accepted_by_restore_audio_list")
    if assets and all(a["availability"] == "unavailable" for a in assets):
        return status("missing", "native_audio_asset_explicitly_has_no_download_locator")
    if assets:
        return status("partial", "native_audio_asset_exists_but_no_accepted_restore_locator")
    return status("missing", "no_direct_native_audio_asset_in_candidate")


def supplement_status(item, docs):
    kind = item["kind"]
    if kind == "article":
        if not docs:
            return status("missing", "no_native_article_document")
        if any(d["text_status"] == "text_present_unverified" and d.get("has_expand_prompt") is not True for d in docs):
            return status("present", "native_article_text_without_observed_expand_prompt")
        return status("partial", "article_document_with_empty_or_expansion_indicated_text")
    if kind == "post":
        if not docs:
            return status("missing", "no_native_post_document")
        entries = [entry for doc in docs for entry in doc["post_text_evidence"]]
        own = [entry for entry in entries if entry["role"] == "own_text"]
        if any(entry["has_more"].get("value") is False for entry in own):
            return status("present", "native_post_own_rich_text_observed_with_no_more_flag")
        if own:
            return status("partial", "native_post_own_text_observed_completeness_not_established")
        if entries:
            return status("partial", "native_post_has_linked_article_preview_linked_fulltext_counted_separately")
        return status("unknown", "native_post_object_saved_but_own_text_presence_not_established")
    return None


def group_restore_audio():
    # Use the same preflight and chosen locator as the M4 restore/audit implementation.
    restore_audio.ROOT = ROOT
    groups = restore_audio.load_audio_archive_groups()
    return {
        (file["local_path"], file["sha256"]): (key, group["archive"], file)
        for key, group in groups.items() for file in group["files"]
    }


def gather():
    items, item_ev, children = {}, {}, defaultdict(list)
    for row, path, line in native_rows("items"):
        item_id = row["id"]
        if item_id in items:
            raise ValueError(f"Duplicate item {item_id}")
        items[item_id] = row
        item_ev[item_id] = evidence(row, path, line)
        if row.get("parent_id"):
            children[row["parent_id"]].append(item_id)
    valid_locs = group_restore_audio()
    audio, artifacts, audio_groups, media_join = defaultdict(list), {}, defaultdict(set), []
    for row, path, line in native_rows("assets"):
        kind = row["kind"]
        if kind != "audio":
            assets_fields = {field: row[field] for field in ("name", "sha256", "size_bytes", "local_path", "url") if field in row}
            artifacts[row["id"]] = evidence(row, path, line, kind=kind, **assets_fields)
            continue
        owners = input_ids(row, "item")
        provider = valid_locs.get((row.get("local_path"), row["sha256"]))
        join = None
        if provider:
            archive_key, archive, restored = provider
            join = {"archive_key": archive_key, "member_path": restored["member_path"],
                    "local_path": restored["local_path"], "expected_sha256": row["sha256"],
                    "expected_size_bytes": row["size_bytes"], "archive_asset_id": archive["id"],
                    "archive_sha256": archive["sha256"], "archive_size_bytes": archive["size_bytes"],
                    "archive_url": archive["url"]}
        record = evidence(row, path, line, availability=row["availability"], sha256=row["sha256"],
                          ownership_field="inputs[role=item]", downloads=row.get("downloads", []),
                          m4={"status": "not_run", "report_path": None, "report_asset_pointer": None, "join_key": join})
        if row["availability"] == "unavailable":
            record["unavailable_evidence_fields"] = [
                f"metadata.{key}" for key in ("availability_note", "external_storage_key") if key in row.get("metadata", {})
            ]
        media_join.append({**record, "owner_item_ids": owners})
        for owner in owners:
            audio[owner].append(record)
            audio_groups[row["sha256"]].add(owner)
    for item_id, item in items.items():
        for sha in item.get("identifiers", {}).get("audio_sha256", []):
            audio_groups[sha].add(item_id)
    if sum(bool(asset["m4"]["join_key"]) for asset in media_join) != len(valid_locs):
        raise ValueError("Inventory restore join is inconsistent with native restore preflight")
    docs = defaultdict(list)
    for row, path, _ in native_rows("documents"):
        owner, parsed = document_info(row, path)
        if owner not in items:
            raise ValueError(f"Missing direct document owner {owner}")
        docs[owner].append(parsed)
    annotations = defaultdict(list)
    for row, path, line in native_rows("annotations"):
        owners = [ref["target_id"] for ref in row["targets"] if ref["role"] == "item"]
        if len(owners) != 1 or owners[0] not in items:
            raise ValueError(f"Invalid annotation item target for {row['id']}")
        annotations[owners[0]].append(evidence(
            row, path, line, kind=row["kind"], native_status=row["status"],
            scope=row.get("scope", "segment_attribution"), targets=row["targets"],
            anchor_fields=[f"anchor.{key}" for key in row["anchor"]],
        ))
    relations = defaultdict(list)
    for item_id, item in items.items():
        for index, relation in enumerate(item.get("relations", [])):
            if relation["kind"] in RELATION_LAYERS:
                target = relation["target_item_id"]
                ref = {"item_id": item_id, "target_item_id": target, "kind": relation["kind"],
                       "field": f"relations[{index}]", "item_record": item_ev[item_id]}
                if relation.get("evidence_path"):
                    ref["evidence_path"] = relation["evidence_path"]
                relations[item_id].append((target, ref))
                if relation["kind"] != "has_full_text":
                    relations[target].append((item_id, ref))
    return items, item_ev, children, documents_for_rows(docs), audio, artifacts, audio_groups, media_join, annotations, relations


def documents_for_rows(docs):
    for group in docs.values():
        group.sort(key=lambda r: r["id"])
    return docs


def build_rows(inventory):
    items, item_ev, children, docs, audio, artifacts, audio_groups, _, annotations, relations = inventory
    for item_id in sorted(items):
        item = items[item_id]
        kind = item["kind"]
        channel = source_info(item)
        parent = item.get("parent_id")
        av_unit = kind in AV or (kind == "video" and not children[item_id])
        explicit_silent = "silent_audio_confirmed" in item.get("metadata", {}).get("audio_assessment", [])
        av_text = av_unit and not explicit_silent
        na_av = "video_parent_metadata_only_use_part_rows" if kind == "video" else "non_av_material"
        na_manuscript = "native_item_explicitly_confirms_no_speech" if explicit_silent else na_av
        na_review = "non_text_context" if kind in COLLECTIONS | {"person"} else na_manuscript
        directly = docs[item_id]
        base = [x for x in directly if x["kind"] == "transcript"]
        edited = [x for x in directly if x["kind"] == "edited_transcript"]
        ancillary = defaultdict(list)
        seen = set()
        for context in (item_id, parent):
            if not context:
                continue
            for far, ref in relations[context]:
                layer = RELATION_LAYERS[ref["kind"]]
                for target in [far, *children[far]]:
                    key = (layer, target, ref["item_id"], ref["field"])
                    if target == item_id or key in seen:
                        continue
                    seen.add(key)
                    ancillary[layer].append({"target_item_id": target, "relation": ref,
                                             "direct_document_ids_at_target": [d["id"] for d in docs[target]]})
        for sha in sorted({a["sha256"] for a in audio[item_id]} | set(item.get("identifiers", {}).get("audio_sha256", []))):
            for target in sorted(audio_groups[sha] - {item_id}):
                ancillary["same_audio"].append({"target_item_id": target, "sha256": sha,
                                               "direct_document_ids_at_target": [d["id"] for d in docs[target]]})
        dimensions = {
            "metadata": metadata_status(item, channel, children, items),
            "base_transcript": manuscript_status(base, "transcript", av_text, na_manuscript),
            "edited_transcript": manuscript_status(edited, "edited_transcript", av_text, na_manuscript),
            "media": media_status(audio[item_id], av_unit, na_av),
            "human_review": review_status(directly, annotations[item_id], av_text or kind in TEXT, na_review),
        }
        yield {
            "channel": channel, "kind": kind, "in_first_release_scope": kind != "person",
            "item": item_ev[item_id], "source_identifiers": item.get("identifiers", {}),
            "urls": item.get("urls", []), "part_number": item.get("part_number"), "parent_item_id": parent,
            "child_part_count": len(children[item_id]), "collection_member_count": len(item.get("members", [])),
            "metadata_fields": ["identifiers", "title", "urls", "metadata"] +
                (["parent_id", "part_number"] if kind == "video_part" else ["members"] if kind in COLLECTIONS else []),
            "native_time_fields": record_times(item),
            "silent_audio_confirmed": explicit_silent,
            "silence_evidence_fields": ["metadata.audio_assessment", "metadata.audio_assessment_evidence"] if explicit_silent else [],
            "dimensions": dimensions, "supplemental_body_observation": supplement_status(item, directly),
            "native_direct_documents": directly, "related_evidence_non_counting": dict(ancillary),
            "local_annotations": annotations[item_id], "direct_audio_assets": audio[item_id],
            "document_artifacts": [artifacts[asset_id] for doc in directly for ids in doc["artifact_input_ids"].values() for asset_id in ids],
        }


def ratio(numerator, denominator):
    return round(numerator / denominator, 8) if denominator else None


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["channel"], row["kind"])].append(row)
    groups[("all", "first_release_scope")] = [row for row in rows if row["in_first_release_scope"]]
    for channel in sorted({row["channel"] for row in rows}):
        groups[(channel, "first_release_scope")] = [row for row in rows if row["channel"] == channel and row["in_first_release_scope"]]
    summary = []
    for (channel, kind), members in sorted(groups.items()):
        entry = {"channel": channel, "kind": kind, "unit_count": len(members), "dimensions": {}}
        for dim in DIMENSIONS:
            count = Counter(row["dimensions"][dim]["status"] for row in members)
            for row in members:
                state = row["dimensions"][dim]
                if state["status"] not in STATES or state["applicable"] != (state["status"] != "not_applicable"):
                    raise ValueError(f"Invalid dimension status {row['item']['id']} {dim}")
            applicable = len(members) - count["not_applicable"]
            if applicable != sum(count[k] for k in STATES[:-1]):
                raise ValueError(f"Status sum mismatch {channel} {kind} {dim}")
            entry["dimensions"][dim] = {"applicable": applicable, **{k: count[k] for k in STATES},
                                        "coverage_present_only": ratio(count["present"], applicable)}
        candidate_media = [row for row in members if row["dimensions"]["media"]["applicable"]]
        audio = {a["id"]:a for row in candidate_media for a in row["direct_audio_assets"]}
        restorable = [a for a in audio.values() if a["m4"]["join_key"]]
        entry["audio"] = {
            "scope_unit_count": len(candidate_media), "distinct_direct_audio_assets": len(audio),
            "restorable_units": sum(any(a["m4"]["join_key"] for a in row["direct_audio_assets"]) for row in candidate_media),
            "restorable_assets": len(restorable),
            "restorable_archives": len({a["m4"]["join_key"]["archive_asset_id"] for a in restorable}),
            "current_m4_status": "not_run" if candidate_media else "not_applicable",
            "current_m4_passed_units": None,
            "current_m4_passed_assets": None,
        }
        entry["supplemental_body"] = dict(sorted(Counter(
            row["supplemental_body_observation"]["status"] for row in members if row["supplemental_body_observation"]
        ).items()))
        entry["supplemental_post_linked_article_fulltext_units"] = sum(
            any(d.get("post_linked_fulltext_present") for d in row["native_direct_documents"]) for row in members
        )
        summary.append(entry)
    return summary


def source_manifest(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["channel"], row["kind"])].append(row)
    manifest = []
    for (channel, kind), members in sorted(groups.items()):
        fields = {}
        for field in TIME_FIELDS[kind]:
            dated_rows = 0
            values = []
            for row in members:
                raw = row["native_time_fields"].get(field, [])
                parsed = [norm_time(field, val) for val in (raw if isinstance(raw, list) else [raw])]
                valid = [x for x in parsed if x]
                dated_rows += bool(valid)
                values.extend(valid)
            fields[f"metadata.{field}"] = {"dated_units": dated_rows, "unknown_units": len(members) - dated_rows,
                                          "earliest": min(values, default=None), "latest": max(values, default=None)}
        key_names = sorted({key for row in members for key in row["source_identifiers"]})
        entry_urls = sorted({url for row in members for url in row["urls"]})
        source_evidence = {"index": "data/items.jsonl", "identifier_fields": [f"identifiers.{key}" for key in key_names],
                           "entry_url_field": "urls", "example_entry_urls": entry_urls[:3],
                           "examples": [row["item"] for row in members[:3]],
                           "url_units": sum(bool(row["urls"]) for row in members)}
        if kind in COLLECTIONS:
            source_evidence["membership_field"] = "members[].item_id"
        if channel == "user_supplied_audio":
            source_evidence["additional_entry_fields"] = ["metadata.source_kind", "assets.sha256", "assets.inputs[role=item]"]
        manifest.append({"channel": channel, "kind": kind, "unit_count": len(members),
                         "in_first_release_scope": kind != "person", "source_evidence": source_evidence,
                         "time_field_statistics": fields, "unverified_range": SOURCE_BOUNDS[channel]})
    return manifest


def ordered_gaps(rows):
    for row in rows:
        if not row["in_first_release_scope"]:
            continue
        dims = row["dimensions"]
        for dim in DIMENSIONS:
            state = dims[dim]["status"]
            if state not in {"partial", "missing", "unknown"}:
                continue
            if dim == "metadata":
                priority, classification, owner = 1, "check_release_inventory_integrity", "maintainer"
            elif dim == "media":
                priority, classification, owner = 4, "disclose_and_follow_up_outside_current_audio_recovery_scope", "media_maintainer"
            elif dim in {"base_transcript", "edited_transcript"}:
                priority, classification, owner = (3 if dim == "base_transcript" else 5), "archive_backfill", "manuscript_maintainer"
            else:
                priority, classification, owner = 6, "verify_or_schedule_human_review", "review_owner_to_be_assigned"
            yield {"priority": priority, "classification": classification, "owner_role": owner,
                   "channel": row["channel"], "kind": row["kind"], "item_id": row["item"]["id"],
                   "item_path": row["item"]["path"], "item_line": row["item"]["line"],
                   "source_identifiers": row["source_identifiers"], "part_number": row["part_number"],
                   "dimension": dim, "state": state, "basis": dims[dim]["basis"],
                   "direct_document_ids": [d["id"] for d in row["native_direct_documents"]],
                   "audio_asset_ids": [a["id"] for a in row["direct_audio_assets"]],
                   "local_annotation_ids": [a["id"] for a in row["local_annotations"]]}
        locs = [a["id"] for a in row["direct_audio_assets"] if a["m4"]["join_key"]]
        if locs:
            yield {"priority": 2, "classification": "m4_release_gate_for_declared_restore_scope", "owner_role": "m4_reviewer",
                   "channel": row["channel"], "kind": row["kind"], "item_id": row["item"]["id"],
                   "item_path": row["item"]["path"], "item_line": row["item"]["line"],
                   "source_identifiers": row["source_identifiers"], "part_number": row["part_number"],
                   "dimension": "media_m4_backfill", "state": "not_run", "basis": "current_audit_receipt_pending",
                   "audio_asset_ids": locs}


def make_samples(rows):
    by_id = {row["item"]["id"]: row for row in rows}
    together = [row for row in rows if row["kind"] == "video_part" and
                "BV1CP4y1s7BM" in row["source_identifiers"].get("bilibili_bvid", [])]
    assert {row["part_number"] for row in together} == {1, 2}
    parts = sorted(together, key=lambda row: row["part_number"])
    owner = next(row for row in rows if row["kind"] == "video_part" and
                 any(a["m4"]["join_key"] for a in row["direct_audio_assets"]) and
                 any(d["kind"] == "transcript" for d in row["native_direct_documents"]) and
                 any(d["kind"] == "edited_transcript" for d in row["native_direct_documents"]))
    cases = [("linked_parts_and_silence", parts), ("part_with_direct_documents_and_restore_locator", [owner]),
             ("confirmed_local_annotation", [next(row for row in rows if row["local_annotations"])])]
    samples = []
    cases.extend([
        ("post_opus_own_rich_text", [next(row for row in rows if row["kind"] == "post" and any(
            entry["role"] == "own_text" and entry["field"].endswith(".opus.summary")
            for doc in row["native_direct_documents"] for entry in doc["post_text_evidence"]))]),
        ("post_linked_article_preview", [next(row for row in rows if row["kind"] == "post" and any(
            doc["post_linked_fulltext_present"] for doc in row["native_direct_documents"]))]),
    ])
    for label, case in cases:
        for row in case:
            readings = []
            for document in row["native_direct_documents"]:
                native = read_json(ROOT / document["path"])
                blocks = native.get("blocks", [])
                if not blocks:
                    continue
                block = blocks[0]
                exact = block_text(native, block)
                readings.append({"id": document["id"], "path": document["path"], "field": "blocks[0]",
                                 "selector": block.get("range", "literal"), "chars": len(exact),
                                 "sha256_utf8": hashlib.sha256(exact.encode()).hexdigest(),
                                 "start": block.get("start"), "end": block.get("end"), "time_unit": native.get("time_unit")})
            parent = by_id.get(row["parent_item_id"])
            samples.append({"case": label, "unit": row, "parent_item": parent["item"] if parent else None,
                            "body_block_readback": readings})
    return samples


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recount", action="store_true", help="Read only published detail, then compare to summary")
    parser.add_argument("--source-head")
    parser.add_argument("--uv-version")
    args = parser.parse_args()
    if args.recount:
        rows = read_lines("detail.jsonl")
        assert len({row["item"]["id"] for row in rows}) == len(rows)
        comparison = read_json(OUT / "summary.json")
        assert summarize(rows) == comparison["groups"]
        assert source_manifest(rows) == read_json(OUT / "sources.json")["groups"]
        assert list(sorted(ordered_gaps(rows), key=gap_sort_key)) == read_lines("gaps.jsonl")
        print(f"{len(rows)} units: summary, source windows and gaps reproduced from detail")
        return
    if not args.source_head or not re.fullmatch(r"[0-9a-f]{40}", args.source_head) or not args.uv_version:
        parser.error("Provide --source-head (original workspace HEAD) and --uv-version")
    started_at = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
    run = load_candidate(args.source_head, started_at)
    run["runtime"]["uv"] = args.uv_version
    inventory = gather()
    rows = list(build_rows(inventory))
    groups = summarize(rows)
    gaps = sorted(ordered_gaps(rows), key=gap_sort_key)
    samples = make_samples(rows)
    write_lines("detail.jsonl", rows)
    write_lines("gaps.jsonl", gaps)
    write_lines("media-m4-join.jsonl", sorted(inventory[7], key=lambda row: row["id"]))
    dump("sources.json", {"method": METHOD, "inventory_on": started_at[:10], "inventory_timezone": "Asia/Hong_Kong",
                          "time_policy": "Field-specific recorded windows, aware timestamps normalized to UTC, date-only strings unchanged, zero Unix timestamp excluded, bounds not source enumeration.",
                          "groups": source_manifest(rows)})
    dump("summary.json", {"method": METHOD, "scope_note": "Identified in candidate archive only. Person is a context row outside first-release totals.", "groups": groups})
    dump("samples.json", {"method": METHOD, "samples": samples})
    run["completed_at"] = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
    run["reports_sha256"] = {name: digest(OUT / name) for name in ("detail.jsonl", "gaps.jsonl", "media-m4-join.jsonl", "sources.json", "summary.json", "samples.json")}
    run["counts"] = {"detail": len(rows), "gap_rows_including_pending_m4": len(gaps), "m4_asset_rows": len(inventory[7])}
    dump("run.json", run)
    print(json.dumps(next(g for g in groups if g["channel"] == "all"), ensure_ascii=False))


def gap_sort_key(row):
    return row["priority"], row["channel"], row["kind"], row["item_id"], row["dimension"]


if __name__ == "__main__":
    main()
