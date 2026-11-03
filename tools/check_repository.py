#!/usr/bin/env python3
"""Validate current archive indexes and regenerate repository navigation."""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

from fetch_media import ROOT, COLLECTIONS, load_manifest, target_path, digest

GENERATED = "<!-- generated: tools/check_repository.py -->"
STATS_START = "<!-- archive-stats:start -->"
STATS_END = "<!-- archive-stats:end -->"
PAGE_SIZE = 200
SOURCES = [
    "metadata/catalog.csv", "metadata/supplemental-audio.csv",
    "metadata/missing-products.csv", "metadata/training-source.json",
    "metadata/sources/cola-videos.json", "data/user-content/summary.json",
    *COLLECTIONS.values(),
]

def require(condition, message):
    if not condition:
        raise ValueError(message)

def read_json(name):
    return json.loads(target_path(name).read_text(encoding="utf-8-sig"))

def read_csv(name):
    with target_path(name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))

def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"

def collect():
    catalog = read_csv("metadata/catalog.csv")
    videos = {p.name for p in (ROOT / "data/videos").iterdir() if p.is_dir()}
    source_ids = {row["id"] for row in read_json("metadata/sources/cola-videos.json")}
    require(videos == source_ids == {row["bvid"] for row in catalog}, "Video directory/source/catalog sets differ")
    require(all(re.fullmatch(r"BV[0-9A-Za-z]{10}", bv) for bv in videos), "Invalid BV format")
    parts = [(row["bvid"], row["page"]) for row in catalog if row["page"]]
    youtube = [row["youtube_id"] for row in catalog if row["youtube_id"]]
    require(len(parts) == len(set(parts)), "Duplicate Bilibili part")
    require(len(youtube) == len(set(youtube)), "Duplicate YouTube track")
    for row in catalog:
        require(target_path(row["folder"]).is_dir(), "Missing catalog folder: " + row["folder"])
        if row["recommended_text"]:
            require(target_path(row["recommended_text"]).is_file(), "Missing recommended text: " + row["recommended_text"])
    training = read_json("metadata/training-source.json")
    require(training["total"] == len(training["entries"]), "Training count mismatch")
    selected = {(row["bvid"], str(row["page"])) for row in training["entries"]}
    require(len(selected) == len(training["entries"]) and selected.issubset(set(parts)), "Invalid training selection")
    user = read_json("data/user-content/summary.json")
    dynamics = len(list((ROOT / "data/user-content/dynamics").glob("*.json")))
    articles = len(list((ROOT / "data/user-content/articles").glob("*.txt")))
    lists = len(list((ROOT / "data/user-content/article-lists").glob("*.json")))
    seasons = len(list((ROOT / "data/user-content/channels").glob("season-*.md")))
    series = len(list((ROOT / "data/user-content/channels").glob("series-*.md")))
    with (ROOT / "data/user-content/videos.jsonl").open(encoding="utf-8") as stream:
        user_videos = sum(bool(line.strip()) for line in stream)
    require((dynamics, articles, lists, seasons, series, user_videos) == (
        user["dynamics_browser_saved"], user["article_bodies_saved"], user["article_lists_browser_saved"],
        user["seasons"], user["series"], user["videos_browser_saved"]), "User-content counts disagree with files")
    audio, assets = [], []
    for path in COLLECTIONS.values():
        manifest = load_manifest(path)
        audio.extend(manifest["files"])
        assets.extend(manifest["assets"])
        require(manifest["audio_count"] == len(manifest["files"]), "Media audio_count mismatch")
        require(manifest["total_audio_bytes"] == sum(row["bytes"] for row in manifest["files"]), "Media byte count mismatch")
    require(len(audio) == len({row["path"] for row in audio}), "Duplicate audio restore destination")
    for row in audio:
        path = target_path(row["path"])
        require(path.is_file() or path.with_name(path.name + ".download.md").is_file(), "Missing audio download entry: " + row["path"])
    counts = {
        "video_directories": len(videos), "catalog_rows": len(catalog),
        "bilibili_parts": len(parts), "youtube_tracks": len(youtube),
        "training_entries": len(training["entries"]),
        "supplemental_audio": len(read_csv("metadata/supplemental-audio.csv")),
        "dynamics": dynamics, "article_bodies": articles, "article_lists": lists,
        "seasons": seasons, "series": series, "user_video_index": user_videos,
        "audio_files": len(audio), "audio_assets": len(assets),
        "audio_bytes": sum(row["bytes"] for row in audio),
        "archive_bytes": sum(asset["bytes"] for asset in assets),
        "pending_missing_products": len(read_csv("metadata/missing-products.csv")),
    }
    summary = {
        "schema": "weimingzi-repository-summary-v2",
        "counts": counts,
        "snapshot_times": {"user_content_exported_at": user["exported_at"]},
        "source_sha256": {path: digest(target_path(path)) for path in SOURCES},
        "review_notice": "Counts describe available records, not human-approved content.",
    }
    return catalog, videos, training, summary

