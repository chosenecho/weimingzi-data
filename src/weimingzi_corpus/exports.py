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
    content_record_path,
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


def iter_review_issues(row: dict, root: Path | None = None):
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
                "record_path": (
                    content_record_path(root, "edited_transcripts", row["id"])
                    .relative_to(root.resolve()).as_posix()
                    if root is not None else f"data/edited_transcripts/{row['id']}.json"
                ),
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
                "record_path": (
                    content_record_path(root, table, row["id"])
                    .relative_to(root.resolve()).as_posix()
                ),
            }
        )
    return out.getvalue()


def export_sqlite(root: Path, output: Path) -> None:
    """Rebuild native record tables and a disposable full-text search projection."""
    from .schema_v3 import is_v3, iter_native_records

    native = is_v3(root)
    tables = (
        ("items", "documents", "assets", "annotations")
        if native else (*JSONL_TABLES, *JSON_RECORD_TABLES)
    )
    iterate = iter_native_records if native else iter_records
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.name + ".part")
    if partial.exists():
        raise ValueError(f"Unfinished SQLite export already exists: {partial}")
    connection = sqlite3.connect(partial)
    try:
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=OFF")
        for table in tables:
            connection.execute(
                f'CREATE TABLE "{table}"(id TEXT PRIMARY KEY, item_id TEXT, record_json TEXT NOT NULL)'
            )
        connection.execute(
            "CREATE VIRTUAL TABLE content_search USING fts5(id UNINDEXED, item_id UNINDEXED, kind UNINDEXED, text, tokenize='trigram')"
        )
        for table in tables:
            for row, _ in iterate(root, table):
                item_id = row.get("item_id")
                if native:
                    owners = [
                        edge["target_id"]
                        for edge in row.get("inputs", row.get("targets", []))
                        if edge["role"] == "item"
                    ]
                    item_id = owners[0] if len(owners) == 1 else None
                connection.execute(
                    f'INSERT INTO "{table}" VALUES(?,?,?)',
                    (row["id"], item_id, canonical_json(row)),
                )
            connection.commit()
        for _, row in iter_content_records(root):
            connection.execute(
                "INSERT INTO content_search VALUES(?,?,?,?)",
                (row["id"], row["item_id"], row["kind"], extract_text(row)),
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


def render_catalog_link(table: str, row: dict, root: Path | None = None) -> str:
    if table == "transcripts":
        label = {
            "subtitle_ai": "平台 AI 字幕",
            "subtitle_cc": "平台 CC 字幕",
            "asr_local": "本地语音转录",
            "asr_cloud": "云端语音转录",
        }.get(row["method"], f"基础转录（{row['method']}）")
    elif table == "edited_transcripts":
        label = "整理稿"
    else:
        label = table
    if table in {"transcripts", "edited_transcripts"}:
        model = row.get("model") or {}
        if model.get("name"):
            model_name = model["name"].replace("\\", "/").rsplit("/", 1)[-1]
            label += f"（{model_name}）"
    record_id = row["id"]
    target = (
        content_record_path(root, table, record_id).relative_to(root.resolve()).as_posix()
        if root is not None else f"data/{table}/{record_id}.json"
    )
    link = (
        f"[{escape_markdown_label(label)}:{record_id[2:10]}]"
        f"(../../{target})"
    )
    if table == "edited_transcripts":
        inputs = "、".join(
            f"`{transcript_id[2:10]}`"
            for transcript_id in row.get("transcript_ids", [])
        )
        link += f"（输入：{inputs}）" if inputs else "（输入未关联）"
    return link


def generate_catalog_docs(root: Path, check: bool = False) -> dict:
    counts = validate_corpus(root)
    items = {r["id"]: r for r, _ in iter_records(root, "items")}
    by_item = defaultdict(list)
    reviews = []
    for table, row in iter_content_records(root):
        by_item[row["item_id"]].append((table, row["id"], render_catalog_link(table, row, root)))
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
    transcript_intro = (
        "同一条目可有多份平台字幕、语音转录和整理稿。链接标明识别方式、已知模型和短 ID；"
        "整理稿后的“输入”对应其关联的基础转录短 ID，“输入未关联”表示尚无可确认的内部引用。"
        "模型路径仅显示末段，完整值保存在 JSON 中。"
        "详见[基础转录与整理稿](../GLOSSARY.md#基础转录与整理稿)。\n\n"
    )

    def links(item_id):
        return (
            " · ".join(link for _, _, link in sorted(by_item[item_id]))
            or "仅元数据"
        )

    rerecordings = defaultdict(list)
    for source in items.values():
        for relation in source.get("relations", []):
            if relation["kind"] == "audible_rerecording_of":
                rerecordings[relation["target_item_id"]].append(source)

    def recording_notes(item):
        notes = []
        metadata = item.get("metadata", {})
        if "silent_audio_confirmed" in metadata.get("audio_assessment", []):
            user_confirmed = any(
                evidence.get("basis") == "user_confirmation"
                for evidence in metadata.get("audio_assessment_evidence", [])
                if isinstance(evidence, dict)
            )
            notes.append("用户确认无声" if user_confirmed else "已确认无声")
        for source in sorted(rerecordings[item["id"]], key=lambda row: row["id"]):
            label = (
                f'P{source["part_number"]}'
                if source.get("part_number") is not None
                and source.get("parent_id")
                and source.get("parent_id") == item.get("parent_id")
                else source["title"]
            )
            notes.append(
                "有声重录版 "
                + escape_markdown_label(label)
                + " 的文稿（相关覆盖）："
                + links(source["id"])
            )
        return "".join("；" + note for note in notes)

    for group, title, kinds in [
        ("videos", "视频与分段", {"video"}),
        ("audio_recordings", "独立录音", {"audio_recording"}),
        ("posts", "动态", {"post"}),
        ("articles", "专栏", {"article"}),
        ("people", "人物资料", {"person"}),
    ]:
        lines = ["# " + title, "", intro]
        if group in {"videos", "audio_recordings"}:
            lines.append(transcript_intro)
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
            lines += [links(row["id"]) + recording_notes(row), ""]
            for child in sorted(
                children[row["id"]], key=lambda x: (x.get("part_number", 0), x["id"])
            ):
                lines += [
                    "- "
                    + escape_markdown_label(child["title"])
                    + "："
                    + links(child["id"])
                    + recording_notes(child)
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
        target = content_record_path(root, "edited_transcripts", record_id).relative_to(root.resolve()).as_posix()
        lines.append(
            f"| [{title} · {record_id[2:10]}](../../{target}) "
            f"| {count} | {labels[review]} | {labels[complete]} | {labels[notes]} | {labels[document]} |"
        )
    output["docs/catalog/reviews.md"] = "\n".join(lines).rstrip() + "\n"
    topic_navigation = []
    if (root / "selections/topics.json").is_file():
        topic_navigation = ["- [专题索引](catalog/topics.md)"]
    output["docs/INDEX.md"] = (
        "# 数据目录\n\n[名词与概念](GLOSSARY.md) · [数据结构](SCHEMA.md)\n\n由 `python tools/corpus.py generate` 生成。计数见 [counts.json](counts.json)。\n\n"
        + "\n".join(
            [
                "- [视频与分段](catalog/videos.md)",
                "- [独立录音](catalog/audio_recordings.md)",
                *topic_navigation,
                "- [动态](catalog/posts.md)",
                "- [专栏](catalog/articles.md)",
                "- [文集、合集与系列](catalog/collections.md)",
                "- [人物资料](catalog/people.md)",
                "- [校对标注与复核状态](catalog/reviews.md)",
                "",
                "同一条目可有多份基础转录及整理稿；目录按识别方式和模型标注，并列出整理稿关联的输入。见[基础转录与整理稿](GLOSSARY.md#基础转录与整理稿)。",
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
