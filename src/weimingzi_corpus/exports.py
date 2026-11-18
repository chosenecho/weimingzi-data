"""Disposable catalog, search, text and review outputs from native records."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sqlite3
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from io import StringIO
from pathlib import Path

from .records import (
    ENTITIES, block_text, canonical_json, input_ids, iter_records, record_path,
    resolve_input_text, resolve_repository_path, validate_corpus,
)


def extract_post_text(content: dict) -> str:
    """Return the author's own text; forwarding remains a separate observation."""
    dynamic = content.get("modules", {}).get("module_dynamic") or {}
    desc = dynamic.get("desc") or {}
    opus = (dynamic.get("major") or {}).get("opus") or {}
    return desc.get("text") or (opus.get("summary") or {}).get("text") or content.get("text", "")


def extract_text(document: dict) -> str:
    return extract_post_text(document.get("content", {})) if document["kind"] == "post" else document.get("text", "")


def format_subtitle_timestamp(value: int, separator: str = ".") -> str:
    hours, rest = divmod(value, 3600000)
    minutes, rest = divmod(rest, 60000)
    seconds, milliseconds = divmod(rest, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02}{separator}{milliseconds:03}"


def render_subtitles(document: dict, format: str) -> str:
    """Serialize stored blocks in order, without repairing their times or text."""
    if format not in {"srt", "vtt"}:
        raise ValueError("Expected srt or vtt")
    if document["kind"] != "transcript":
        raise ValueError("Subtitles require a timed transcript")
    if document.get("quality", {}).get("is_subtitle_export_enabled") is False:
        raise ValueError("This transcript explicitly disables timed exports")
    if document.get("time_unit") not in {"s", "ms"}:
        raise ValueError("Subtitles require an explicit s or ms time unit")
    factor = 1000 if document["time_unit"] == "s" else 1
    output = ["WEBVTT\n"] if format == "vtt" else []
    previous_end = Decimal(0)
    for ordinal, block in enumerate(document.get("blocks", []), 1):
        try:
            if any(type(block.get(key)) not in (int, float) for key in ("start", "end")):
                raise ValueError("Times must be numbers")
            start, end = [Decimal(str(block[key])) * factor for key in ("start", "end")]
        except (InvalidOperation, ValueError, KeyError) as error:
            raise ValueError(f"Block {ordinal} has invalid timestamps") from error
        if not start.is_finite() or not end.is_finite() or not 0 <= start < end or start < previous_end:
            raise ValueError(f"Block {ordinal} has unordered or invalid timestamps")
        if any(value != value.to_integral_value() for value in (start, end)):
            raise ValueError(f"Block {ordinal} cannot be represented at millisecond precision")
        previous_end = end
        text = block_text(document, block)
        if "-->" in text or "\n\n" in text.replace("\r\n", "\n"):
            raise ValueError(f"Block {ordinal} contains text unsafe for subtitle serialization")
        separator = "," if format == "srt" else "."
        output.append(f"{ordinal}\n{format_subtitle_timestamp(int(start), separator)} --> {format_subtitle_timestamp(int(end), separator)}\n{text}\n")
    return "\n".join(output)


def render_markdown(document: dict, item: dict) -> str:
    lines = ["# " + item["title"], "", "文档：`" + document["id"] + "`", ""]
    if "quality" in document:
        lines += ["质量标记：`" + canonical_json(document["quality"]) + "`", ""]
    lines += [extract_text(document), ""]
    if document["kind"] == "post":
        for article in input_ids(document, "article_item"):
            lines += ["关联专栏：`" + article + "`", ""]
        original = document.get("content", {}).get("orig")
        if original:
            lines += ["## 转发内容", "", extract_post_text(original), ""]
    return "\n".join(lines)


