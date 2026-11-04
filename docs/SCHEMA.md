# 数据结构

所有维护记录使用 UTF-8 JSON 或 JSONL。`schema_version` 为 `1`；各表的实际数量见 [counts.json](counts.json)，校验入口为 [data.py](../src/weimingzi_corpus/data.py)。

## 条目与结果

`data/items.jsonl` 每行一个内容条目。`kind` 使用 `video`、`part`、`recording`、`dynamic`、`article`、`person`。视频与分段通过 `parent_id`、`part_number` 相连；独立录音直接作为条目。

| 字段 | 含义 |
| --- | --- |
| `id` | 仓库内稳定标识 |
| `title` | 展示标题 |
| `identifiers` | 外部标识的命名空间和值列表 |
| `urls` | 内容链接 |
| `attributes` | 元数据；每个键保存不同取值的列表 |
| `relations` | 关联条目及关系类型、依据 |

平台 ID、数据库中的转录或修订编号均作为字段保留。来源平台不构成目录层级。同一字段已有多个不同观测值时并列保存，不以某个采集批次覆盖其他值。

`relations` 只表示记录的关系。例如视频参照关系不表示两份音频相同；音频相同与否用文件 SHA-256 判断。

## 基础转录

`data/transcripts/<id>.json` 保存一份转录结果。`item_id` 指向内容条目；`method`、`model`、`language` 描述结果；`text` 是全文，`segments` 保存原始顺序的分段。

每段含 `ordinal`、`start`、`end`、`text`，其余已有字段保留。`time_unit` 明确为 `ms` 或 `s`。说话人标签及分块偏移按记录保留；分块内的说话人编号不自动视为跨块同一人。

`content_sha256` 是 `item_id / method / language / model / time_unit / text / segments` 对象的规范 JSON 哈希。规范编码使用 `sort_keys=True`、`ensure_ascii=False`、紧凑分隔符，并拒绝 NaN。`quality.timing_issues` 必须准确描述现存时间问题；校验不排序、截断或修补原值。

`alignments` 可保存识别响应中独有的词级时间和句子信息。每项含块偏移（秒）、块内时间单位、句子和词记录；`alignments_sha256` 单独保护这些补充信息。它们不替代正文分段。无可识别正文的块可保存空句子及质量说明。

## 整理稿

`data/readings/<id>.json` 每份独立结果包含 `text`、`paragraphs`、`model`、`notes`、`complete`、`quality`。`transcript_ids` 关联可确认的基础转录；无法确认的关系留空，不猜测。

段落保存原文、整理文字、原有段落标签、疑点和时间范围。`paragraphs_match_text` 表示全文是否与段落正文一致。只有 Markdown 转义解码后与结构化正文全文相等时，才去除展示转义；不同措辞作为独立结果保留。少量校验稿包含正文之外的独有说明，保存在 `review_markdown` 中供导出。

`input_units` 保存整理时使用的参照单位；局部结果也可通过 `reference_units_reading_id` 引用同条目的参照单位。部分参照来自较长音频块，其边界不代表逐字、逐句时间。`segment_ids` 是输入单位标签，不应直接当作仓库记录 ID。

`complete=false` 表示结果未完成或仅覆盖部分输入。局部模型输出带 `partial_model_output` 标记；未解析的输入标签列在 `quality.unresolved_unit_labels`。它们仍是普通整理结果，使用时按完整性筛选。

`derived_from` 用于确有文字或注释修订关系的整理稿。人工确认后的选稿关联原稿及确认记录；不保留运行批次和文件迁移链。

## 动态、专栏和集合

`data/dynamics/<id>.json` 的 `content` 保留完整富文本对象，包括转发内容、图片信息和卡片；`article_item_ids` 关联展开全文对应的专栏。纯文本导出不会替代这些结构。

`data/articles/<id>.json` 保存 `text` 和已有 `html`。浏览器正文与文本导出确有差异时，使用 `text_variant` 保留；`quality.has_expand_prompt` 记录采集页面是否仍有展开提示，不以文件存在推断全文完整。

`data/collections.jsonl` 使用 `article_list / season / series` 表示文集、合集和系列。`members` 按 `position` 保存条目引用及成员顺序。集合与平台目录分开；成员不另复制正文。

## 音频与人工确认

`data/media.jsonl` 按音频 SHA-256 合并记录。`availability=release` 含文件字节数、本地恢复路径和 `downloads`；每个下载位置含 Release 标签、ZIP 元信息与原 ZIP 成员名。归档成员名是下载定位字段，不是仓库分类。`availability=unavailable` 只记录已知文件标识及缺失说明。详见 [下载规则](DOWNLOAD.md)。

`data/annotations.jsonl` 保存确认范围、原文锚点、修改后文字、双方哈希、术语注释及适用整理稿。确认范围按原记录保留，不向全文扩张。

`selections/training.json` 只保存 `item_id / reading_id / annotation_ids` 选稿引用。选入训练集不改变 `human_reviewed`。`approval_scope` 声明现有确认仅限局部字句。

## ID 与更新

条目 ID 以 `i-` 开头，根据条目类型和外部标识生成；转录 `t-`、整理稿 `r-`、动态 `d-`、专栏及确认 `a-`、集合 `c-` 使用相应身份或内容摘要；音频 `m-` 使用完整文件 SHA-256。普通 ID 使用摘要的前段，校验拒绝重复 ID。

所有内部关系按表和 ID 校验。新增不同结果时生成新 ID；元数据补充不重命名已有条目。导出格式、JSON 排版或文件位置不同，不构成新的正文结果。
