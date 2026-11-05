# 维护与入库

## 添加数据

按 [结构说明](SCHEMA.md) 生成记录。先创建条目，再加入转录、整理稿、动态或专栏；关联媒体和集合也使用条目 ID。已有内容使用现有条目，不按平台或采集日期另建目录。

```sh
python tools/corpus.py import --table items incoming-items.jsonl
python tools/corpus.py import --table transcripts incoming-transcript.json
python tools/corpus.py import --table edited_transcripts incoming-edited-transcript.json
```

入库接受单条 JSON、JSON 数组或 JSONL。命令在隔离副本中校验完整数据及引用后再写入：完全相同的 ID 和记录可重复导入；同一 ID 内容不同会报错。需修改已有元数据时直接编辑维护记录后运行校验。

同一条目存在多种真实结果时并列保存；没有文字或时间差异的导出副本不再入库。局部、缺失或待复核结果在质量字段中说明。

修改数据后更新目录并检查：

```sh
python tools/corpus.py validate
python tools/corpus.py generate
python tools/check_repository.py
python -m unittest discover -s tests -v
```

`generate` 重建 `docs/INDEX.md`、`docs/catalog/` 和 `docs/counts.json`。不要手改生成文件。CI 会检查这些文件是否与数据一致。

## 增量批次

跨表批次通过[增量入库入口](INCREMENTAL-INGEST.md)处理。它核对批次身份、文件哈希和来源范围，在候选库中检查引用及冲突，并保留接收凭证。

    python tools/corpus.py ingest verify BATCH_DIRECTORY
    python tools/corpus.py ingest validate-repository

规划和应用需要 origin 指向目标仓库且工作区干净；具体命令、过期计划和中断处理见该入口。不要把交接包中的文件直接复制到维护数据目录。

## 导出与检索

从 [内容目录](INDEX.md) 找到转录或整理稿 ID；下列 `RECORD_ID` 替换为该 ID。导出文件放在忽略目录中。

```sh
python tools/corpus.py export --id RECORD_ID --format txt --output .cache/exports/result.txt
python tools/corpus.py export --id RECORD_ID --format markdown --output .cache/exports/result.md
python tools/corpus.py export --id RECORD_ID --format review_markdown --output .cache/exports/review.md
python tools/corpus.py export --id RECORD_ID --format vtt --output .cache/exports/result.vtt
python tools/corpus.py export --id RECORD_ID --format srt --output .cache/exports/result.srt
python tools/corpus.py export --selection training --format jsonl --output .cache/exports/training.jsonl
python tools/corpus.py export --format catalog --output .cache/exports/catalog.csv
python tools/corpus.py export --format sqlite --output .cache/exports/corpus.sqlite3
python tools/corpus.py search 唯物主义
```

`review_markdown` 需要整理稿 ID；`srt/vtt` 需要基础转录 ID。字幕只接受可无损表达为毫秒的时间值；出现倒退、无效范围或明确禁用时间导出的结果会报错，不自动修复。

SQLite 是可删除重建的检索结果，保存各维护表的完整 JSON 和训练选稿，并建立中文正文索引。默认查询 `.cache/exports/corpus.sqlite3`；可用 `--database` 指定其他导出文件。

## 查看校对标注

[校对标注与复核状态](catalog/reviews.md) 列出全部整理稿，包含没有段落标注的结果。打开记录，查看 paragraphs[].issues 中的 note、candidate、evidence_labels。

核对时结合段落 input_text、text、input_unit_labels 和时间范围。候选文字和参照标签可能为空或未提供。

整份结果的附注见 notes_markdown，另存的完整参照稿见 review_document_markdown。review_markdown 导出会保留独立稿及未完整包含的附注；没有独立稿时，从结构化段落和全部标注生成。

导出全部段落标注，或限制为一份整理稿、训练选稿：

```sh
python tools/corpus.py export --format review_issues --output .cache/exports/review_issues.jsonl
python tools/corpus.py export --id RECORD_ID --format review_issues --output .cache/exports/record_issues.jsonl
python tools/corpus.py export --selection training --format review_issues --output .cache/exports/training_issues.jsonl
```

每行包含原始标注和记录、段落、标注位置，可回到维护 JSON 查看上下文。该导出只汇总段落标注；完整附注、输入参照和质量快照应查看维护 JSON。

普通 TXT、正文 Markdown 和字幕不包含完整标注；search 的全文索引只查正文。查询候选文字或标注说明时检索 review_issues JSONL，查询附注和独立稿时查看维护 JSON。

标注中既有疑点，也有已采用修改的说明。复核后新增有依据、有适用范围的人工确认，保留原标注；不能批量把所有标注算作未解决问题，或把 AI 候选升级为人工术语释义。

## 确认和选稿

新增人工确认时记录原文、修订文字、哈希、确认范围、核对依据和适用整理稿。只有实际审核过的范围才能标记为已确认。全文未审核时，保留原有 `is_fully_human_reviewed` 状态。

更新 `selections/training.json` 时引用目标整理稿及适用确认。校验会拒绝跨条目的选稿、无法定位的确认和失效引用。
