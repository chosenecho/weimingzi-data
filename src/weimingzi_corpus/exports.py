"""Derived edited transcript, subtitle, catalog and search outputs."""

from __future__ import annotations

import csv
import json
import os
import sqlite3
from collections import defaultdict
from decimal import Decimal
from io import StringIO
from pathlib import Path

from .records import (
    JSON_RECORD_TABLES,
    JSONL_TABLES,
    canonical_json,
    read_json,
    iter_records,
    find_timestamp_issues,
    validate_corpus,
)


def extract_post_text(content: dict) -> str:
    """Keep the author's own summary separate from any forwarded full text."""
    dynamic = content.get("modules", {}).get("module_dynamic") or {}
    desc = dynamic.get("desc") or {}
    major = dynamic.get("major") or {}
    opus = major.get("opus") or {}
    summary = opus.get("summary") or {}
    return desc.get("text") or summary.get("text") or ""


def extract_text(row: dict) -> str:
    return (
        extract_post_text(row["content"])
        if row["kind"] == "post"
        else row.get("text", "")
    )


def format_subtitle_timestamp(value: int, separator: str = ".") -> str:
    hours, rest = divmod(value, 3600000)
    minutes, rest = divmod(rest, 60000)
    seconds, milliseconds = divmod(rest, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02}{separator}{milliseconds:03}"


def render_subtitles(record: dict, format: str) -> str:
    if record["kind"] != "transcript":
        raise ValueError(
            "Subtitles require a timed transcript, not an edited transcript"
        )
    issues = find_timestamp_issues(record)
    if issues:
        raise ValueError("Stored timestamps cannot be exported: " + issues[0])
    if record.get("quality", {}).get("is_subtitle_export_enabled") is False:
        raise ValueError("This transcript explicitly disables timed exports")
    output = ["WEBVTT\n"] if format == "vtt" else []
    factor = 1000 if record["time_unit"] == "s" else 1
    for ordinal, segment in enumerate(record["segments"], 1):
        bounds = [Decimal(str(segment[key])) * factor for key in ("start", "end")]
        if any(value != value.to_integral_value() for value in bounds):
            raise ValueError(
                f"Segment {ordinal} cannot be represented at millisecond precision"
            )
        start, end = map(int, bounds)
        separator = "," if format == "srt" else "."
        text = segment["text"]
        if "-->" in text or "\n\n" in text.replace("\r\n", "\n"):
            raise ValueError(
                f"Segment {ordinal} contains text unsafe for subtitle serialization"
            )
        output.append(
            f"{ordinal}\n{format_subtitle_timestamp(start, separator)} --> {format_subtitle_timestamp(end, separator)}\n{text}\n"
        )
    return "\n".join(output)


def render_markdown(row: dict, item: dict) -> str:
    lines = ["# " + item["title"], "", "记录：`" + row["id"] + "`", ""]
    if "quality" in row:
        lines += ["质量标记：`" + canonical_json(row["quality"]) + "`", ""]
    lines += [extract_text(row), ""]
    if row["kind"] == "post":
        for article in row.get("article_item_ids", []):
            lines += ["关联专栏：`" + article + "`", ""]
        if row["content"].get("orig"):
            lines += ["## 转发内容", "", extract_post_text(row["content"]["orig"]), ""]
    return "\n".join(lines)


def render_review_markdown(row: dict, item: dict) -> str:
    if row["kind"] != "edited_transcript":
        raise ValueError("A review requires an edited transcript record")
    if row.get("review_document_markdown"):
        document = row["review_document_markdown"]
        notes = row.get("notes_markdown", "")
        if notes and notes not in document:
            return document + "\n\n## 记录附注\n\n" + notes + "\n"
        return document
    lines = ["# " + item["title"] + "：校验稿", "", row.get("notes_markdown", ""), ""]
    if not row.get("paragraphs_match_text", True):
        lines += ["正文与段落参照有差异；以下保留原有段落参照，不代表逐字对齐。", ""]
    for index, paragraph in enumerate(row["paragraphs"], 1):
        lines += [f"## 段落 {index}", ""]
        if "start" in paragraph and "end" in paragraph:
            lines += [
                f"时间：{paragraph['start']} 至 {paragraph['end']}（{row['time_unit']}）",
                "",
            ]
        if paragraph.get("input_unit_labels"):
            lines += [
                "参照："
                + "、".join("`" + ref + "`" for ref in paragraph["input_unit_labels"]),
                "",
            ]
        lines += [
            "输入文字：" + paragraph.get("input_text", ""),
            "",
            "整理稿：" + paragraph["text"],
            "",
        ]
        for issue in paragraph.get("issues", []):
            lines += ["- 疑点：" + canonical_json(issue)]
        lines.append("")
    return "\n".join(lines)


