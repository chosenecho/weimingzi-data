# 查询、导出与引用

本页负责找稿、专题、正文与校对标注导出、全文检索。字段含义见[数据结构](SCHEMA.md)，新增或修订资料见[维护说明](MAINTENANCE.md)。在仓库根目录执行命令；首次使用先运行 `uv sync --locked`。查询与导出不改变归档记录，输出放在忽略的 `.cache/` 目录。

## 找稿与关联

从[内容目录](INDEX.md)查找条目、基础转录或整理稿 ID。跨来源查稿使用 `coverage`：identifier 接受条目 ID 或精确的平台标识，可查询视频、分 P 或独立录音，并保留每份文稿的原始 ID。按视频查询会包含其子条目；按分 P 查询不会把同视频的其他分 P 算作直接覆盖。

```sh
uv run python tools/corpus.py coverage BV1oq4y1q7rg --part 1
uv run python tools/corpus.py coverage i-7fee8b9e09f3f0d185f2aaa2
uv run python tools/corpus.py coverage BV1oq4y1q7rg --part 1 --include-records --output .cache/exports/coverage.json
uv run python tools/corpus.py coverage BV1dA411T7xD --format jsonl --include-records --output .cache/exports/coverage.jsonl
```

JSON 报告包含 `scope_item_ids`、四层关联、逐层计数和 `summary`；JSONL 每行包含查询条目、关联层及一份记录。不加 `--output` 时标准输出是完整报告，`--format jsonl` 直接逐行输出；加 `--output` 时完整报告写入文件，标准输出只返回输出路径和 `summary`。

| 层 | 依据 | 范围 |
| --- | --- | --- |
| direct | 文稿 inputs 中 role=item 的 target_id | 查询条目及所查视频的分 P |
| cross_source | 显式引用或重录关系 | 展示原关系与来源 |
| same_audio | 完整音频 SHA-256 相等 | 展示哈希及原索引 |
| chapter_supplement | 显式章节补充关系 | 章节范围的补充文稿 |

`cross_source` 双向展示 `references`、`references_video` 关系；视频级引用不证明分 P 对齐或音轨相同。`audible_rerecording_of` 也进入该层：从原条目可查有声重录版的文稿并保留确认依据，但重录关系不证明音轨同一或逐段时间对齐。文稿保留实际录音条目及原时间值。

`same_audio` 保留已记录的完整哈希身份依据，不因文件暂不可恢复而抹除。`chapter_supplement` 使用 `chapter_supplement_not_audio_identity` 关系，不证明音轨相同或整条目完整覆盖。

关系只扩展一跳，不把引用、同音频、章节补充连成可传递的等价关系。返回的 `items` 也列出暂时只有元数据的关联条目。每份结果分别带有原条目、实际记录路径和关联证据；加 `--include-records` 后可查完整 `record.inputs`（其中 transcript 角色指输入转录）。直接层为空时应继续检查相关层；相关层有稿也不等于该分 P 已有直接整理稿。

加 `--include-records` 后，结果中的 `record` 就是完整原生文稿，含正文、`blocks`、`inputs`、附注、校对标注和质量；`record_path` 指实际维护文件 `data/documents/<id>.json`。相同记录可能出现在不同层；各层按 ID 去重，`summary.related` 跨层按 ID 去重。查询不选择“最佳版本”。

完成与复核状态分别查看 `is_complete`、`is_fully_human_reviewed`、`requires_review` 和原 `quality`。`text_status` 只筛查存储文本：`empty` 表示没有文字，`filler_only` 表示去掉标点空白后只含“嗯呃啊哦唔额唉哎噢”中的字，其余为 `text_present_unverified`。它不测量音频，也不判断静音。`complete_text_candidates` 仅统计完成且非空、非纯填充词的整理稿，仍须结合质量标记复核；`human_reviewed_complete_texts` 另行统计实际标记为全文人工审核的结果。

### 回归案例

基础转录总记录数为 `transcripts`。`text_present_transcripts` 统计非空且非纯填充词的记录，`filler_only_transcripts` 统计纯填充词记录，`empty_transcripts` 统计空记录；文本筛查不代表识别准确或已核过原音频。

- BV1oq4y1q7rg P1：`direct` 包含该条目已有的独立稿件；`cross_source` 保留 YouTube LhbZtt3hmSE 的独立稿及指向 Bilibili 视频的原引用。新稿不替换旧稿。
- BV1dA411T7xD 中“美的辩证法”条目 i-7fee8b9e09f3f0d185f2aaa2：`same_audio` 展示其他来源版本及完整哈希。
- “克尔凯廓尔三阶段论”条目 i-e33df3f1154c7f435ae90247：`same_audio` 展示其他来源版本及完整哈希。
- 独立录音“神创论”“自然神论”“神义论”：从明确的章节补充关系查阅；未完成整理稿仍显示 `is_complete=false`。
- BV1CP4y1s7BM P2：用户已确认原分 P 无声，P1 是有声重录版。`direct` 保留纯填充词原稿；`cross_source` 返回 P1 已有文稿。无声判断来自用户确认，`filler_only` 仍只表示文本筛查结果。

