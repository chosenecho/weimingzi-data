"""Derived reading, subtitle, catalog and search outputs."""

from __future__ import annotations

import csv
import json
import os
import sqlite3
from collections import defaultdict
from decimal import Decimal
from io import StringIO
from pathlib import Path

from .data import (
    DIRECTORIES,
    TABLES,
    canonical,
    read_json,
    records,
    timing_issues,
    validate,
)


def dynamic_text(content: dict) -> str:
    """Keep the author's own summary separate from any forwarded full text."""
    dynamic = content.get("modules", {}).get("module_dynamic") or {}
    desc = dynamic.get("desc") or {}
    major = dynamic.get("major") or {}
    opus = major.get("opus") or {}
    summary = opus.get("summary") or {}
    return desc.get("text") or summary.get("text") or ""


def text_of(row: dict) -> str:
    return (
        dynamic_text(row["content"])
        if row["kind"] == "dynamic"
        else row.get("text", "")
    )


def clock_ms(value: int, separator: str = ".") -> str:
    hours, rest = divmod(value, 3600000)
    minutes, rest = divmod(rest, 60000)
    seconds, milliseconds = divmod(rest, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02}{separator}{milliseconds:03}"


def subtitle(record: dict, format: str) -> str:
    if record["kind"] != "transcript":
        raise ValueError("Subtitles require a timed transcript, not a reading")
    issues = timing_issues(record)
    if issues:
        raise ValueError("Stored timestamps cannot be exported: " + issues[0])
    if record.get("quality", {}).get("timed_exports_available") is False:
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
            f"{ordinal}\n{clock_ms(start, separator)} --> {clock_ms(end, separator)}\n{text}\n"
        )
    return "\n".join(output)


def markdown(row: dict, item: dict) -> str:
    lines = ["# " + item["title"], "", "记录：`" + row["id"] + "`", ""]
    if "quality" in row:
        lines += ["质量标记：`" + canonical(row["quality"]) + "`", ""]
    lines += [text_of(row), ""]
    if row["kind"] == "dynamic":
        for article in row.get("article_item_ids", []):
            lines += ["关联专栏：`" + article + "`", ""]
        if row["content"].get("orig"):
            lines += ["## 转发内容", "", dynamic_text(row["content"]["orig"]), ""]
    return "\n".join(lines)


def review_markdown(row: dict, item: dict) -> str:
    if row["kind"] != "reading":
        raise ValueError("A review requires a reading record")
    if row.get("review_markdown"):
        return row["review_markdown"]
    lines = ["# " + item["title"] + "：校验稿", "", row.get("notes", ""), ""]
    if not row.get("paragraphs_match_text", True):
        lines += ["正文与段落参照有差异；以下保留原有段落参照，不代表逐字对齐。", ""]
    for index, paragraph in enumerate(row["paragraphs"], 1):
        lines += [f"## 段落 {index}", ""]
        if "start" in paragraph and "end" in paragraph:
            lines += [
                f"时间：{paragraph['start']} 至 {paragraph['end']}（{row['time_unit']}）",
                "",
            ]
        if paragraph.get("segment_ids"):
            lines += [
                "参照："
                + "、".join("`" + ref + "`" for ref in paragraph["segment_ids"]),
                "",
            ]
        lines += [
            "原文：" + paragraph.get("original_text", ""),
            "",
            "整理稿：" + paragraph["text"],
            "",
        ]
        for issue in paragraph.get("issues", []):
            lines += ["- 疑点：" + canonical(issue)]
        lines.append("")
    return "\n".join(lines)


def all_documents(root: Path):
    for table in DIRECTORIES:
        for row, _ in records(root, table):
            yield table, row


def catalog(root: Path) -> str:
    items = {r["id"]: r for r, _ in records(root, "items")}
    out = StringIO(newline="")
    fields = [
        "id",
        "item_id",
        "kind",
        "title",
        "identifiers",
        "human_reviewed",
        "requires_review",
        "path",
    ]
    writer = csv.DictWriter(out, fields, lineterminator="\n")
    writer.writeheader()
    for table, row in all_documents(root):
        item = items[row["item_id"]]
        flags = row.get("quality", {})
        writer.writerow(
            {
                "id": row["id"],
                "item_id": item["id"],
                "kind": row["kind"],
                "title": item["title"],
                "identifiers": canonical(item["identifiers"]),
                "human_reviewed": flags.get("human_reviewed"),
                "requires_review": flags.get("requires_review"),
                "path": f"data/{table}/{row['id']}.json",
            }
        )
    return out.getvalue()