def iter_review_issues(row: dict):
    """Expose every stored annotation with an exact locator, without inferring status."""
    if row["kind"] != "edited_transcript":
        raise ValueError("Review issues require an edited transcript record")
    for paragraph_index, paragraph in enumerate(row["paragraphs"]):
        for issue_index, issue in enumerate(paragraph.get("issues", [])):
            yield {
                "edited_transcript_id": row["id"],
                "item_id": row["item_id"],
                "paragraph_index": paragraph_index,
                "issue_index": issue_index,
                "record_path": f"data/edited_transcripts/{row['id']}.json",
                "issue": issue,
            }


def iter_content_records(root: Path):
    for table in JSON_RECORD_TABLES:
        for row, _ in iter_records(root, table):
            yield table, row


def render_catalog_csv(root: Path) -> str:
    items = {r["id"]: r for r, _ in iter_records(root, "items")}
    out = StringIO(newline="")
    fields = [
        "id",
        "item_id",
        "kind",
        "title",
        "identifiers",
        "is_fully_human_reviewed",
        "requires_review",
        "record_path",
    ]
    writer = csv.DictWriter(out, fields, lineterminator="\n")
    writer.writeheader()
    for table, row in iter_content_records(root):
        item = items[row["item_id"]]
        flags = row.get("quality", {})
        writer.writerow(
            {
                "id": row["id"],
                "item_id": item["id"],
                "kind": row["kind"],
                "title": item["title"],
                "identifiers": canonical_json(item["identifiers"]),
                "is_fully_human_reviewed": flags.get("is_fully_human_reviewed"),
                "requires_review": flags.get("requires_review"),
                "record_path": f"data/{table}/{row['id']}.json",
            }
        )
    return out.getvalue()


def export_sqlite(root: Path, output: Path) -> None:
    """Rebuild a disposable SQLite search projection from canonical records."""
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.name + ".part")
    if partial.exists():
        raise ValueError(f"Unfinished SQLite export already exists: {partial}")
    connection = sqlite3.connect(partial)
    try:
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=OFF")
        for table in (*JSONL_TABLES, *JSON_RECORD_TABLES):
            connection.execute(
                f'CREATE TABLE "{table}"(id TEXT PRIMARY KEY, item_id TEXT, record_json TEXT NOT NULL)'
            )
        connection.execute(
            "CREATE VIRTUAL TABLE content_search USING fts5(id UNINDEXED, item_id UNINDEXED, kind UNINDEXED, text, tokenize='trigram')"
        )
        for table in (*JSONL_TABLES, *JSON_RECORD_TABLES):
            for row, _ in iter_records(root, table):
                connection.execute(
                    f'INSERT INTO "{table}" VALUES(?,?,?)',
                    (row["id"], row.get("item_id"), canonical_json(row)),
                )
                if table in JSON_RECORD_TABLES:
                    connection.execute(
                        "INSERT INTO content_search VALUES(?,?,?,?)",
                        (row["id"], row["item_id"], row["kind"], extract_text(row)),
                    )
            connection.commit()
        connection.execute(
            "CREATE TABLE selections(name TEXT PRIMARY KEY, selection_json TEXT NOT NULL)"
        )
        selection = read_json(root / "selections/training.json")
        connection.execute(
            "INSERT INTO selections VALUES(?,?)",
            ("training", canonical_json(selection)),
        )
        connection.commit()
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity check failed")
    finally:
        connection.close()
    os.replace(partial, output)


def escape_markdown_label(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("\n", " ")
        .replace("\r", " ")
        .rstrip()
    )


