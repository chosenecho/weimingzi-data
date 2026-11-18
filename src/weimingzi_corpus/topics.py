"""Rebuildable thematic selections, separate from source-platform collections."""

from __future__ import annotations

import unicodedata
from pathlib import Path

from .coverage import CoverageIndex, LAYERS, counts
from .records import read_json


def generate_topic_catalog(root: Path, check: bool = False) -> dict:
    """Check the optional lookup rules and rebuild their separate navigation."""
    if not (root / "selections/topics.json").is_file():
        return {}
    topics = definitions(root)
    index = CoverageIndex(root)
    value = render_topic_catalog(index, topics)
    path = root / "docs/catalog/topics.md"
    if check:
        if not path.is_file() or path.read_text(encoding="utf-8") != value:
            raise ValueError("Generated file is stale: docs/catalog/topics.md; run generate")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8", newline="\n")
    return {
        "topics": len(topics),
        "topic_entries": sum(len(select_topic(index, topic)) for topic in topics),
    }


def normalized(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).split()).casefold()


def string_observations(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for nested in value:
            yield from string_observations(nested)


def definitions(root: Path) -> list[dict]:
    document = read_json(root / "selections/topics.json")
    if document.get("format") != "thematic-index/v1":
        raise ValueError("Unsupported thematic index format")
    topics = document.get("topics")
    if not isinstance(topics, list):
        raise ValueError("Topic definitions must be a list")
    seen = set()
    for topic in topics:
        if (
            not isinstance(topic, dict)
            or not isinstance(topic.get("id"), str)
            or not topic["id"]
            or topic["id"] in seen
        ):
            raise ValueError("Invalid or duplicate topic ID")
        seen.add(topic["id"])
        if not isinstance(topic.get("title"), str) or not topic["title"]:
            raise ValueError("Topic requires a title")
        rules = topic.get("rules")
        if not isinstance(rules, dict):
            raise ValueError("Topic requires selection rules")
        for field in ("collection_ids", "title_prefixes", "exact_tags"):
            if not isinstance(rules.get(field), list) or any(
                not isinstance(x, str) or not x for x in rules[field]
            ):
                raise ValueError("Invalid topic rule: " + field)
        if type(rules.get("include_chapter_supplements")) is not bool:
            raise ValueError("Topic supplement rule must be boolean")
        if not isinstance(topic.get("manual_inclusions", []), list):
            raise ValueError("Manual inclusions must be a list")
        for manual in topic.get("manual_inclusions", []):
            if (
                not isinstance(manual, dict)
                or manual.get("role")
                not in {"related", "core", "chapter_supplement", "introductory"}
                or not isinstance(manual.get("item_id"), str)
                or not isinstance(manual.get("evidence"), str)
                or not manual["evidence"]
            ):
                raise ValueError(
                    "Manual topic inclusion requires item, role and evidence"
                )
    return topics


def select_topic(index: CoverageIndex, topic: dict) -> list[dict]:
    rules = topic["rules"]
    selected = {}
    priorities = {"related": 0, "core": 1, "chapter_supplement": 2, "introductory": 3}

    def add(item_id, role, reason):
        if item_id not in index.items:
            raise ValueError("Unknown thematic item: " + item_id)
        item = index.items[item_id]
        entry = selected.setdefault(
            item_id,
            {
                "item_id": item_id,
                "title": item["title"],
                "role": role,
                "inclusion_reasons": [],
            },
        )
        if priorities[role] > priorities[entry["role"]]:
            entry["role"] = role
        if reason not in entry["inclusion_reasons"]:
            entry["inclusion_reasons"].append(reason)

    # Collections share the item namespace; kind selects their member semantics.
    collections = {r["id"]: r for r in index.collections}
    for collection_id in rules["collection_ids"]:
        if collection_id not in collections:
            raise ValueError("Unknown topic collection: " + collection_id)
        collection = collections[collection_id]
        for member in collection["members"]:
            add(
                member["item_id"],
                "core",
                {
                    "rule": "source_collection",
                    "collection_id": collection_id,
                    "title": collection["title"],
                    "member": member,
                },
            )
    for item in sorted(index.items.values(), key=lambda r: r["id"]):
        if item["kind"] not in {"video", "audio_recording"}:
            continue
        title = normalized(item["title"])
        for prefix in rules["title_prefixes"]:
            if title.startswith(normalized(prefix)):
                add(
                    item["id"],
                    "core",
                    {
                        "rule": "normalized_title_prefix",
                        "prefix": prefix,
                        "observed_title": item["title"],
                    },
                )
        for tag in sorted(
            set(string_observations(item.get("metadata", {}).get("tags", [])))
        ):
            for expected in rules["exact_tags"]:
                if normalized(tag) == normalized(expected):
                    add(
                        item["id"],
                        "related",
                        {
                            "rule": "exact_tag",
                            "expected_tag": expected,
                            "observed_tag": tag,
                            "field": "metadata.tags",
                        },
                    )
    for manual in topic.get("manual_inclusions", []):
        if manual["role"] not in priorities or not manual.get("evidence"):
            raise ValueError("Manual topic inclusion requires role and evidence")
        add(manual["item_id"], manual["role"], {**manual, "rule": "manual_inclusion"})
    # A selected parent already covers its parts; retain their exact match reasons.
    for item_id in list(selected):
        parent = index.items[item_id].get("parent_id")
        if parent in selected:
            entry = selected.pop(item_id)
            for reason in entry["inclusion_reasons"]:
                add(parent, entry["role"], {**reason, "matched_item_id": item_id})
    if rules["include_chapter_supplements"]:
        scope = {i for item_id in selected for i in index.family(item_id)}
        for item in sorted(index.items.values(), key=lambda r: r["id"]):
            for relation in item.get("relations", []):
                if (
                    relation["kind"] == "chapter_supplement_not_audio_identity"
                    and relation["target_item_id"] in scope
                ):
                    add(
                        item["id"],
                        "chapter_supplement",
                        {
                            "rule": "explicit_chapter_supplement",
                            "source_item_id": item["id"],
                            "relation": relation,
                        },
                    )
    return sorted(
        selected.values(), key=lambda r: (r["role"], r["title"], r["item_id"])
    )


def topic_report(index: CoverageIndex, topic: dict, include_records=False) -> dict:
    entries = select_topic(index, topic)
    summary = {layer: [] for layer in LAYERS}
    for entry in entries:
        entry["coverage"] = index.report(
            entry["item_id"], include_records=include_records
        )
        for layer in LAYERS:
            summary[layer].extend(entry["coverage"]["layers"][layer]["records"])
    return {
        "format": "topic-coverage/v1",
        "topic": topic,
        "entries": entries,
        "counts": {layer: counts(rows) for layer, rows in summary.items()},
    }


def render_topic_catalog(index: CoverageIndex, topics: list[dict]) -> str:
    from .exports import escape_markdown_label

    escape = escape_markdown_label
    lines = [
        "# 专题索引",
        "",
        "由 selections/topics.json 规则生成；与来源平台系列分别维护，不改写原题名、标签或集合成员。",
        "",
        "core 表示来源系列或题名前缀命中，related 表示仅标签命中，introductory 是有依据的导入材料，chapter_supplement 是章节补充。角色只说明纳入规则。",
        "",
        "[查询与完整导出](../QUERY.md#专题查询) · [分层覆盖定义](../QUERY.md#找稿与关联)",
        "",
    ]
    labels = dict(zip(LAYERS, ["直接关联", "跨来源引用", "同音频", "章节补充"]))
    for topic in topics:
        entries = select_topic(index, topic)
        lines += ["## " + escape(topic["title"]), "", "专题：" + topic["id"], ""]
        for entry in entries:
            lines += [
                "### " + escape(entry["title"]),
                "",
                "条目：" + entry["item_id"] + "；纳入角色：" + entry["role"],
                "",
            ]
            for reason in entry["inclusion_reasons"]:
                rule = reason["rule"]
                if rule == "source_collection":
                    text = (
                        "来源系列："
                        + reason["title"]
                        + "（"
                        + reason["collection_id"]
                        + "）"
                    )
                elif rule == "normalized_title_prefix":
                    text = "规范化题名前缀：" + reason["prefix"]
                elif rule == "exact_tag":
                    text = "精确标签：" + reason["observed_tag"]
                elif rule == "manual_inclusion":
                    text = "人工纳入依据：" + reason["evidence"]
                else:
                    text = (
                        "章节关系："
                        + reason["relation"]["target_item_id"]
                        + "；"
                        + reason["relation"].get("evidence", "")
                    )
                lines.append("- " + escape(text))
            lines.append("")
            report = index.report(entry["item_id"])
            for layer in LAYERS:
                rows = report["layers"][layer]["records"]
                c = report["layers"][layer]["counts"]
                lines += [
                    "**"
                    + labels[layer]
                    + "**：基础转录 "
                    + str(c["transcripts"])
                    + "；整理稿 "
                    + str(c["edited_transcripts"])
                    + "；完成且非空非填充词候选 "
                    + str(c["complete_text_candidates"])
                    + "；其中全文人工审核 "
                    + str(c["human_reviewed_complete_texts"]),
                    "",
                ]
                lines += [
                    " · ".join(
                        "[" + r["id"] + "](../../" + r["record_path"] + ")"
                        for r in rows
                    )
                    or "无文稿记录",
                    "",
                ]
    return chr(10).join(lines).rstrip() + chr(10)