def render_review_markdown(document: dict, item: dict, root: Path | None = None) -> str:
    if document["kind"] != "edited_transcript":
        raise ValueError("A review requires an edited_transcript document")
    assets = input_ids(document, "review_document_markdown")
    if assets:
        if root is None or len(assets) != 1:
            raise ValueError("Review artifact requires a root and exactly one asset")
        asset = next((row for row, _ in iter_records(root, "assets") if row["id"] == assets[0]), None)
        if asset is None:
            raise ValueError("Missing review artifact asset")
        payload = resolve_repository_path(root, asset["local_path"]).read_bytes()
        if hashlib.sha256(payload).hexdigest() != asset["sha256"] or len(payload) != asset["size_bytes"]:
            raise ValueError("Review artifact byte hash or size mismatch")
        text = payload.decode("utf-8")
        notes = document.get("notes_markdown") or ""
        return text + "\n\n## 记录附注\n\n" + notes + "\n" if notes and notes not in text else text
    entities = {"documents": {row["id"]: row for row, _ in iter_records(root, "documents")}} if root is not None else {"documents": {}}
    lines = ["# " + item["title"] + "：校验稿", "", document.get("notes_markdown") or "", ""]
    for ordinal, block in enumerate(document.get("blocks", []), 1):
        lines += [f"## 正文块 {ordinal}", ""]
        if "start" in block and "end" in block:
            lines += [f"时间：{block['start']} 至 {block['end']}（{document.get('time_unit', '未说明')}）", ""]
        if block.get("input_unit_labels"):
            lines += ["参照：" + "、".join("`" + label + "`" for label in block["input_unit_labels"]), ""]
        source = resolve_input_text(document, block, entities)
        lines += ["输入文字：" + (source or ""), "", "整理稿：" + block_text(document, block), ""]
        lines += ["- 疑点：" + canonical_json(issue) for issue in block.get("issues", [])]
        lines.append("")
    return "\n".join(lines)


def iter_review_issues(document: dict, root: Path | None = None):
    """Expose stored issues unchanged, including empty candidate observations."""
    if document["kind"] != "edited_transcript":
        raise ValueError("Review issues require an edited_transcript document")
    path = record_path(root, "documents", document["id"]).relative_to(root.resolve()).as_posix() if root is not None else f"data/documents/{document['id']}.json"
    for block_index, block in enumerate(document.get("blocks", [])):
        for issue_index, issue in enumerate(block.get("issues", [])):
            yield {"document_id": document["id"], "block_index": block_index, "issue_index": issue_index, "path": path, "issue": issue}


def render_catalog_csv(root: Path) -> str:
    items = {row["id"]: row for row, _ in iter_records(root, "items")}
    out = StringIO(newline="")
    fields = ["id", "item_id", "kind", "title", "identifiers", "is_fully_human_reviewed", "requires_review", "path"]
    writer = csv.DictWriter(out, fields, lineterminator="\n")
    writer.writeheader()
    for document, path in iter_records(root, "documents"):
        for owner in input_ids(document, "item"):
            item = items[owner]
            quality = document.get("quality", {})
            writer.writerow({"id": document["id"], "item_id": owner, "kind": document["kind"], "title": item["title"], "identifiers": canonical_json(item.get("identifiers", {})), "is_fully_human_reviewed": quality.get("is_fully_human_reviewed"), "requires_review": quality.get("requires_review"), "path": path.relative_to(root).as_posix()})
    return out.getvalue()


def export_sqlite(root: Path, output: Path) -> None:
    """Rebuild four native tables and a disposable document full-text index."""
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.name + ".part")
    if partial.exists():
        raise ValueError(f"Unfinished SQLite export already exists: {partial}")
    connection = sqlite3.connect(partial)
    try:
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=OFF")
        for entity in ENTITIES:
            connection.execute(f'CREATE TABLE "{entity}"(id TEXT PRIMARY KEY, kind TEXT NOT NULL, record_json TEXT NOT NULL)')
            connection.executemany(f'INSERT INTO "{entity}" VALUES(?,?,?)', ((row["id"], row["kind"], canonical_json(row)) for row, _ in iter_records(root, entity)))
        connection.execute("CREATE VIRTUAL TABLE content_search USING fts5(id UNINDEXED, item_id UNINDEXED, kind UNINDEXED, text, tokenize='trigram')")
        for document, _ in iter_records(root, "documents"):
            owners = input_ids(document, "item")
            connection.execute("INSERT INTO content_search VALUES(?,?,?,?)", (document["id"], owners[0] if owners else None, document["kind"], extract_text(document)))
        connection.commit()
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity check failed")
    except BaseException:
        connection.close()
        partial.unlink(missing_ok=True)
        raise
    else:
        connection.close()
    os.replace(partial, output)