def sqlite_export(root: Path, output: Path) -> None:
    """Rebuild a disposable SQLite search projection from canonical records."""
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.name + ".part")
    if partial.exists():
        raise ValueError(f"Unfinished SQLite export already exists: {partial}")
    connection = sqlite3.connect(partial)
    try:
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=OFF")
        for table in (*TABLES, *DIRECTORIES):
            connection.execute(
                f'CREATE TABLE "{table}"(id TEXT PRIMARY KEY, item_id TEXT, data TEXT NOT NULL)'
            )
        connection.execute(
            "CREATE VIRTUAL TABLE search USING fts5(id UNINDEXED, item_id UNINDEXED, kind UNINDEXED, text, tokenize='trigram')"
        )
        for table in (*TABLES, *DIRECTORIES):
            for row, _ in records(root, table):
                connection.execute(
                    f'INSERT INTO "{table}" VALUES(?,?,?)',
                    (row["id"], row.get("item_id"), canonical(row)),
                )
                if table in DIRECTORIES:
                    connection.execute(
                        "INSERT INTO search VALUES(?,?,?,?)",
                        (row["id"], row["item_id"], row["kind"], text_of(row)),
                    )
            connection.commit()
        connection.execute(
            "CREATE TABLE selections(name TEXT PRIMARY KEY, data TEXT NOT NULL)"
        )
        selection = read_json(root / "selections/training.json")
        connection.execute(
            "INSERT INTO selections VALUES(?,?)", ("training", canonical(selection))
        )
        connection.commit()
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity check failed")
    finally:
        connection.close()
    os.replace(partial, output)


def escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("\n", " ")
        .replace("\r", " ")
        .rstrip()
    )


def navigation(root: Path, check: bool = False) -> dict:
    counts = validate(root)
    items = {r["id"]: r for r, _ in records(root, "items")}
    by_item = defaultdict(list)
    for table, row in all_documents(root):
        by_item[row["item_id"]].append((table, row["id"]))
    children = defaultdict(list)
    for row in items.values():
        if row.get("parent_id"):
            children[row["parent_id"]].append(row)
    output = {}
    intro = "此目录由 `python tools/corpus.py generate` 生成。所有结果分别列出，排序不代表审核质量。\n\n"

    def links(iid):
        return (
            " · ".join(
                f"[{table}:{rid[2:10]}](../../data/{table}/{rid}.json)"
                for table, rid in sorted(by_item[iid])
            )
            or "仅元数据"
        )

    for group, title, kinds in [
        ("videos", "视频与分段", {"video"}),
        ("recordings", "独立录音", {"recording"}),
        ("dynamics", "动态", {"dynamic"}),
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
                "## " + escape(row["title"] or row["id"]),
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
                lines += ["- " + escape(child["title"]) + "：" + links(child["id"])]
            lines.append("")
        output[f"docs/catalog/{group}.md"] = "\n".join(lines).rstrip() + "\n"
    groups = {
        "video": "videos",
        "part": "videos",
        "recording": "recordings",
        "dynamic": "dynamics",
        "article": "articles",
        "person": "people",
    }
    lines = ["# 文集、合集与系列", "", intro]
    for row, _ in sorted(
        records(root, "collections"), key=lambda pair: (pair[0]["title"], pair[0]["id"])
    ):
        lines += [
            "## " + escape(row["title"]),
            "",
            "集合：`" + row["id"] + "`（" + row["kind"] + "）",
            "",
        ]
        for member in row["members"]:
            entry = items[member["item_id"]]
            group = groups[entry["kind"]]
            target = entry.get("parent_id", entry["id"])
            lines.append(
                f"{member['position']}. [{escape(entry['title'])}]({group}.md#{target})"
            )
        lines.append("")
    output["docs/catalog/collections.md"] = "\n".join(lines).rstrip() + "\n"
    output["docs/INDEX.md"] = (
        "# 数据目录\n\n由 `python tools/corpus.py generate` 生成。计数见 [counts.json](counts.json)。\n\n"
        + "\n".join(
            [
                "- [视频与分段](catalog/videos.md)",
                "- [独立录音](catalog/recordings.md)",
                "- [动态](catalog/dynamics.md)",
                "- [专栏](catalog/articles.md)",
                "- [文集、合集与系列](catalog/collections.md)",
                "- [人物资料](catalog/people.md)",
                "",
                f"基础转录 {counts['transcripts']} 条；整理结果 {counts['readings']} 条；动态 {counts['dynamics']} 条；专栏 {counts['articles']} 篇。",
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
