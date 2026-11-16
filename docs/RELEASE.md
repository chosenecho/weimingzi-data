# 发布视图

发布视图（release view）是把 `data/` 投影成「每个条目一份整理稿、已应用人工确认」的段落表，供检索、导出和后续数据集使用。它是一层只读投影，不是第二份真源：`selections/release.json` 只存指针，段落正文每次从 `data/edited_transcripts/` 重建。

发布视图不等于人工复核。段落上的 `issue_state` 来自整理稿自带的模型校对标注；仓库中没有任何记录声明 `is_fully_human_reviewed=true`。

## 为什么需要这一层

同一段音视频可能有多份整理稿（重跑、参照稿、残稿）。实测 2021 份整理稿覆盖 1989 个条目，其中 30 个条目有 2–4 份稿（1 个条目 4 份，29 个条目 2 份）。直接按整理稿检索会把同一段内容重复返回，且人工确认可能只落在其中一份上。发布视图固定「哪一份是 head」并显式记录确认落点。

## 指针文件

`selections/release.json`（schema_version=2，policy_version=release-1）：

```json
{
  "schema_version": 2,
  "policy_version": "release-1",
  "generated_from_commit": "<生成时读取数据的 commit>",
  "items": [
    {
      "item_id": "i-…",
      "head_edited_id": "r-…",
      "applied_confirmation_ids": ["a-…"],
      "excluded_paragraphs": []
    }
  ]
}
```

只为「多份稿的条目」和「带确认的条目」写条目（当前 30 条）。单稿无确认的条目不需要指针，按唯一整理稿处理。`excluded_paragraphs` 存段落 index，默认留空；排除只影响投影，不删记录。

## head 规则

head = 该条目下 `metadata.revision_id` 存在、且没有被组内任何 `derived_from_id` 指向的那一份。实测 30/30 组唯一。`derived_from_id` 已记录「新版由旧版派生」；取代关系本身只由 `selections/release.json` 的 `head_edited_id` 表达，原始稿不改一个字节（原始稿哈希由 `tests/test_local_revision.py` 钉住）。

判定 head 时只信指针和这套规则，不做正文相似度猜测。如果组内出现 0 个或 2 个以上候选，`check` 报 `HEAD_NOT_UNIQUE`。

## 确认的应用状态

对每条确认，在 head 中定位 `anchor.original_text`：

- `apply`：唯一命中，导出时替换成 `corrected_text`。
- `already_applied`：原文找不到、`corrected_text` 唯一命中——head 已是修订后文本。
- `no_change`：`original_text == corrected_text`，仅登记。
- `orphan` / `ambiguous`：定位不到或不唯一，`check` 报 `CONFIRMATION_NOT_APPLIED`。

当前 7 条确认在各自 head 上全部可定位：5 条 `already_applied`、2 条 `no_change`，因此正文零改动。

## 校验码

`python tools/release.py check` 与 `python tools/corpus.py validate` 都会跑同一套检查（后者在有 `selections/release.json` 时调用 `validate_release`）：

| 码 | 含义 |
| --- | --- |
| `HEAD_NOT_UNIQUE` | 多份稿的条目没有唯一 head（缺指针或规则给不出唯一解） |
| `HEAD_MISSING` | 指针里的 `head_edited_id` 不是该条目的整理稿，或指针指向无稿条目 |
| `CONFIRMATION_ORPHAN` | 确认不存在、不属于该条目、head 未列在确认的 `edited_transcript_ids` 中，或有确认未登记进指针 |
| `CONFIRMATION_NOT_APPLIED` | 确认锚点在 head 中定位不到或不唯一 |
| `DUPLICATE_ITEM_EDITED` | 同一 item 在指针中出现两次，或同一份 head 被两个 item 认领 |
| `SUPERSEDED_CONFLICT` | 记录若带 `superseded_by`，其指向必须存在、同条目，且与 head 一致（当前数据无记录使用该字段，检查保留） |

## 命令

```sh
python tools/release.py check
python tools/release.py init-selection          # 首次按 head 规则生成 selections/release.json，已存在则拒绝覆盖
python tools/release.py export --output .cache/exports/release_paragraphs.jsonl
```

`export` 输出段落级 JSONL 并写同名 `.manifest.json`（含 `selection_sha256`、`release_paragraphs_sha256`、计数和 `review_basis` 说明）。导出是派生物，不入库；需要分发时由 `chosenecho/weimingzi-datasets` 承载。

## 导出字段

`release_schema_version`、`policy_version`、`item_id`、`item_title`、`source_url`、`edited_id`、`paragraph_id`（`<edited_id>:p<index>`）、`paragraph_index`、`time_unit`（恒 `ms`）、`start_ms`、`end_ms`、`text`、`issue_state`（`clean` / `flagged`）、`issue_count`、`applied_confirmation_ids`、`review_basis`（`model_flagged_clean` / `model_flagged_with_notes`）。

当前投影：1989 个条目、117440 段（总 118775 段减去非 head 版本的 1335 段），其中 41086 段带校对标注。

## 边界

- 时间只精确到 ASR 块边界（整理稿 `metadata.timing_scope` 原文为 "ASR chunk bounds only, not exact paragraph timestamps"），引用时给 `paragraph_id` 和毫秒区间，不宣称逐字对齐。
- 发布视图不判断观点、真伪或可用性，也不表示内容权利状态；权利按[内容权利说明](../CONTENT-RIGHTS.md)。
- 训练选稿与正式发布版本仍归 `chosenecho/weimingzi-datasets`，本视图只提供段落级输入。
