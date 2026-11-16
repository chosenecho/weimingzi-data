# 数据结构

维护数据采用 UTF-8 JSON/JSONL，`data/schema.json` 声明 schema v3。记录、元数据与归档内容不等于真实性、完整性、人工审核或使用权判断。对象定义见 [名词与概念](GLOSSARY.md)，取舍见 [四实体决定](decisions/0001-four-entity-storage.md)。

[机器可读契约](schema-v3-contract.json) 固定字段、引用、读取接口及投影规则；实现为 [schema_v3.py](../src/weimingzi_corpus/schema_v3.py)，事实校验入口为 [records.py](../src/weimingzi_corpus/records.py)。[v2 语义参考](SCHEMA-V2.md) 保留旧字段含义和历史路径，供已有接收协议与历史投影查阅；其中旧目录不是当前维护源。

## 四类维护实体

| 实体 | 维护位置 | 内容 |
| --- | --- | --- |
| items | data/items.jsonl | 条目与有序集合，沿用原 ID 和 kind |
| documents | data/documents/\<id\>.json | transcript、edited_transcript、post、article |
| assets | data/assets.jsonl | audio、archive、review_document、html |
| annotations | data/annotations.jsonl | confirmation、segment_attribution |

独立 Markdown、HTML 工件字节位于 `data/artifacts/`，由资产记录定位和校验。音频的 `local_path` 和远端恢复位置保持原值，不因结构迁移搬动或重新下载音频。恢复位置存在不表示已实时验证远端可用。

`data/schema.json` 的契约为：

```json
{"schema_version":3,"entities":["items","documents","assets","annotations"],"range_unit":"unicode_codepoint","range_end":"exclusive"}
```

记录不再重复保存 `schema_version`。字段、项目自定枚举使用 snake_case；供应商对象、富文本、提示词、术语键和正文内部字段保留原貌。未知状态保留 null，不改成 false。

## 唯一正文与分块

基础转录、整理稿和文章的全文在 `text` 中。转录原分段和整理原段落统一为 `blocks`，数组顺序保留原粒度；序号按数组位置派生。每块包含下列二选一的正文选择器：

- `range: [start, end]`：取本记录 `text[start:end]`。
- `literal: "原段文字"`：保留与全文有 Markdown 转义等字面差异的原段值。

坐标为解析 JSON 后字符串的 Unicode 码点，左闭右开；它不是 UTF-8 字节偏移，也不是 UTF-16 代码单元。换行按原字符串计数。范围按块的原顺序单调排列，允许全文中存在未被任何块覆盖的内容。不得拼接块来覆盖全文或推断没有缺句。

块内保留原 `start`、`end`、说话人标签、块偏移、输入标签及 `issues` 等独立信息。记录 `time_unit` 只作用于原已声明的正文时间轴；供应商块内时间、秒偏移和输入快照毫秒时间各保留自己的单位。校验和导出不排序、截断、取整或修补原始时间。

动态以 `content` 保存原富文本和转发结构，纯文本沿用作者摘要提取规则，不把转发全文冒充作者原文；已有独立文字字段按原值保留。

## 输入与关系

`inputs` 是带角色的引用数组，每项为 `{role, target_id}`。有限角色如下：

| role | 含义 |
| --- | --- |
| item | 文稿归属条目，或音频关联的内容条目 |
| audio | 本次转录实际使用的音频 |
| transcript | 整理稿已确认的输入转录 |
| derived_from | 文字或注释修订关系 |
| input_units_from | 同条目另一整理稿的输入参照 |
| article_item | 动态关联的独立文章条目 |
| review_document_markdown / html | 原有独立工件 |

条目关系和集合 `members` 继续表达各自事实；成员数组顺序为权威顺序，等值的 `position` 按位置加一派生。视频与分 P 的原关系、集合种类、来源编号不按标题推断或合并。

`blocks[].input_text_ref` 保存 `target_id`、`content_sha256`、`source` 和字符 `range`。来源类型为转录全文、原分段文字的指定连接方式，或已有输入快照。只有源记录和片段均唯一且能精确复原时才替代重复 `input_text`；歧义、无映射和空值按原情况保留。引用校验重新计算源哈希，不仅比较一个可能过期的哈希字段。

`input_units` 保留整理时输入快照，含原文字、块边界、旧内容哈希、时间和质量。`upstream_transcript_id` 是快照中的外部标识，不能擅自变成内部转录引用。当前转录不能覆盖历史快照。未分配或未解析的标签保持原记录含义。

