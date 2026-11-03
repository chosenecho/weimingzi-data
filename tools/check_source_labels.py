#!/usr/bin/env python3
"""Check or regenerate supplemental-source labels without editing source evidence."""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import io
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
START = "<!-- source-labels:start -->"
END = "<!-- source-labels:end -->"
BACKFILL = "provenance/asr/2026-11-03-missing-local"
CATEGORIES = {
    "user_audio_supplement": "用户补充 · 仅音频来源",
    "youtube_supplement": "YouTube 补充音轨",
    "bilibili_asr_backfill": "B 站后补 ASR",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def local_path(root, name):
    require(bool(name) and "\\" not in name and ":" not in name, f"Invalid repository path: {name}")
    path = (root / name).resolve()
    require(path.is_relative_to(root.resolve()), f"Path escapes repository: {name}")
    return path


def read_json(root, name):
    return json.loads(local_path(root, name).read_text(encoding="utf-8-sig"))


def read_csv(root, name):
    return list(csv.DictReader(io.StringIO(local_path(root, name).read_text(encoding="utf-8-sig"))))


def flag(value):
    require(value in ("True", "False"), f"Expected explicit boolean, got {value!r}")
    return value == "True"


def collect(root):
    catalog = read_csv(root, "metadata/catalog.csv")
    by_folder = {r["folder"]: r for r in catalog}
    require(len(by_folder) == len(catalog), "Duplicate catalog folder")
    rows = []

    def add(row, source, current):
        row["audio_sha256"] = source.get("audio_sha256", source.get("sha256"))
        require(bool(re.fullmatch(r"[0-9a-f]{64}", row["audio_sha256"] or "")), "Invalid audio SHA-256")
        row["quality"] = {
            "recognized_text_empty": flag(current["recognized_text_empty"]),
            "requires_review": flag(current["requires_review"]),
            "timed_exports_available": flag(current["timed_exports_available"]),
            "human_reviewed": False,
            "ai_draft_available": bool(current["ai_draft_available"]),
        }
        row["recommended_text"] = current["recommended_text"]
        require(local_path(root, row["recommended_text"]).is_file(), "Missing recommended text")
        rows.append(row)

    for current in read_csv(root, "metadata/audio.csv"):
        folder = current["folder"]
        evidence = folder + "/source.json"
        source = read_json(root, evidence)
        require(source["source_kind"] == "user-supplied-audio", "Unexpected supplemental source")
        require(source["sha256"] == current["audio_sha256"], "Supplemental audio identity mismatch")
        require(not flag(current["human_reviewed"]), "Update the source-label review policy for a reviewed item")
        require((source["related_bvid"] or "") == current["related_bvid"], "Supplemental BV mapping mismatch")
        row = {
            "record_id": "audio:" + current["audio_sha256"],
            "category": "user_audio_supplement", "source_platform": "user_supplied",
            "input_media": "audio_only", "batch_id": "user-audio-2026-11-03",
            "title": current["title"], "folder": folder, "source_record": evidence,
            "batch_record": "data/audio/入库回执.json",
            "source_url": None, "source_received_at": source["received_at"],
            "reference_bvid": source["related_bvid"], "reference_page": None,
            "youtube_id": None, "mapping_scope": source["relation"] or "unconfirmed",
        }
        add(row, source, {**current, "recognized_text_empty": "False",
                          "ai_draft_available": bool(current["ai_revision_id"])})

    for current in catalog:
        if not current["youtube_id"]:
            continue
        folder = current["folder"]
        evidence = folder + "/source.json"
        source = read_json(root, evidence)
        require(source["youtube_id"] == current["youtube_id"] and
                source["reference_bvid"] == current["bvid"], "YouTube identity/mapping mismatch")
        row = {
            "record_id": "youtube:" + source["youtube_id"],
            "category": "youtube_supplement", "source_platform": "youtube",
            "input_media": "audio_track", "batch_id": "youtube-missing-20261103",
            "title": source["title"], "folder": folder, "source_record": evidence,
            "batch_record": "metadata/sources/youtube-audit.json",
            "source_url": source["youtube_url"], "source_received_at": None,
            "reference_bvid": current["bvid"], "reference_page": None,
            "youtube_id": source["youtube_id"],
            "mapping_scope": "video_reference_not_part_or_audio_identity",
        }
        add(row, source, {**current, "requires_review": current["youtube_requires_review"],
                          "ai_draft_available": int(current["complete_ai_revisions"]) > 0})

    for historical in read_csv(root, BACKFILL + "/分P目录.csv"):
        bv, page = historical["bvid"], int(historical["page"])
        folder = f"data/bilibili/{bv}/P{page:03d}"
        evidence = folder + "/原始转录/asr-cloud-qwen-audio-3.1-asr-flash-20261103/source.json"
        source = read_json(root, evidence)
        current = by_folder[folder]
        require(source["bvid"] == bv and source["page"] == page, "Bilibili part identity mismatch")
        row = {
            "record_id": f"bilibili:{bv}:p{page}",
            "category": "bilibili_asr_backfill", "source_platform": "bilibili",
            "input_media": "audio_track", "batch_id": "missing-local-2026-11-03",
            "title": source["part_title"], "folder": folder, "source_record": evidence,
            "batch_record": BACKFILL + "/分P目录.csv",
            "source_url": source["source_url"], "source_received_at": None,
            "source_downloaded_at": source["downloaded_at"],
            "reference_bvid": bv, "reference_page": page, "youtube_id": None,
            "mapping_scope": "bilibili_part",
        }
        add(row, source, {**current, "requires_review": historical["requires_review"],
                          "ai_draft_available": int(current["complete_ai_revisions"]) > 0})

    require(len(rows) == len({r["record_id"] for r in rows}), "Duplicate source-label identity")
    require(len(rows) == len({r["folder"] for r in rows}), "Duplicate source-label folder")
    return sorted(rows, key=lambda r: (r["category"], r["record_id"]))


def link(from_file, to_file):
    return Path(os.path.relpath(to_file, Path(from_file).parent)).as_posix()


def escaped(value):
    return value.replace("|", "\\|").replace("\n", " ").replace("[", "\\[").replace("]", "\\]")


def state(row):
    q = row["quality"]
    value = "无识别正文；无 AI 稿" if q["recognized_text_empty"] else (
        "ASR + AI 草稿" if q["ai_draft_available"] else "ASR；无 AI 稿")
    if q["requires_review"]:
        value += "；需复核"
    return value


def document(rows):
    lines = ["<!-- generated: tools/check_source_labels.py -->", "# 补充材料与来源标记", "",
             "机器清单见 [source-labels.json](../metadata/source-labels.json)，按 `folder` 与 [catalog.csv](../metadata/catalog.csv) 或 [audio.csv](../metadata/audio.csv) 关联。每条都有音频 SHA-256、来源记录和批次依据。", "",
             "`audio_only` 表示收到的材料只有音频，不表示现在没有文稿；`audio_track` 表示从平台视频取得的音轨。来源类别与正文、字幕、AI 校对、人工复核状态分别记录，标签不表示训练批准。", "",
             "## 用户补充的仅音频材料", "",
             "用户提供 MP3 后入库，当前均有 ASR 转录与 AI 校对稿，未经人工审核。接收时间见各条 `source.json`；入库依据见[回执](../data/audio/入库回执.json)。`asr-cloud` 是识别方式，材料来源为 `user_supplied`。", "",
             "| 材料 | 标记 | BV 关系 | 当前产物 |", "| --- | --- | --- | --- |"]
    for row in rows:
        if row["category"] == "user_audio_supplement":
            relation = row["reference_bvid"] + "：同章节补充" if row["reference_bvid"] else "无已确认 BV 对应"
            lines.append(f'| [{escaped(row["title"])}](../{row["folder"]}/README.md) | `user_audio_supplement` · `audio_only` | {relation} | {state(row)} |')
    lines += ["", "神创论的 BV 关联依据是用户文件名章节与旧条目标题，不证明音轨相同；自然神论与神义论不补造 BV。依据见各条[来源记录](../data/audio/README.md)。", "",
              "## YouTube 补充音轨", "",
              "以下材料从 YouTube 音轨识别，按原始清单的 BV 参考关系归档；不表示从 B 站下载，也不表示与某个分 P 或音轨逐一相同。批次见 [youtube-index.csv](../metadata/sources/youtube-index.csv) 和[识别审计](../metadata/sources/youtube-audit.json)。", "",
              "| 材料 | YouTube ID | 参考 BV | 当前产物 |", "| --- | --- | --- | --- |"]
    for row in rows:
        if row["category"] == "youtube_supplement":
            lines.append(f'| [{escaped(row["title"])}](../{row["folder"]}/README.md) | [{row["youtube_id"]}]({row["source_url"]}) | {row["reference_bvid"]} | {state(row)} |')
    lines += ["", "本表全部标记为 `youtube_supplement` · `audio_track`。有正文的条目有 AI 草稿，均未经人工审核；AI 校对批次见[处理记录](../provenance/ai-proofreading/2026-11-03-opencode-go/README.md)。时间戳异常和未返回词语的区间保留在审计与原始响应中。", "",
              "`EMkOxG97L-w` 无识别正文、未做 AI 校对；历史静音检测结果见 [audio-validation.json](../data/youtube/EMkOxG97L-w/audio-validation.json)。用户补充的有声神创论音频另列，未覆盖该音轨。", "",
              "## 后补的 B 站 ASR", "",
              "首次汇总时没有本地产物，后续从 B 站取得音频并补跑云识别。批次、下载来源与复核区间见[补跑记录](../provenance/asr/2026-11-03-missing-local/README.md)；标记仅作用于下列分 P。", "",
              "| 材料 | BV / 分 P | 当前产物 |", "| --- | --- | --- |"]
    for row in rows:
        if row["category"] == "bilibili_asr_backfill":
            lines.append(f'| [{escaped(row["title"])}](../{row["folder"]}/README.md) | {row["reference_bvid"]} P{row["reference_page"]} | {state(row)} |')
    lines += ["", "本表全部标记为 `bilibili_asr_backfill` · `audio_track`，未经人工审核。`BV1F7t16iEW6` P1 保留时间戳异常，本条没有 SRT/VTT；不要通过排序或截断时间戳补造字幕。", "",
              "## 给 AI 与数据处理脚本", "",
              "- 读取 `source-labels.json` 的 `schema` 和 `records`，以 `record_id` 为稳定身份、`folder` 为关联键；不要只看父目录里的 BV 猜来源。清单只覆盖这里列出的补充批次，未列出条目不能据此推定来源或人工审核状态。",
              "- 保留 `category`、`source_platform`、`input_media`、`batch_id`、`source_record` 和 `audio_sha256`；正文质量另看 `quality` 和原记录。导出训练集或知识库时随 lineage 保留来源。",
              "- `source_received_at` 取自音频接收记录，`source_downloaded_at` 取自下载记录；批次名中的日期不是视频发表日，也不一定是 Git 提交日。YouTube 批次已有于首次汇总，后续另加 AI 校对；不要把 AI 校对完成时间当作抓取时间。",
              "- 来源标记位于 README 的 `source-labels` 区块；源响应、历史清单、AI 文稿与训练选稿均未因加标签而改写。", "",
              "维护标记：在仓库根目录运行 `python -X utf8 tools/check_source_labels.py --update`，再运行不带 `--update` 的同一命令检查。新增批次应补充明确的来源依据；检查不会调用模型、下载音频或改生产状态。", "",
              "返回[仓库首页](../README.md) · [批次与校验](PROVENANCE.md)。", ""]
    return "\n".join(lines)


def with_block(original, block):
    if START in original or END in original:
        require(original.count(START) == original.count(END) == 1, "Malformed source-label markers")
        before, rest = original.split(START)
        _, after = rest.split(END)
        return before + block + after
    title, sep, rest = original.partition("\n")
    require(title.startswith("# ") and bool(sep), "Expected a README title")
    return title + "\n\n" + block + "\n\n" + rest.lstrip("\n")


def expected_files(root, rows):
    output = {"metadata/source-labels.json": json.dumps({
        "schema": "weimingzi-source-labels-v1", "records": rows,
    }, ensure_ascii=False, indent=2) + "\n", "docs/SOURCE-LABELS.md": document(rows)}
    for row in rows:
        name = row["folder"] + "/README.md"
        path = local_path(root, name)
        original = path.read_text(encoding="utf-8") if path.exists() else "# " + row["title"] + "\n"
        text = {
            "user_audio_supplement": "用户提供的 MP3，接收时仅有音频；当前转录与 AI 草稿另见本目录。",
            "youtube_supplement": "本目录为 YouTube 抓取音轨及转录。BV 仅作视频级参考，不证明分 P 或音轨相同。",
            "bilibili_asr_backfill": "本分 P 属于首次汇总后的 B 站云 ASR 补跑批次。",
        }[row["category"]]
        block = "\n".join([START, f'**来源标记：`{row["category"]}` · `{row["input_media"]}`**', "", text, "",
            f'[来源依据]({link(name, row["source_record"])}) · [批次依据]({link(name, row["batch_record"])}) · [补充来源清单]({link(name, "docs/SOURCE-LABELS.md")})', END])
        output[name] = with_block(original, block)
    groups = defaultdict(list)
    for row in rows:
        if row["reference_bvid"]:
            groups[row["reference_bvid"]].append(row)
    for bv, items in groups.items():
        name = f"data/bilibili/{bv}/README.md"
        lines = [START, "**补充来源标记**", ""]
        for row in items:
            lines.append(f'- `{row["category"]}`：[具体材料]({link(name, row["folder"] + "/README.md")})（{CATEGORIES[row["category"]]}）。')
        lines += ["", f'[来源类别与映射边界]({link(name, "docs/SOURCE-LABELS.md")})。标签作用于所链接材料。', END]
        output[name] = with_block(local_path(root, name).read_text(encoding="utf-8"), "\n".join(lines))
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args(argv)
    rows = collect(ROOT)
    for name, expected in expected_files(ROOT, rows).items():
        path = local_path(ROOT, name)
        if args.update:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Only README label blocks and generated indexes change; preserve existing newline convention.
            newline = b"\r\n" if path.exists() and b"\r\n" in path.read_bytes() else b"\n"
            path.write_bytes(expected.replace("\n", newline.decode()).encode("utf-8"))
        require(path.exists() and path.read_text(encoding="utf-8") == expected,
                f"Source labels are stale: {name}; run tools/check_source_labels.py --update")
    print(json.dumps({"status": "ok", "labelled_records": len(rows),
                      "categories": {k: sum(r["category"] == k for r in rows) for k in CATEGORIES}}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as error:
        print(f"Source-label check failed: {error}", file=sys.stderr)
        sys.exit(1)