覆盖案例依据 [issue #4](https://github.com/chosenecho/weimingzi-data/issues/4) 和仓库规范记录。填充词案例原问题见 [issue #5](https://github.com/chosenecho/weimingzi-data/issues/5)，用户确认的原话、日期与重录关系见[质量核查记录](evidence/issue-5-filler-only.md)。

## 专题查询

[专题目录](catalog/topics.md)由 `selections/topics.json` 生成，配置格式为 `thematic-index/v1`。专题与 [data/items.jsonl](../data/items.jsonl) 中的平台集合分别维护；集合也是原生 `items`，以集合 `kind` 与有序 `members` 查询。已配置专题及统计以生成目录为准；以下使用专题 ID `ismism`、名称“主义主义”演示。

纳入规则保留各自证据，不检索作者名、上传者名、简介或正文中的宽泛关键词：

1. `collection_ids`：明确指定的来源系列成员，保留集合 ID、题名、原成员位置。
2. `title_prefixes`：题名经 Unicode NFKC、去空白及 casefold 后匹配配置的前缀，保留原题名和命中前缀。
3. `exact_tags`：仅匹配 `metadata.tags` 中规范化后相等的完整标签，保留原标签。
4. `manual_inclusions`：必须提供条目 ID、纳入角色及依据，可补充来源链接。
5. `include_chapter_supplements`：沿明确的章节补充关系加入独立录音，不推定音轨相同。

`core` 表示系列或题名规则命中；`related` 表示仅标签命中；`introductory` 表示有依据的导入材料；`chapter_supplement` 表示章节补充。角色不证明文稿完成或已人工审核。同一条目可保留多个纳入理由；已纳入视频的分 P 不重复作为专题条目。

BV1wk4y1L7Q2《【我是谁】无论是要批判我还是向我学习都要了解的基本情况》通过原“主义主义”标签和 issue #3 的导入材料依据纳入。其题名不含专题关键词，也没有伪造来源系列成员关系。生成索引保留它的直接转录、整理稿及复核状态。

```sh
uv run python tools/corpus.py topic ismism --output .cache/exports/ismism-coverage.json
uv run python tools/corpus.py topic 主义主义 --include-records --output .cache/exports/ismism-records.json
```

`topic` 对每个入选条目复用[分层关联查询](#找稿与关联)，分别列出直接关联、跨来源引用、同音频与章节补充，保留所有变体。报告的 `entries` 包含纳入原因和完整 `coverage`；加 `--include-records` 才嵌入完整原生文稿，正文、块、输入、标注和质量保持原值，`record_path` 指实际维护文件。顶层 `counts` 在每层跨专题条目按记录 ID 去重；不同层可能包含同一记录，不能相加当作文稿总数。不加 `--output` 时标准输出是完整报告；加 `--output` 时完整报告写入文件，标准输出只返回输出路径和 `counts`。

修改专题时只编辑 `selections/topics.json`，不为专题筛选改写原始题名、标签或集合，也不手改生成目录：

```sh
uv run python tools/corpus.py validate
uv run python tools/corpus.py generate
uv run python tools/corpus.py generate --check
```

`validate`、记录导入和批次入库只校验归档数据，不加载专题规则；专题查询、`generate` 和全仓检查显式校验已有规则，拒绝未知集合、失效条目和缺少依据的人工纳入。`generate` 更新专题目录。

## 导出正文与标注

从[内容目录](INDEX.md)找到转录或整理稿 ID，将下列 `RECORD_ID` 替换为该 ID：

```sh
uv run python tools/corpus.py export --id RECORD_ID --format txt --output .cache/exports/result.txt
uv run python tools/corpus.py export --id RECORD_ID --format markdown --output .cache/exports/result.md
uv run python tools/corpus.py export --id RECORD_ID --format review_markdown --output .cache/exports/review.md
uv run python tools/corpus.py export --id RECORD_ID --format vtt --output .cache/exports/result.vtt
uv run python tools/corpus.py export --id RECORD_ID --format srt --output .cache/exports/result.srt
uv run python tools/corpus.py export --entity documents --id RECORD_ID --format jsonl --output .cache/exports/record.jsonl
uv run python tools/corpus.py export --format catalog --output .cache/exports/catalog.csv
```

`review_markdown` 需要整理稿 ID；`srt/vtt` 需要基础转录 ID。字幕只接受可无损表达为毫秒的时间值；出现倒退、无效范围或明确禁用时间导出的结果会报错，不自动修复。不得为导出而排序、截断、取整或修补原时间值。

JSON/JSONL 必须指定 `--entity items|documents|assets|annotations`，直接返回原生记录；可加 `--id`。JSON 无 ID 时是数组，有 ID 时是对象；JSONL 每行一条原生记录。文本、字幕及校对格式只接受 documents，`--entity documents` 可省；catalog/sqlite 是全库派生，不能加 ID 或 entity。程序读取统一用 `records.iter_records(root, entity, kind=...)`，返回原生记录和实际路径，单稿用 `load_document`。

人工证据直接导出原生标注，不另造归属格式：

```sh
uv run python tools/corpus.py export --entity annotations --format jsonl --output .cache/exports/annotations.jsonl
```

`targets`、原生 `anchor.paragraph_index` 和审核依据保持原值。topic 配置中 `manual_inclusions[].item_id` 是合法领域选择键，不是文稿引用字段。

### 查看校对标注

[校对标注与复核状态](catalog/reviews.md)列出全部整理稿，包含没有段落标注的结果。目录链接指向原生维护文件 `data/documents/<id>.json`；块级校对标注及字段语义见[校对标注与参照稿](SCHEMA.md#校对标注与参照稿)。原生位置为 `blocks[].issues`，包括 `note`、`candidate`、`evidence_labels`；JSON/JSONL 保持该原生字段位置。

核对时结合块的正文切片或 `literal`、输入原文、`input_unit_labels` 和时间范围。`input_text_ref` 按 target_id、目标原生内容摘要、source=text|blocks 和区间定位精确输入；source=blocks 时无分隔拼接目标各块的 `block_text`。内联 `input_text` 则保留独立原始输入事实。候选文字和参照标签可能为空或未提供。

整份结果的附注见 `notes_markdown`；独立的完整参照稿通过 `inputs` 中 `role=review_document_markdown` 引用资产。`review_markdown` 导出保留独立稿及未完整包含的附注；没有独立稿时，从结构化段落和全部标注生成。

导出全部段落标注，或限制为一份整理稿：

```sh
uv run python tools/corpus.py export --format review_issues --output .cache/exports/review_issues.jsonl
uv run python tools/corpus.py export --id RECORD_ID --format review_issues --output .cache/exports/record_issues.jsonl
```

每行包含 `document_id`、`block_index`、`issue_index`、`path`、`issue`；两个 index 从零起，定位实际文件的 `blocks[block_index].issues[issue_index]`。该导出只汇总段落标注；完整附注、输入参照和质量快照仍查看维护 JSON。普通 TXT、正文 Markdown 和字幕不包含完整标注；查候选文字或标注说明时检索 `review_issues` JSONL，查附注或独立稿时查看维护 JSON。

标注中既有疑点，也有已采用修改的说明。复核后按[人工确认与局部修订](MAINTENANCE.md#人工确认与局部修订)新增有依据、有适用范围的确认并保留原标注；不批量把全部标注算作未解决问题，也不把 AI 候选升级为人工术语释义。

## 全文检索

首次检索或归档数据更新后，先重建 SQLite 副本，再搜索正文：

```sh
uv run python tools/corpus.py export --format sqlite --output .cache/exports/corpus.sqlite3
uv run python tools/corpus.py search 唯物主义
uv run python tools/corpus.py search 唯物主义 --database .cache/exports/corpus.sqlite3 --limit 20
```

SQLite 是可删除重建的派生数据，不是归档来源。v3 导出保存 `items`、`documents`、`assets`、`annotations` 四张原生记录表的完整 JSON，另建 `content_search` 中文正文索引；没有其他实体表或旧视图。默认数据库为 `.cache/exports/corpus.sqlite3`，`--database` 可指定其他导出文件。

`search` 只索引基础转录、整理稿、动态和专栏正文，不检索全部元数据、校对标注、附注、输入参照或独立校验稿。少于三个字符的查询使用字面子串匹配；检索不提供语义理解、拼写纠正或事实判断。标注查询使用[专用导出](#查看校对标注)，其他未索引内容回到维护 JSON。

搜索命中只是定位线索。引用前打开 `data/documents/<id>.json`，核对完整段落或分段、来源链接、模型及质量信息。基础转录、整理稿和专栏正文为 `text`，动态正文见富文本 `content`，转发内容另存。文稿按块的 `range` 取得 Unicode 码点 `[start, end)` 切片，或按 `literal` 还原无法精确切片的原块；需要时间定位时核对 `time_unit` 并保留原时间值。回答应给出记录 ID、仓库相对路径及引用字段或块。未命中只表示当前查询没有结果，不据此断定仓库没有相关记录。