## 人工证据与模型标注

人工证据在 `annotations`，其 `targets` 数组使用 `item`、`applies_to`、`revision` 角色。适用整理稿关系和修订采用依据分别保留；`confirmation_index` 只在旧整理稿实际列过该确认时记录原列表位置。文稿不再维护第二份确认列表。

文字确认保留原文锚点、原文字节哈希、修订文字与哈希、术语释义、审核范围及既有核对信息。片段归属保留段落锚点、说话者角色、观点归属及审核状态。每个目标均须存在、属于同条目并通过相应文字与时间定位；局部确认不升级为整段、整稿审核。

`blocks[].issues` 是附属标注，原顺序和每项 `note`、可空或缺省的 `candidate`、`evidence_labels` 均保留，不生成独立实体或推断解决状态。`review_issues` 导出的 `paragraph_index` 定位当前 JSON 的 `blocks[paragraph_index]`；历史投影中仍对应 `paragraphs[paragraph_index]`。`record_path` 指向真实维护文件。

## 工件、恢复位置与哈希

音频保持文件 SHA-256、大小、关联条目和恢复位置。重复归档描述只保存在 `kind=archive` 的资产中；音频下载位置用 `archive_id`、原 `member_path`、`release_tag` 定位。恢复链限于文件到归档文件，不增加通用递归恢复图或成员反向清单。

原有独立校验稿和 HTML 按 UTF-8 原字符串提取到资产，保留换行和完整文字；文稿通过输入角色引用。已有识别块、词信息和快照如只服务该文稿，继续保留为内嵌结构。未保存过的原始响应字节不补造；已整理的识别块不重新命名为供应商原始响应。

各种哈希按对象区分：

- 音频、ZIP 和提取工件的 `sha256` 校验文件字节。
- 旧转录 `content_sha256` 仍校验 `item_id/method/language/model/time_unit/text/segments` 的规范 JSON；分段由选择器无损还原后再计算。
- `recognition_chunks_sha256` 校验补充识别块的规范 JSON，不是某个新 JSON 文件的字节哈希。
- 文字锚点哈希继续校验原文字串的 UTF-8 字节。

规范 JSON 使用排序键、紧凑分隔符、未转义 Unicode，并拒绝 NaN。结构改名不重新分配旧 ID，也不把一种对象的哈希冒充另一种。

## 元数据、派生值与旧格式投影

元数据仍保存并列观测，不覆盖不同值。已证实同义的键，仅在 JSON 类型和全部值精确相同时合并；还原规则以字段名映射记录，不保存第二份值。`created`、`ctime`、作者和上传者等不得仅因数值或名称相近而合并。标题、模型、语言和正文哈希与对应元数据完全相同时也只存一个值；独立观测和字面差异保留。

计数、反向列表和序号由读取层派生。`paragraphs_match_text`、`quality.timing_issues` 只有在与旧公式的实际结果完全相等时移除并按公式还原；旧断言不相等则保留。其他人工或模型质量判断不因此推导。完成、待复核、全文人工复核、字幕导出和确认静音分别解释，false 与 null 继续区分。

`_legacy` 是有限版本配方，保存旧逻辑表、原字段存在性以及 `metadata_aliases`、`derived`、`null_fields` 等可逆规则；不存旧整行或通用 raw/payload 副本。`records.iter_records` 等接口向已有工具提供九个旧逻辑视图，返回真实 v3 路径；`iter_native_records` 提供四实体记录。SQLite 采用四个实体表和可重建的正文全文索引，目录与 CSV 指向当前文稿文件。

## 迁移与验收

运行 [迁移工具](../tools/migrate_schema_v3.py) 时，源与目标均为包含 `data/` 的仓库根，且互不包含；目标须为空。源文件不写入，未知字段、失效引用、哈希不符、无法逐记录复原等情况均停止发布目标。目标报告保存完整源文件清单、逐记录映射、字段去向和验收结果。

```sh
python tools/migrate_schema_v3.py --source /path/to/v2-checkout --output /path/to/separate-v3-root
python tools/migrate_schema_v3.py --source /path/to/v2-checkout --output /path/to/separate-v3-root --verify-only
```

切换当前数据前逐记录核对全部旧 JSON 值，验证来源、全文、分段、输入、时间、模型、质量和人工证据。维护源只写 v3，不长期双写旧目录；历史提交、入库收据、保存清单及冻结产物仍按原版本复验，原字节不改。训练选稿和发布策略继续在[制作工程](RELEASE.md)维护。