def stats_table(counts):
    c = counts
    return "\n".join([
        "| 内容 | 数量 | 核验入口 |", "| --- | ---: | --- |",
        f'| 视频目录 | {c["video_directories"]:,} 个 BV | [视频索引](docs/VIDEO-INDEX.md) |',
        f'| B 站分 P | {c["bilibili_parts"]:,} | [catalog.csv](metadata/catalog.csv) |',
        f'| YouTube 音轨 | {c["youtube_tracks"]:,} | [catalog.csv](metadata/catalog.csv) |',
        f'| 训练选稿 | {c["training_entries"]:,} 份 | [训练索引](metadata/training-source.json) |',
        f'| 动态／专栏正文 | {c["dynamics"]:,} 条／{c["article_bodies"]:,} 篇 | [用户内容](data/user-content/README.md) |',
        f'| 文集／合集／系列 | {c["article_lists"]:,}／{c["seasons"]:,}／{c["series"]:,} | [用户内容](data/user-content/README.md) |',
        f'| 已发布音频 | {c["audio_files"]:,} 份，{c["audio_assets"]:,} 个分卷 | [媒体清单](metadata/media/) |',
        f'| 用户补充音频 | {c["supplemental_audio"]:,} 份 | [补充音频](data/supplemental-audio/README.md) |',
    ]) + "\n"

def escaped(value):
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("<", "&lt;").replace(">", "&gt;").replace("[", "\\[").replace("]", "\\]")

def generated_files(catalog, videos, summary):
    groups = defaultdict(list)
    for row in catalog:
        groups[row["bvid"]].append(row)
    ordered = sorted(videos)
    pages = [ordered[i:i + PAGE_SIZE] for i in range(0, len(ordered), PAGE_SIZE)]
    main = [
        GENERATED, "# 视频目录", "",
        "按 BV 排序分页。按标题、分 P、来源或复核状态检索，可下载 [catalog.csv](../metadata/catalog.csv)。",
        "计数来自当前机器索引，见 [dataset-summary.json](../metadata/dataset-summary.json)。",
        "", "| 页 | BV 范围 | 条目 |", "| --- | --- | ---: |",
    ]
    output = {}
    for number, bvs in enumerate(pages, 1):
        filename = f"{number:02d}.md"
        main.append(f"| [{number:02d}](videos/{filename}) | {bvs[0]} 至 {bvs[-1]} | {len(bvs)} |")
        links = ["[目录](../VIDEO-INDEX.md)"]
        if number > 1:
            links.append(f"[上一页]({number - 1:02d}.md)")
        if number < len(pages):
            links.append(f"[下一页]({number + 1:02d}.md)")
        navigation = " · ".join(links)
        lines = [GENERATED, f"# 视频目录 · {number:02d}", "", navigation, "",
                 "| BV | 标题 | 分 P | YouTube |", "| --- | --- | ---: | ---: |"]
        for bv in bvs:
            metadata = read_json(f"data/videos/{bv}/metadata.json")
            rows = groups[bv]
            parts = len({row["page"] for row in rows if row["page"]})
            youtube = len({row["youtube_id"] for row in rows if row["youtube_id"]})
            lines.append(f'| [{bv}](../../data/videos/{bv}/README.md) | {escaped(metadata["title"])} | {parts} | {youtube} |')
        lines.extend(["", navigation, ""])
        output[f"docs/videos/{filename}"] = "\n".join(lines)
    main.extend(["", "返回[仓库首页](../README.md)。", ""])
    output["docs/VIDEO-INDEX.md"] = "\n".join(main)
    output["metadata/dataset-summary.json"] = json_text(summary)
    return output

