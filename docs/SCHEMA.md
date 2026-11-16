# 数据结构与术语

维护数据采用 UTF-8 JSON/JSONL，`data/schema.json` 声明 schema v3。本文统一定义当前实体、术语和字段语义；操作见[维护与入库](MAINTENANCE.md)，查稿及导出见[资料查询](QUERY.md)。记录、元数据与归档内容不等于真实性、完整性、人工审核或使用权判断。

[机器可读契约](schema-v3-contract.json)固定字段、引用、读取接口及投影规则；实现为 [schema_v3.py](../src/weimingzi_corpus/schema_v3.py)，事实校验入口为 [records.py](../src/weimingzi_corpus/records.py)。结构取舍见[四实体决定](decisions/0001-four-entity-storage.md)。[v2 语义参考](SCHEMA-V2.md)保留旧字段含义和历史路径，供现有接收协议与历史投影查阅；其中旧目录不是当前维护源。

## 四类维护实体

| 实体与术语 | 维护位置 | 内容 |
| --- | --- | --- |
| 条目与有序集合 item / collection | data/items.jsonl | 内容、人物或有序集合的索引对象，沿用原 ID 和 kind |
| 文稿 document | data/documents/\<id\>.json | transcript、edited_transcript、post、article，各自保存一份独立文字结果 |
| 资产 asset | data/assets.jsonl | audio、archive、review_document、html，保存独立文件及校验、恢复位置 |
| 人工证据 annotation | data/annotations.jsonl | confirmation、segment_attribution，保存可引用的局部文字确认或片段归属 |

条目保存标题、外部标识、链接、元数据和关联；同一内容条目可以关联多份转录、整理稿或音频文件。`audio_recording` 是被索引的独立录音内容条目，与按文件 SHA-256 标识的音频资产分开。文稿不是发布 head 或训练选稿。

动态贴文以富文本保留转发对象、图片和卡片；专栏文章保存独立正文和已有 HTML，动态可以关联展开全文对应的文章条目。集合是有序条目引用，分别使用 `article_collection`、`video_collection`、`video_series`，不复制成员正文。

独立 Markdown、HTML 工件字节位于 `data/artifacts/`，由资产记录定位和校验，不构成第五类实体。音频 `local_path` 和远端恢复位置保持原值，不因结构迁移搬动或重新下载音频；恢复位置存在不表示已实时验证远端可用。

`data/schema.json` 的契约为：

```json
{"schema_version":3,"entities":["items","documents","assets","annotations"],"range_unit":"unicode_codepoint","range_end":"exclusive"}
```

记录不再重复保存 `schema_version`。字段、项目自定枚举使用 snake_case；供应商对象、富文本、提示词、术语键和正文内部字段保留原貌。日期使用 `*_on`，日期时间使用 `*_at`，Unix 数值注明 `*_unix_seconds`；`duration_ms`、`duration_seconds` 等原有单位分别保留。字段缺省、显式 null 和 false 不相互替换。