def generate_catalog_docs(root: Path, check: bool = False) -> dict:
    counts = validate_corpus(root)
    items = {r["id"]: r for r, _ in iter_records(root, "items")}
    by_item = defaultdict(list)
    reviews = []
    for table, row in iter_content_records(root):
        by_item[row["item_id"]].append((table, row["id"]))
        if table == "edited_transcripts":
            issue_count = sum(len(p.get("issues", [])) for p in row["paragraphs"])
            reviews.append(
                (
                    row["item_id"],
                    row["id"],
                    issue_count,
                    row.get("quality", {}).get("requires_review"),
                    row["is_complete"],
                    bool(row.get("notes_markdown")),
                    bool(row.get("review_document_markdown")),
                )
            )
    children = defaultdict(list)
    for row in items.values():
        if row.get("parent_id"):
            children[row["parent_id"]].append(row)
    output = {}
    intro = "此目录由 `python tools/corpus.py generate` 生成。所有结果分别列出，排序不代表审核质量。\n\n"

    def links(item_id):
        return (
            " · ".join(
                f"[{table}:{record_id[2:10]}](../../data/{table}/{record_id}.json)"
                for table, record_id in sorted(by_item[item_id])
            )
            or "仅元数据"
        )

    for group, title, kinds in [
        ("videos", "视频与分段", {"video"}),
        ("audio_recordings", "独立录音", {"audio_recording"}),
        ("posts", "动态", {"post"}),
        ("articles", "专栏", {"article"}),
        ("people", "人物资料", {"person"}),
    ]:
        lines = ["# " + title, "", intro]
        selected = sorted(
            (i for i in items.values() if i["kind"] in kinds),
            key=lambda i: (i["title"], i["id"]),
        )
        for row in selected:
            lines += [
                f'<a id="{row["id"]}"></a>',
                "",
                "## " + escape_markdown_label(row["title"] or row["id"]),
                "",
                "条目：`" + row["id"] + "`",
                "",
            ]
            if row["urls"]:
                lines += [
                    " · ".join(
                        f"[原文 {i}]({url})" for i, url in enumerate(row["urls"], 1)
                    ),
                    "",
                ]
            lines += [links(row["id"]), ""]
            for child in sorted(
                children[row["id"]], key=lambda x: (x.get("part_number", 0), x["id"])
            ):
                lines += [
                    "- "
                    + escape_markdown_label(child["title"])
                    + "："
                    + links(child["id"])
                ]
            lines.append("")
        output[f"docs/catalog/{group}.md"] = "\n".join(lines).rstrip() + "\n"
    groups = {
        "video": "videos",
        "video_part": "videos",
        "audio_recording": "audio_recordings",
        "post": "posts",
        "article": "articles",
        "person": "people",
    }
    lines = ["# 文集、合集与系列", "", intro]
    for row, _ in sorted(
        iter_records(root, "collections"),
        key=lambda pair: (pair[0]["title"], pair[0]["id"]),
    ):
        lines += [
            "## " + escape_markdown_label(row["title"]),
            "",
            "集合：`" + row["id"] + "`（" + row["kind"] + "）",
            "",
        ]
        for member in row["members"]:
            entry = items[member["item_id"]]
            group = groups[entry["kind"]]
            target = entry.get("parent_id", entry["id"])
            lines.append(
                f"{member['position']}. [{escape_markdown_label(entry['title'])}]({group}.md#{target})"
            )
        lines.append("")
    output["docs/catalog/collections.md"] = "\n".join(lines).rstrip() + "\n"
    lines = [
        "# 校对标注与复核状态",
        "",
        intro,
        "列出全部整理稿，包括没有段落标注的结果。标注数量包含疑点、候选改法和修改说明，不代表未解决问题的数量。",
        "",
        "[字段定义](../GLOSSARY.md#校对标注与参照稿) · [查阅与导出](../MAINTENANCE.md#查看校对标注)",
        "",
        "| 整理稿 | 标注数 | 待复核 | 结果完成 | 附注 | 独立校验稿 |",
        "| --- | ---: | --- | --- | --- | --- |",
    ]
    labels = {True: "是", False: "否", None: "未说明"}
    for item_id, record_id, count, review, complete, notes, document in sorted(
        reviews, key=lambda entry: (items[entry[0]]["title"], entry[1])
    ):
        title = escape_markdown_label(items[item_id]["title"]).replace("|", "\\|")
        lines.append(
            f"| [{title} · {record_id[2:10]}](../../data/edited_transcripts/{record_id}.json) "
            f"| {count} | {labels[review]} | {labels[complete]} | {labels[notes]} | {labels[document]} |"
        )
    output["docs/catalog/reviews.md"] = "\n".join(lines).rstrip() + "\n"
    output["docs/INDEX.md"] = (
        "# 数据目录\n\n[名词与概念](GLOSSARY.md) · [数据结构](SCHEMA.md)\n\n由 `python tools/corpus.py generate` 生成。计数见 [counts.json](counts.json)。\n\n"
        + "\n".join(
            [
                "- [视频与分段](catalog/videos.md)",
                "- [独立录音](catalog/audio_recordings.md)",
                "- [动态](catalog/posts.md)",
                "- [专栏](catalog/articles.md)",
                "- [文集、合集与系列](catalog/collections.md)",
                "- [人物资料](catalog/people.md)",
                "- [校对标注与复核状态](catalog/reviews.md)",
                "",
                f"基础转录 {counts['transcripts']} 条；整理结果 {counts['edited_transcripts']} 条；动态 {counts['posts']} 条；专栏 {counts['articles']} 篇。",
                "",
                "正文保存在对应 JSON 记录中；可用 `export` 命令生成 Markdown、文本和字幕。\n",
            ]
        )
    )
    output["docs/counts.json"] = json.dumps(counts, ensure_ascii=False, indent=2) + "\n"
    for name, value in output.items():
        path = root / name
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != value:
                raise ValueError(f"Generated file is stale: {name}; run generate")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value, encoding="utf-8", newline="\n")
    return counts