def check_generated(output, summary, update):
    for name, expected in output.items():
        path = target_path(name)
        if update:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected.encode("utf-8"))
        require(path.is_file() and path.read_text(encoding="utf-8") == expected,
                f"Generated file is stale: {name}; run --update-index")
    for path in (ROOT / "docs/videos").glob("*.md"):
        if path.relative_to(ROOT).as_posix() not in output:
            require(update and path.read_text(encoding="utf-8").startswith(GENERATED), "Unexpected video-index page")
            path.unlink()
    path = ROOT / "README.md"
    original = path.read_text(encoding="utf-8")
    require(original.count(STATS_START) == 1 and original.count(STATS_END) == 1, "Missing README stats markers")
    before, rest = original.split(STATS_START, 1)
    _, after = rest.split(STATS_END, 1)
    expected = before + STATS_START + "\n" + stats_table(summary["counts"]) + STATS_END + after
    if update:
        path.write_bytes(expected.encode("utf-8"))
    require(path.read_text(encoding="utf-8") == expected, "README counts are stale; run --update-index")

def check_links():
    paths = [*ROOT.glob("*.md"), *(ROOT / "docs").glob("*.md"), *(ROOT / "docs/videos").glob("*.md")]
    count = 0
    for path in paths:
        text = path.read_text(encoding="utf-8-sig")
        text = re.sub(r"^```.*?^```[^\n]*", "", text, flags=re.M | re.S)
        require(not re.search(r"^(<<<<<<<|=======|>>>>>>>)", text, re.M), f"Conflict marker: {path}")
        for match in re.finditer(r"(?<!\\)\[[^\]\n]*\]\(([^\n)]+)\)", text):
            href = match.group(1).strip("<>")
            parts = urlsplit(href)
            if parts.scheme or parts.netloc or not parts.path:
                continue
            dest = (path.parent / unquote(parts.path)).resolve()
            require(dest.is_relative_to(ROOT.resolve()), f"Link escapes repository: {path}: {href}")
            require(dest.exists(), f"Broken link: {path.relative_to(ROOT)}: {href}")
            count += 1
    return count

def check_training(training, verify_hashes):
    checked = set()
    for row in training["entries"]:
        require(bool(row.get("quality_status")), "Training source has no review status")
        for path_key, hash_key in [("paths", "sha256"), ("original_paths", "original_sha256")]:
            for key, name in row[path_key].items():
                path = target_path(name)
                require(path.is_file(), "Missing training source: " + name)
                if verify_hashes and name not in checked:
                    require(digest(path) == row[hash_key][key], "Training hash mismatch: " + name)
                    checked.add(name)
    return len(checked)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update-index", action="store_true")
    parser.add_argument("--verify-hashes", action="store_true")
    args = parser.parse_args(argv)
    catalog, videos, training, summary = collect()
    check_generated(generated_files(catalog, videos, summary), summary, args.update_index)
    links = check_links()
    hashes = check_training(training, args.verify_hashes)
    print(json_text({"status": "ok", "counts": summary["counts"], "navigation_links_checked": links,
                     "training_files_hashed": hashes}), end="")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as error:
        print(f"Repository check failed: {error}", file=sys.stderr)
        sys.exit(1)