def escape_markdown_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]").replace("\n", " ").replace("\r", " ").rstrip()


def render_catalog_link(document: dict, root: Path) -> str:
    kind = document["kind"]
    label = {"transcript": "基础转录", "edited_transcript": "整理稿", "post": "动态正文", "article": "文章正文"}.get(kind, kind)
    if document.get("method"):
        label += " · " + document["method"]
    model = document.get("model") or {}
    if model.get("name"):
        label += "（" + model["name"].replace("\\", "/").rsplit("/", 1)[-1] + "）"
    target = record_path(root, "documents", document["id"]).relative_to(root.resolve()).as_posix()
    result = f"[{escape_markdown_label(label)}:{document['id'][2:10]}](../../{target})"
    if kind == "edited_transcript":
        sources = "、".join("`" + value[2:10] + "`" for value in input_ids(document, "transcript"))
        result += "（输入：" + sources + "）" if sources else "（输入未关联）"
    return result


def generate_catalog_docs(root: Path, check: bool = False) -> dict:
    counts = validate_corpus(root)
    items = {row["id"]: row for row, _ in iter_records(root, "items")}
    by_item, children, rerecordings = defaultdict(list), defaultdict(list), defaultdict(list)
    reviews = []
    for document, _ in iter_records(root, "documents"):
        for owner in input_ids(document, "item"):
            by_item[owner].append((document["id"], render_catalog_link(document, root)))
            if document["kind"] == "edited_transcript":
                reviews.append((owner, document))
    for item in items.values():
        if item.get("parent_id"):
            children[item["parent_id"]].append(item)
        for relation in item.get("relations", []):
            if relation["kind"] == "audible_rerecording_of":
                rerecordings[relation["target_item_id"]].append(item)
    def links(item_id):
        return " · ".join(link for _, link in sorted(by_item[item_id])) or "仅条目元数据"
    def recording_notes(item):
        notes = []
        metadata = item.get("metadata", {})
        if "silent_audio_confirmed" in metadata.get("audio_assessment", []):
            confirmed = any(isinstance(evidence, dict) and evidence.get("basis") == "user_confirmation" for evidence in metadata.get("audio_assessment_evidence", []))
            notes.append("用户确认无声" if confirmed else "已确认无声")
        for source in sorted(rerecordings[item["id"]], key=lambda row: row["id"]):
            notes.append("有声重录版 " + escape_markdown_label(source["title"]) + " 的相关文档：" + links(source["id"]))
        return "".join("；" + note for note in notes)
    intro = "由 `uv run python tools/corpus.py generate` 生成。文档按 kind 分别列出；排序不代表审核质量。\n"
    groups = {"video": "videos", "video_part": "videos", "audio_recording": "audio_recordings", "post": "posts", "article": "articles", "person": "people"}
    output = {}
    for group, title, kind in [("videos", "视频与分段", "video"), ("audio_recordings", "独立录音", "audio_recording"), ("posts", "动态", "post"), ("articles", "专栏", "article"), ("people", "人物资料", "person")]:
        lines = ["# " + title, "", intro]
        if kind in {"video", "audio_recording"}:
            lines += ["同一条目可关联多份 transcript 与 edited_transcript 文档。输入边保留各份文档的来源；完整模型、质量与正文块见原生 JSON。", ""]
        for item in sorted((row for row in items.values() if row["kind"] == kind), key=lambda row: (row["title"], row["id"])):
            lines += [f'<a id="{item["id"]}"></a>', "", "## " + escape_markdown_label(item["title"] or item["id"]), "", "条目：`" + item["id"] + "`", ""]
            lines += [" · ".join(f"[原文 {ordinal}]({url})" for ordinal, url in enumerate(item.get("urls", []), 1)), "", links(item["id"]) + recording_notes(item), ""]
            for child in sorted(children[item["id"]], key=lambda row: (row.get("part_number", 0), row["id"])):
                lines += ["- " + escape_markdown_label(child["title"]) + "：" + links(child["id"]) + recording_notes(child)]
            lines.append("")
        output[f"docs/catalog/{group}.md"] = "\n".join(lines).rstrip() + "\n"
    lines = ["# 文集、合集与系列", "", intro, "集合是 items 中带有成员的集合 kind。", ""]
    for item in sorted((row for row in items.values() if row["kind"] in {"video_collection", "video_series", "article_collection"}), key=lambda row: (row["title"], row["id"])):
        lines += ["## " + escape_markdown_label(item["title"]), "", f"集合条目：`{item['id']}`（{item['kind']}）", ""]
        for ordinal, member in enumerate(item.get("members", []), 1):
            entry = items[member["item_id"]]
            group = groups[entry["kind"]]
            lines.append(f"{ordinal}. [{escape_markdown_label(entry['title'])}]({group}.md#{entry.get('parent_id', entry['id'])})")
        lines.append("")
    output["docs/catalog/collections.md"] = "\n".join(lines).rstrip() + "\n"
    lines = ["# 校对标注与复核状态", "", intro, "列出全部 edited_transcript 文档。正文块中的 issues 保留原样，数量不代表未解决问题数；局部确认不等于全文审核。", "", "| 文档 | 标注数 | 待复核 | 结果完成 | 附注 | 独立校验稿 |", "| --- | ---: | --- | --- | --- | --- |"]
    labels = {True: "是", False: "否", None: "未说明"}
    for owner, document in sorted(reviews, key=lambda pair: (items[pair[0]]["title"], pair[1]["id"])):
        title = escape_markdown_label(items[owner]["title"]).replace("|", "\\|")
        target = record_path(root, "documents", document["id"]).relative_to(root.resolve()).as_posix()
        values = [sum(len(block.get("issues", [])) for block in document.get("blocks", [])), labels[document.get("quality", {}).get("requires_review")], labels[document.get("is_complete")], labels[bool(document.get("notes_markdown"))], labels[bool(input_ids(document, "review_document_markdown"))]]
        lines.append(f"| [{title} · {document['id'][2:10]}](../../{target}) | " + " | ".join(map(str, values)) + " |")
    output["docs/catalog/reviews.md"] = "\n".join(lines).rstrip() + "\n"
    navigation = [("视频与分段", "videos"), ("独立录音", "audio_recordings"), ("动态", "posts"), ("专栏", "articles"), ("文集、合集与系列", "collections"), ("人物资料", "people"), ("校对标注与复核状态", "reviews")]
    if (root / "selections/topics.json").is_file():
        navigation.insert(2, ("专题索引", "topics"))
    output["docs/INDEX.md"] = "# 数据目录\n\n[结构与术语](SCHEMA.md) · [查询与导出](QUERY.md)\n\n" + intro + "\n" + "\n".join(f"- [{title}](catalog/{group}.md)" for title, group in navigation) + "\n\n" + "；".join(f"{entity} {counts[entity]} 条" for entity in ENTITIES) + "。完整计数见 [counts.json](counts.json)。\n\n正文来自 documents 的 text/content/blocks；音频与独立工件来自 assets，人工依据来自 annotations。\n"
    output["docs/counts.json"] = json.dumps(counts, ensure_ascii=False, indent=2) + "\n"
    for relative, value in output.items():
        path = root / relative
        if check:
            if not path.is_file() or path.read_text(encoding="utf-8") != value:
                raise ValueError(f"Generated file is stale: {relative}; run generate")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value, encoding="utf-8", newline="\n")
    return counts