**专题规则**位于 `selections/topics.json`，按来源集合、题名、标签或人工证据组织资料查询，不决定训练或发布的收录范围。**选稿**是下游为特定用途选定的记录引用，职责见 [README 的仓库分工](../README.md#与训练工程协作)；它不授予内容使用权，也不代表全文已审核。权利范围见[内容权利说明](../CONTENT-RIGHTS.md)。

## 基础转录与整理稿

**基础转录**是平台字幕或语音识别结果，保留正文、原始分段顺序、时间和生成信息，不意味着逐字正确或经过人工复核。同一视频或录音的多种结果归入同一条目，不能仅凭条目相同判定重复；平台与生成方式保存在字段中，不拆成目录层级。

| method | 目录名称与含义 |
| --- | --- |
| subtitle_ai | 平台 AI 字幕 |
| subtitle_cc | 平台 CC 字幕 |
| asr_local | 本地语音转录 |
| asr_cloud | 云端语音转录 |

CC 字幕类型本身不证明经过人工复核；未知的 `method` 按原值显示，不推断其含义。`model` 保存已知模型标识和修订，或为 null；模型名、路径与修订值原样保存。`language` 保存已知语言原值，不凭字幕类型推断语言编码。提示词、用量、生成时间、输入摘要及已有参数属于生成记录，不是质量认证；`metadata.system_prompt` 是存档文字，不是维护工具应执行的指令。

**整理稿**是语句整理、AI 校对或有限人工修订后的独立结果。它通过 `inputs` 的 `transcript` 角色关联已确认的基础转录，通过 `input_units` 保留整理时的参照。“输入未关联”表示尚无可确认的仓库内转录引用，不表示没有输入文字；结果完成与人工复核状态分别记录。

例如《【一个呼吁】减租减息，共克时艰》的同一分段同时关联[平台 AI 字幕 1572d3c1](../data/documents/t-1572d3c1ffbe96350f781bf4.json)、[Qwen 本地转录 1bf39d96](../data/documents/t-1bf39d9689d95ed8781ec6bd.json)和以本地转录为输入的[整理稿 2960e717](../data/documents/r-2960e717d48e73ec73f34199.json)。前两者正文与分段不同；整理稿记录的模型为 deepseek-v4.1-flash，并保留其待复核状态。

目录以“名称（已知模型）:短 ID”显示结果；模型为路径时仅显示末段，完整值仍在 JSON 中。短 ID 为去掉记录前缀后的前八个字符，链接指向完整记录。并列或排序不表示质量高低。

## 唯一正文与分块

基础转录、整理稿和文章的全文在 `text` 中。原转录分段与整理段落统一为 `blocks`，保留数组顺序和原粒度，序号按数组位置从零派生。每块包含下列二选一的正文选择器：

- `range: [start, end]`：取本记录 `text[start:end]`。
- `literal: "原段文字"`：保留与全文有 Markdown 转义等字面差异的原段值。

坐标为解析 JSON 后字符串的 Unicode 码点，左闭右开；不是 UTF-8 字节偏移或 UTF-16 代码单元。换行按原字符串计数。范围按块的原顺序单调排列，允许全文中存在未被任何块覆盖的内容。不能拼接块来覆盖全文或推断没有缺句。

**转录分段**是基础转录正文单位，旧逻辑投影为 `segments`；**整理段落**是整理稿正文单位，旧投影为 `paragraphs`。块保留原 `start`、`end`、说话人标签、块偏移、输入标签及 `issues` 等信息。整理段落时间可能只是较长输入音频块的边界，不保证逐句或逐字对齐。

`time_unit` 只作用于记录原已声明的正文时间轴，取 `ms` 或 `s`。**识别块** `recognition_chunks` 保存识别响应的块偏移、时长、句子及词信息：`offset_seconds`、`duration_seconds` 使用秒，块内时间遵循块自己的 `time_unit`，供应商内部字段沿用其原定义。输入快照中的 `start_ms`、`end_ms` 仍是毫秒。校验和导出不排序、截断、取整或修补原始时间，也不把识别块表述为强制对齐结果。

说话人标签可能只在识别块内有效，相同 `speaker_id` 不自动证明跨块是同一人。人物和观点归属只由人工片段归属确认。

动态以 `content` 保存原富文本和转发结构，纯文本沿用作者摘要提取规则，不把转发全文冒充作者原文；已有独立文字字段按原值保留。文章的既有 `text_variant` 保存确有字面差异的文字，HTML 作为独立资产保存，不相互覆盖。

## 输入与关系

`inputs` 是带角色的引用数组，每项为 `{role, target_id}`。有限角色如下；旧专有字段名仅说明兼容投影中的同一语义。

| role | 含义与旧字段 |
| --- | --- |
| item | 文稿归属条目，或音频关联的内容条目；item_id / item_ids |
| audio | 本次转录实际使用的音频；audio_ids |
| transcript | 整理稿已确认的输入转录；transcript_ids |
| derived_from | 同条目整理稿的实际文字或注释修订关系；derived_from_id，不得成环 |
| input_units_from | 同条目另一整理稿的输入参照；input_units_from_id |
| article_item | 动态关联的独立文章条目；article_item_ids |
| review_document_markdown / html | 原有独立工件资产 |

条目 `relations` 与集合 `members` 继续表达各自事实；成员数组顺序为权威顺序，等值的 `position` 按位置加一派生。视频与分 P 的 `parent_id`、从一开始的 `part_number`、集合种类和外部来源编号不按标题推断或合并。

条目关系中的 `has_full_text` 表示关联全文，`references_video`、`references` 表示参照；参照不证明音频相同，音频同一性按文件 SHA-256 判断。`audible_rerecording_of` 从有声重录版指向原条目，保留确认依据和日期；它不证明音轨相同或时间轴逐段对应，文稿仍归属于实际有声版本，查询时归入跨来源补充。

`blocks[].input_text_ref` 保存 `target_id`、`content_sha256`、`source` 和字符 `range`。`source` 可以是 `text`，或原分段文字按空串、空格、换行连接的 `segments`、`segments_space`、`segments_newline`，或 `input_units` 中已有输入快照。只有源记录和片段均唯一且能精确复原时才替代重复 `input_text`；歧义、无映射和空值按原情况保留。引用校验重新计算源哈希，不只比较可能过期的字段：转录引用重算旧契约正文哈希，快照引用计算 `input_units.base` 的规范 JSON 哈希。

**输入单位** `input_units` 是整理时使用的文字与参照片段，粒度可能不同于转录分段。它保留原文字、块边界、旧内容哈希、时间和质量；当前转录不能覆盖历史快照。`upstream_transcript_id` 是快照中的外部标识，不擅自变成内部转录引用。局部稿可通过 `input_units_from` 引用同条目另一整理稿的输入单位。

**输入单位标签** `input_unit_labels` 只在对应输入中定位片段；**证据标签** `evidence_labels` 定位输入侧参照。它们可含旧编号或片段编号，不作为仓库记录 ID 解析。`unassigned_reference_labels` 是未分配参照标签，`unresolved_unit_labels` 是尚不能定位的输入标签；字段为空不证明正文正确。附注或快照中的外部编号、输入哈希和修订字符串按原文保留。

## 人工证据与模型标注

人工证据在 `annotations`，其 `targets` 数组使用 `item`、`applies_to`、`revision` 角色。`item` 指内容条目；`applies_to` 表示证据适用文稿。带 `confirmation_index` 的目标保留旧文档确实列过该确认的列表位置，有 `derived_from` 输入的修订文稿采用 `revision` 角色，记录修订采用依据。适用范围与采用关系分别核对，文稿不再维护第二份确认列表。每个目标须存在、属于同条目，并通过对应文字和时间定位。

### 校对标注与参照稿

**校对标注／疑点** `blocks[].issues` 附属于具体整理段落，保存 AI 整理或后续修订留下的疑点、候选改法及修改说明，原顺序保持不变。`note` 为标注说明，记录存疑原因、处理理由或回查事项；`candidate` 是候选文字，可为词、短语、整句、空字符串或未提供，已有可空值按原情况保留。候选为空不等于应删除原文。`evidence_labels` 是输入侧参照标签，可为空或未提供。

部分候选已用于正文，部分只是要求继续核对。当前标注没有统一的逐条解决状态或问题类别；不能把标注总数当作未解决问题数，或把所有候选词直接收入人工术语释义。回查时结合本块的输入文字、正文、时间和标签。完整目录见[校对标注与复核状态](catalog/reviews.md)。

**整理附注** `notes_markdown` 保存整份结果的说明、局部修订和核对事实。**独立校验稿**是另行保留的完整 Markdown 参照稿，通过 `review_document_markdown` 输入角色引用资产；它可能与结构化段落、附注有差异，分别保存。

`review_markdown` 导出完整保留独立稿，附注未完整包含时另附；无独立稿时，从附注、输入文字、段落正文及全部标注生成。普通 TXT、正文 Markdown 和字幕不包含完整标注，全文索引也只查正文；操作见[正文与标注导出](QUERY.md#导出正文与标注)。完整维护信息看 JSON，段落标注可用 `review_issues` 导出。该导出的 `paragraph_index`、`issue_index` 从零开始，定位当前 `blocks[paragraph_index].issues[issue_index]`，旧投影中对应 `paragraphs`；`record_path` 指真实维护文件。导出不生成独立维护 ID，也不推断解决状态。

### 人工确认

**人工确认** `kind=confirmation` 保存审核过的局部字句或术语、原文锚点、修订文字及适用整理稿。`anchor` 保留 `original_text`、原文字节哈希和已有输入单位标签；`corrected_text` 及其哈希保存确认后的文字。`term_glosses` 只保存确认中明确记录的词义或简称解释，适用范围由该确认限定。

`scope`、`status` 和 `confirmation` 保留审核范围、核对摘录、结论、审核角色、日期、时区及既有听音事实。审核角色标签不推断真实身份。AI 候选、AI 修改说明和人工确认分别保存，不自动提升确认等级。`scope=local_text_or_term` 不扩展为整段、整稿审核；适用确认不证明正文已采用，采用也不证明全文审核或授予内容使用权。

### 片段说话人与观点归属

**片段归属** `kind=segment_attribution` 保存人工审核认定的某段或段内某句由谁说出、表达谁的观点，与文字确认使用不同规则。`anchor` 保留从零开始的 `paragraph_index`、`paragraph_text_sha256`、`excerpt`、`start`、`end`、`time_unit`。段落哈希为按选择器还原的精确段落文字的 UTF-8 SHA-256；`excerpt=null` 表示整段，否则须为段内原文子串；时间值与对应块及文稿一致。

`speaker_role` 取 `primary_speaker`、`other_speaker`、`unknown`，主讲人由审核者认定，不由上传者、标题或识别标签推断。`viewpoint` 取 `own_view`（本人观点）、`quoted_or_read_aloud`（朗读或引述原话）、`explained_or_paraphrased`（讲解或转述）、`unknown`（审核后仍无法判断）。没有记录是未审核，与 `unknown` 不同。

`review` 保留审核者原话 `basis`、角色、日期、时区、看过原视频及助手听音的已有事实和可选来源链接。`status` 只接受 `human_confirmed`，模型归属候选不写入此类证据。段落文字改动后旧哈希不再匹配，须重新审核后另建记录，不能只改旧哈希。归属不确认文字正确、不改变质量状态；文字确认不代替归属确认。下游作为作者本人参照时，仅采用 `speaker_role=primary_speaker` 且 `viewpoint=own_view` 的确认范围。

## 工件、恢复位置与哈希

音频保留文件 SHA-256、大小、条目关联和恢复位置。**本地路径** `local_path` 指音频恢复后的仓库相对路径或已保存工件的仓库相对路径。重复归档描述仅保存在 `kind=archive` 的资产中，含 `name`、`size_bytes`、`sha256`、`url`；音频 `downloads` 用 `archive_id`、原 `member_path`、`release_tag` 定位，旧投影还原为 `archive` 对象。

**成员路径**是 ZIP 内原有成员名，必须与远端内容一致；Release 标签和目录命名不改变这些外部定位值。恢复链限于文件到归档文件，不增加通用递归恢复图或成员反向清单；恢复操作见[音频恢复](PRESERVATION.md#音频恢复)。

原有独立校验稿和 HTML 按 UTF-8 原字符串提取到资产，保留换行和完整文字，文稿通过输入角色引用。仅服务该文稿的识别块、词信息和快照继续内嵌。未保存过的原始响应字节不补造，已整理的识别块不重新命名为供应商原始响应。

各种哈希按对象区分：

- 音频、ZIP 和提取工件的 `sha256` 校验实际文件字节。
- 旧转录 `content_sha256` 校验 `item_id/method/language/model/time_unit/text/segments` 的规范 JSON；分段由选择器无损还原后计算，不是新文稿文件的字节哈希。
- `recognition_chunks_sha256` 校验补充识别块的规范 JSON，不替代正文哈希。
- 文字锚点哈希校验指定原文字串的 UTF-8 字节。

规范 JSON 使用排序键、紧凑分隔符、未转义 Unicode，并拒绝 NaN。结构改名不重新分配旧 ID，不把一种对象的哈希冒充另一种。批次字节、载荷及计划的其他哈希边界见[批次协议](INCREMENTAL-INGEST-SPEC.md#哈希边界)。

## 元数据、派生值与旧格式投影

**记录 ID** 是稳定、不透明的内部标识，纯字段或目录改名不改变已有 ID；新增不同结果生成新 ID。**外部标识**保存在 `identifiers` 的命名空间中，不自动转成仓库引用。

**元数据** `metadata` 的每键保存并列观测值列表，对象或数组本身也可作为一次完整观测，不递归展开，不覆盖不同值。已证实同义的键仅在 JSON 类型及全部值精确相同时合并，还原时记录字段名映射，不保存第二份值。`created`、`ctime`、作者和上传者不因近似而合并；`observed_at` 和 `observed_at_unix_seconds` 保留各自字符串或秒数。标题、模型、语言和正文哈希与对应元数据完全相同时只存一个值，独立观测和字面差异保留。平台对象内的 `review`、`video_review`、`disable_preview` 不自动解释成人工复核状态。

计数、反向列表和序号由读取层派生。`paragraphs_match_text`、`quality.timing_issues` 只有与旧公式结果完全相等时才移除并按公式还原：前者比较 `"\n\n".join(段落文字).strip()` 与 `text.strip()`，后者按现有时间检查算法计算。旧断言不等则原样保留，其他人工或模型质量判断不推导。

`_legacy` 是有限版本配方，保存旧逻辑表、原字段存在性以及 `metadata_aliases`、`derived`、`null_fields` 等可逆规则，不存旧整行或通用 raw/payload 副本。`records.iter_records` 等现有接口提供九个旧逻辑视图，返回真实 v3 路径；`schema_v3.iter_native_records(root, entity)` 提供四实体记录。兼容读取不表示原生 JSON 仍有旧字段，也不承诺新的输入格式。

**导出结果**是由维护记录生成的 TXT、Markdown、字幕、CSV 或 SQLite；格式或排版变化不构成新的正文结果。SQLite 使用四张原生实体表和可重建的正文全文索引，目录与 CSV 指向当前文稿文件。生成目录、检索库均为可重建的派生结果，不是权威维护来源。

## 质量、完整性与可用状态

| 名称 | 字段或值 | 限定含义 |
| --- | --- | --- |
| 结果完成 | is_complete | 该输出已完成，不保证音频全覆盖、识别无遗漏或审核完成 |
| 全文人工复核 | is_fully_human_reviewed | 全文已经实际人工核查 |
| 待复核 | requires_review | 结果需要继续检查 |
| 字幕导出启用 | is_subtitle_export_enabled | 是否启用字幕导出，仍须通过实际时间与序列化检查 |
| 识别异常区间 | recognition_issue_intervals | 已记录的识别或时间异常范围 |
| 正文可用 | transcript_text_available | 对应区间存在文字 |
| 可恢复音频 | availability=available | 索引有恢复位置，不承诺远端永久在线 |
| 不可获取音频 | availability=unavailable | 索引无可用下载位置，不表示确认静音 |

审核和导出标记的 false 表示明确否，null 表示原数据未说明。局部确认与训练选稿不能把全文人工复核标记提升为 true。`is_complete=false` 可表示未完成或只覆盖部分输入，`partial_model_output` 等原有状态继续保留。

`paragraphs_match_text=false` 时段落与全文都保留，不能把段落参照直接当成当前全文。`has_expand_prompt` 表示文章采集页面是否仍有展开提示，与校对疑点分开记录，文件存在不证明全文完整。

字幕启用后仍须校验时间：倒退、无效范围或不能无损表示为毫秒的数值使导出失败，不自动修复。`recognition_issue_intervals` 使用独立的 `start_seconds`、`end_seconds`，不继承文稿 `time_unit`；已有原因、转录及识别块证据分别保留。时间戳不可用、未返回识别词、待复核、文字存在、不可用字幕、缺失音频和确认静音互不推断。

`timing_issues` 是按当前时间值检查的问题列表，`reported_timing_issues` 保存既有时间报错；`audio_assessment` 是已有音频判断。用户明确确认原分 P 无声时可记录 `silent_audio_confirmed`，并在 `audio_assessment_evidence` 保留 `basis=user_confirmation`、原话、日期、时区和证据位置。条目级判断作为元数据观测，转录级质量与依据分别保留；确认无声不改变音频文件恢复状态，也不表示整理稿人工复核完成。

**输入质量快照** `quality.input_quality` 描述输入当时已有质量判断，整理稿自身 `quality` 描述当前结果。上游时间异常、文字可用状态及当前待复核状态分别读取，不用当前上游记录覆盖快照；转录存在也不表示音频可恢复。

## 迁移与验收

运行[迁移工具](../tools/migrate_schema_v3.py)时，源与目标均为包含 `data/` 的仓库根，且互不包含；首次迁移目标须不存在或为空。源文件不写入，未知字段、失效引用、哈希不符、无法逐记录复原等情况均停止发布目标。目标报告保存完整源文件清单、逐记录映射、字段去向和验收结果。

```sh
uv run python tools/migrate_schema_v3.py --source /path/to/v2-checkout --output /path/to/separate-v3-root
uv run python tools/migrate_schema_v3.py --source /path/to/v2-checkout --output /path/to/separate-v3-root --verify-only
```

`--verify-only` 只读复验已完成的目标，不要求目标仍为空。切换当前数据前逐记录核对全部旧 JSON 值，验证来源、全文、分段、输入、时间、模型、质量和人工证据。维护源只写 v3，不长期双写旧目录；历史提交、入库收据、保存清单及冻结产物仍按原版本复验，原字节不改。训练选稿和发布策略继续在 [README 所述制作工程](../README.md#与训练工程协作)维护。
