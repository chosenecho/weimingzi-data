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

### 导入双视频结果包

结果包使用 requested-video-results/v1 格式，可重复执行：

    python tools/corpus.py import-package .cache/incoming/requested-video-results.zip

适配器逐一校验清单中的文件、大小和 SHA-256，按 BVID、分 P、CID 匹配现有条目；在隔离副本中同时校验新增基础转录与整理稿后写入。相同包重复入库不新增记录，不替换旧结果。源包哈希、清单、视频快照和上游运行标识保存在 metadata.source_package 与 metadata.upstream。

正文、段落原文、候选改法、参照标签和完整 review.md 分别保留。is_complete 表示包内全部输入段被整理块引用一次，不证明音频全覆盖或人工审核通过；两份整理稿均待人工复核。包中只提供 ASR model_id，无法据此确定模型名称，因此规范记录的 model 为 null。字幕按原时间值校验，不排序或截断旧结果。

导入和校验成功后，结果 ZIP 可从当前仓库版本移除。规范记录保留源包 SHA-256、完整 manifest、各成员的校验信息和上游定位；维护脚本不会依赖仓库内留存该 ZIP。若以后需要重新导入，先将原包放入忽略目录，再传入其路径。

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

跨来源查稿见[分层文稿覆盖查询](COVERAGE.md)，可同时查看直接关联、显式引用、同音频和章节补充。

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

新增多版本整理稿或人工确认后，同步发布视图指针 `selections/release.json`：

```sh
python tools/release.py check
python tools/release.py export --output .cache/exports/release_paragraphs.jsonl
```

`init-selection` 用于首次生成清单；数据变动后加 `--force` 重建，不加则拒绝覆盖。head 规则、收录策略、校验码和导出字段见[发布视图](RELEASE.md)。

## 片段归属

审核者看过原视频或听过音频并给出结论后，才在 `data/attributions.jsonl` 新增片段归属。每条记录对应一个整理稿段落或段内一句：从当前段落取 `text` 计算 UTF-8 SHA-256，复制段落的 `start`、`end` 和整理稿的 `time_unit`，`review.basis` 保留审核者原话。字段和取值见[数据结构](SCHEMA.md#片段说话人与观点归属)。

无法判断时写 `unknown`，不补全推测。模型给出的归属建议不写入本表。整理稿段落文字改动后，原记录的哈希校验失败；须由审核者重新确认后另建记录，不直接改写旧哈希。

记录写入后运行 `python tools/corpus.py validate`。训练选稿需要引用归属时，在对应 entry 的 `attribution_ids` 中列出记录 ID。
