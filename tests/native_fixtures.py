"""Small native four-entity corpus shared by integration tests; no migration step."""
from __future__ import annotations

import hashlib
from pathlib import Path

from weimingzi_corpus.records import ENTITIES, document_hash_input, json_sha256, make_record_id, write_json, write_jsonl


def rid(name: str, prefix: str = "i") -> str:
    return make_record_id(prefix, name)


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def fixture_records() -> dict[str, list[dict]]:
    """Return fresh editable records, including independent assets and local evidence.

    Documents are ordered transcript, edited_transcript, revision, post, article.
    Item IDs use rid('video'), rid('part'), rid('post'), rid('article'), rid('collection').
    Document IDs use rid('transcript','t'), rid('edited','r'), rid('revision','r'),
    rid('post','d'), rid('article','a'). No fixture asserts whole-document review.
    """
    video, part, post_item, article_item, collection = [rid(name) for name in ("video", "part", "post", "article", "collection")]
    transcript, edited, revision = rid("transcript", "t"), rid("edited", "r"), rid("revision", "r")
    audio, archive = rid("audio", "m"), rid("archive", "z")
    items = [
        {"id": video, "kind": "video", "title": "示例视频", "identifiers": {"bilibili_bvid": ["BVfixture"]}, "urls": ["https://example.org/video"], "metadata": {}},
        {"id": part, "kind": "video_part", "title": "示例分段", "identifiers": {"bilibili_bvid": ["BVfixture"], "bilibili_part": ["BVfixture:P1"]}, "parent_id": video, "part_number": 1, "urls": ["https://example.org/video?p=1"], "metadata": {}},
        {"id": post_item, "kind": "post", "title": "动态", "identifiers": {"bilibili_dynamic": ["123"]}, "metadata": {}},
        {"id": article_item, "kind": "article", "title": "文章", "identifiers": {"bilibili_cvid": ["456"]}, "metadata": {}},
        {"id": collection, "kind": "video_collection", "title": "合集", "identifiers": {}, "members": [{"item_id": video}], "metadata": {}},
    ]
    raw = {"id": transcript, "kind": "transcript", "inputs": [{"role": "item", "target_id": part}, {"role": "audio", "target_id": audio}],
           "method": "asr_cloud", "language": "zh", "model": {"name": "fixture-asr"}, "time_unit": "ms", "text": "原句😀。第二段。",
           "blocks": [{"range": [0, 4], "start": 0, "end": 1000}, {"range": [4, 8], "start": 1000, "end": 2000}],
           "quality": {"is_fully_human_reviewed": None, "requires_review": True, "is_subtitle_export_enabled": True}, "metadata": {}}
    raw["content_sha256"] = json_sha256(document_hash_input(raw))
    base = {"id": edited, "kind": "edited_transcript", "inputs": [{"role": "item", "target_id": part}, {"role": "transcript", "target_id": transcript}],
            "text": "原句😀。\n\n第二段。", "time_unit": "ms", "model": None, "is_complete": True,
            "blocks": [{"range": [0, 4], "start": 0, "end": 1000, "input_unit_labels": ["unit-1"], "input_text_ref": {"target_id": transcript, "content_sha256": raw["content_sha256"], "source": "blocks", "range": [0, 4]}, "issues": []},
                       {"range": [6, 10], "start": 1000, "end": 2000, "input_text": "第二段。", "input_unit_labels": ["unit-2"], "issues": []}],
            "input_units": {"base": {"content_sha256": "historical-observation", "segments": [{"label": "unit-1", "text": "原句😀。", "start_ms": 0, "end_ms": 1000}, {"label": "unit-2", "text": "第二段。", "start_ms": 1000, "end_ms": 2000}]}, "unassigned_reference_labels": []},
            "quality": {"is_fully_human_reviewed": False, "requires_review": True, "is_subtitle_export_enabled": True}, "notes_markdown": "保留的局部注记。", "metadata": {"source_sha256": "historical-observation"}}
    revised = {"id": revision, "kind": "edited_transcript", "inputs": [{"role": "item", "target_id": part}, {"role": "transcript", "target_id": transcript}, {"role": "derived_from", "target_id": edited}, {"role": "input_units_from", "target_id": edited}],
               "text": "改句😀。\n\n第二段。", "time_unit": "ms", "model": None, "is_complete": True,
               "blocks": [{"range": [0, 4], "start": 0, "end": 1000, "input_unit_labels": ["unit-1"], "input_text": "原句😀。", "issues": []}, {"range": [6, 10], "start": 1000, "end": 2000, "input_unit_labels": ["unit-2"], "issues": []}],
               "quality": {"is_fully_human_reviewed": False, "requires_review": True, "is_subtitle_export_enabled": True}, "notes_markdown": "仅首段采用确认。"}
    confirmation = {"id": rid("confirmation", "a"), "kind": "confirmation", "targets": [{"role": "item", "target_id": part}, {"role": "applies_to", "target_id": edited}, {"role": "revision", "target_id": revision, "order": 0}],
                    "anchor": {"original_text": "原句😀。", "original_text_sha256": text_sha256("原句😀。"), "input_unit_label": "unit-1", "paragraph_index": 0},
                    "corrected_text": "改句😀。", "corrected_text_sha256": text_sha256("改句😀。"), "scope": "local_text_or_term", "status": "user_confirmed", "term_glosses": {},
                    "confirmation": {"reviewer_label": "fixture-reviewer", "reviewed_on": "2026-11-05", "review_timezone": "Asia/Hong_Kong", "assistant_listened_to_audio": False, "excerpt": "只改首字", "resolution": "局部确认"}, "urls": []}
    attribution = {"id": rid("attribution", "s"), "kind": "segment_attribution", "targets": [{"role": "item", "target_id": part}, {"role": "applies_to", "target_id": edited}],
                   "anchor": {"paragraph_index": 1, "paragraph_text_sha256": text_sha256("第二段。"), "excerpt": None, "start": 1000, "end": 2000, "time_unit": "ms"},
                   "speaker_role": "primary_speaker", "viewpoint": "own_view", "status": "human_confirmed", "review": {"basis": "人工查看指定片段", "reviewer_label": "fixture-reviewer", "reviewed_on": "2026-11-06", "review_timezone": "Asia/Hong_Kong", "reviewer_reported_watched_original_video": True, "assistant_listened_to_audio": False}, "urls": []}
    return {"items": items, "documents": [raw, base, revised,
        {"id": rid("post", "d"), "kind": "post", "inputs": [{"role": "item", "target_id": post_item}, {"role": "article_item", "target_id": article_item}], "content": {"text": "动态正文"}},
        {"id": rid("article", "a"), "kind": "article", "inputs": [{"role": "item", "target_id": article_item}], "text": "文章正文", "quality": {"is_fully_human_reviewed": None}}],
        "assets": [{"id": audio, "kind": "audio", "inputs": [{"role": "item", "target_id": part}], "availability": "available", "sha256": "a" * 64, "size_bytes": 3, "local_path": "audio/fixture.m4a", "downloads": [{"release_tag": "fixture-v1", "archive_id": archive, "member_path": "原始/fixture.m4a"}]},
                   {"id": archive, "kind": "archive", "name": "fixture.tar", "sha256": "b" * 64, "size_bytes": 100, "url": "https://example.org/fixture.tar"},
                   {"id": rid("independent-archive", "z"), "kind": "archive", "name": "independent.tar", "sha256": "c" * 64, "size_bytes": 0, "url": "https://example.org/independent.tar"}],
        "annotations": [confirmation, attribution]}


def write_corpus(root: Path, records=None) -> dict[str, list[dict]]:
    records = fixture_records() if records is None else records
    root = Path(root)
    write_json(root / "data/schema.json", {"schema_version": 3, "entities": list(ENTITIES), "range_unit": "unicode_codepoint", "range_end": "exclusive"})
    (root / "data/documents").mkdir(parents=True, exist_ok=True)
    for entity in ENTITIES:
        if entity == "documents":
            for row in records.get(entity, []):
                write_json(root / "data/documents" / (row["id"] + ".json"), row)
        else:
            write_jsonl(root / "data" / (entity + ".jsonl"), records.get(entity, []))
    return records
