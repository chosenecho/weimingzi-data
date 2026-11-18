# 数据结构与术语

维护数据采用 UTF-8 JSON/JSONL，`data/schema.json` 声明 schema v3。本文统一定义当前实体、术语、字段和读取 Interface；操作见[维护与入库](MAINTENANCE.md)，查稿及导出见[资料查询](QUERY.md)。记录、元数据与归档内容不等于真实性、完整性、人工审核或使用权判断。

[机器可读契约](schema-v3-contract.json)固定原生字段与引用；实现为 [schema_v3.py](../src/weimingzi_corpus/schema_v3.py)，读取、哈希与事实校验入口为 [records.py](../src/weimingzi_corpus/records.py)。当前四实体数据的整理与证据见[实施记录](NATIVE-V3-CLEANUP.md)。历史结构说明、决定和收据只解释其当时版本，当前 Interface 以本文和源码为准。

## 四类维护实体

| 实体与术语 | 维护位置 | 内容 |
| --- | --- | --- |
| 条目与有序集合 item / collection | data/items.jsonl | 内容、人物或有序集合的索引对象 |
| 文稿 document | data/documents/\<id\>.json | transcript、edited_transcript、post、article，各自保存一份独立文字结果 |
| 资产 asset | data/assets.jsonl | audio、archive、review_document、html，保存文件及其校验、恢复位置 |
| 人工证据 annotation | data/annotations.jsonl | confirmation、segment_attribution，保存局部文字确认或片段归属 |

条目保存标题、外部标识、链接、元数据和关联；同一内容条目可以关联多份转录、整理稿或音频。`audio_recording` 是独立录音内容条目，与按文件 SHA-256 标识的音频资产分开。文稿保存实际结果，不指定唯一最佳版本。

动态保留富文本、转发对象、图片和卡片；专栏保存独立正文及已有 HTML，动态可关联展开全文对应的文章条目。有序集合仍是 `items`，使用 `article_collection`、`video_collection`、`video_series` 等 `kind`；`members` 引用成员条目，数组顺序为权威顺序，不复制成员正文。成员的 `item_id` 是该领域选择键。

独立 Markdown、HTML 工件字节位于 `data/artifacts/`，由资产定位和校验，不构成第五类实体。音频本地路径、原 ZIP 成员名和恢复定位保持其实际含义；定位存在不表示已实时验证远端可用。

`data/schema.json` 是唯一版本声明：

```json
{"schema_version":3,"entities":["items","documents","assets","annotations"],"range_unit":"unicode_codepoint","range_end":"exclusive"}
```

记录不重复 `schema_version`。字段、项目自定枚举使用 snake_case；供应商对象、富文本、提示词、术语键和正文内部字段保留原貌。日期使用 `*_on`，日期时间使用 `*_at`，Unix 数值注明 `*_unix_seconds`；已有毫秒、秒及原始时间值分别保留。字段缺省、显式 null 和 false 不相互替换。

**专题规则**位于 `selections/topics.json`，按来源集合、题名、标签或人工依据组织查询。专题纳入不代表全文审核或内容使用权；权利范围见[内容权利说明](../CONTENT-RIGHTS.md)。

## 基础转录与整理稿

**基础转录**是平台字幕或语音识别结果，`kind=transcript`，保留正文、分块顺序、原时间和生成信息，不意味着逐字正确或经过人工复核。同一条目的真实不同结果并列保存。

| method | 目录名称与含义 |
| --- | --- |
| subtitle_ai | 平台 AI 字幕 |
| subtitle_cc | 平台 CC 字幕 |
| asr_local | 本地语音转录 |
| asr_cloud | 云端语音转录 |

CC 字幕类型本身不证明人工复核；未知 `method` 按原值显示。`model` 保存已知模型标识和修订，或为 null；模型名、路径、修订值及 `language` 原样保存。提示词、用量、生成时间、输入摘要和参数属于生成记录，不是质量认证；`metadata.system_prompt` 是存档文字。

**整理稿**为 `kind=edited_transcript`，是语句整理、AI 校对或有限人工修订后的独立结果。它通过 `inputs` 的 `transcript` 角色关联已确认的基础转录，并保留整理时的输入参照。“输入未关联”表示尚无可确认的仓库内转录引用，不表示没有输入文字；结果完成与人工复核分别记录。

例如《【一个呼吁】减租减息，共克时艰》的同一分段同时关联[平台 AI 字幕 1572d3c1](../data/documents/t-1572d3c1ffbe96350f781bf4.json)、[Qwen 本地转录 1bf39d96](../data/documents/t-1bf39d9689d95ed8781ec6bd.json)和以本地转录为输入的[整理稿 2960e717](../data/documents/r-2960e717d48e73ec73f34199.json)。前两者正文与分块不同；整理稿记录模型 deepseek-v4.1-flash 并保留待复核状态。

目录以“名称（已知模型）:短 ID”显示结果；模型为路径时仅显示末段，完整值仍在 JSON 中。短 ID 为去掉前缀后的前八个字符，链接指向完整记录。并列和排序不表示质量高低。

## 唯一正文与分块

基础转录、整理稿和文章的全文存于 `text`；动态的原富文本 `content` 合法且独立保存。正文分块统一为 `blocks`，保留数组顺序、原粒度及时间、说话人标签、输入标签、`issues` 等已有事实。块序号按数组位置从零开始。

每块恰有一种正文选择器：`range: [start, end]` 取本记录 `text[start:end]`；`literal` 保存与全文有 Markdown 转义等字面差异的原块值。范围以解析后字符串的 Unicode 码点计数，左闭右开，换行按原字符串计数；它不是 UTF-8 字节偏移或 UTF-16 代码单元。`block_text(document, block)` 还原精确块文字。范围单调排列，允许全文有未被块覆盖的部分；拼接块不替代全文，也不证明没有缺句。

**转录分段**与**整理段落**分别指两种文稿的正文块。整理段落的时间可能只是较长输入音频块边界，不保证逐句或逐字对齐。`time_unit` 的 `ms` 或 `s` 只作用于文稿原已声明的时间轴。

**识别块** `recognition_chunks` 保存识别响应的块偏移、时长、句子及词信息；`offset_seconds`、`duration_seconds` 使用秒，块内时间遵循块自己的 `time_unit`，供应商内部字段沿用原定义。输入快照的 `start_ms`、`end_ms` 仍为毫秒。校验和导出保留原时间顺序与精度。

说话人标签可能只在识别块内有效，相同 `speaker_id` 不证明跨块同一人。人物和观点归属以人工片段归属的适用范围为准。动态不把转发全文冒充作者原文；文章已有 `text_variant` 保留真实字面差异，HTML 另存资产，不互相覆盖。

## 输入与关系

`inputs` 是 `{role, target_id}` 数组：

| role | 含义 |
| --- | --- |
| item | 文稿归属条目，或音频关联的内容条目 |
| audio | 本次转录实际使用的音频资产 |
| transcript | 整理稿已确认的输入转录 |
| derived_from | 同条目整理稿实际文字或注释修订的来源 |
| input_units_from | 同条目另一整理稿的输入参照 |
| article_item | 动态关联的独立文章条目 |
| review_document_markdown / html | 对应独立工件资产 |

每份文稿恰属一个条目；`derived_from`、`input_units_from`、`html`、`review_document_markdown` 各至多一个。真实多来源的 `audio`、`transcript`、`article_item` 分别保留并去重。派生、输入参照及其联合引用图均须无环。

条目的 `relations` 和集合的 `members` 表达各自事实。视频与分 P 的 `parent_id`、从一开始的 `part_number`、集合类型及外部来源编号按原事实保存，不按标题猜测。`has_full_text` 关联全文，`references_video`、`references` 表示参照；参照不证明音频相同，同音频证据使用完整文件 SHA-256。`audible_rerecording_of` 从有声重录版指向原条目并保留依据，不证明音轨相同或时间轴对应。

块可有 `input_text` 或 `input_text_ref`，两者互斥。精确引用形状为：

```json
{"target_id":"TRANSCRIPT_ID","content_sha256":"TARGET_DIGEST","source":"blocks","range":[0,12]}
```

目标必须是本稿通过 `transcript` 角色直接引用的基础转录。`source=text` 取目标 `text`；`source=blocks` 按目标顺序无分隔拼接 `block_text`，再取 Unicode 码点半开区间。摘要必须等于按目标当前原生 `document_hash_input` 重算的摘要，选择器及解析片段须精确匹配。`resolve_input_text(document, block, entities)` 解析输入文字，`entities` 为 `{entity: {id: record}}`。

内联 `input_text` 是独立原始输入事实，不要求与当前上游相同。**输入单位** `input_units` 保存整理时文字、参照片段、时间、质量和当时摘要，粒度可以不同于转录块；它与 `input_units_from` 互斥。`input_units.base.content_sha256`、`metadata.source_sha256` 属历史观测，不随上游新摘要或时间重写。快照里的 `upstream_transcript_id` 是外部标识，不自行转成内部引用。

`input_unit_labels` 只在对应输入定位片段，`evidence_labels` 定位输入侧参照；旧编号不按仓库 ID 解析。`unassigned_reference_labels`、`unresolved_unit_labels` 和附注中的原文、编号及修订字符串分别保留；字段为空不证明正文正确。

## 人工证据与模型标注

人工证据统一在 `annotations`，通过 `targets` 的 `{role, target_id}` 单向指向条目和文稿。每条恰有一个 `item`，文稿目标须属同条目。`applies_to` 只表示证据适用；`revision` 只表示真实采用，目标必须有 `derived_from` 并包含对应修订文字。仅 `revision` 使用 `order`，同一文稿的采用顺序唯一、连续且从零开始。适用、实际采用和全文审核分别核对，文稿不维护第二份反向确认列表。

### 校对标注与参照稿

**校对标注／疑点** `blocks[].issues` 保存 AI 整理或后续修订的疑点、候选改法及说明，顺序保持不变。`note` 记录理由或回查事项；`candidate` 可为词、短语、整句、空字符串、null 或缺省，保留原状态，空值不等于应删除原文。`evidence_labels` 可为空或缺省。

部分候选已用于正文，部分仍需回查；当前没有统一逐条解决状态或问题类别，标注总数不是未解决问题数，AI 候选也不是人工术语释义。回查应结合本块精确文字、输入、时间、标签和[校对目录](catalog/reviews.md)。

`notes_markdown` 是整份结果的附注。独立完整 Markdown 校验稿通过 `review_document_markdown` 输入角色引用资产，可能与结构化块、附注不同，分别保留。`review_markdown` 导出保留完整独立稿及未完整包含的附注；无独立稿时从附注、输入、块及全部标注生成。普通 TXT、正文 Markdown、字幕和正文索引不涵盖完整标注。

`review_issues` JSONL 导出使用 `document_id`、`block_index`、`issue_index`、`path`、`issue`，索引从零开始，定位 `blocks[block_index].issues[issue_index]`；`path` 指实际维护文件。它不生成独立维护 ID，也不推断解决状态。操作见[正文与标注导出](QUERY.md#导出正文与标注)。

### 人工确认

`kind=confirmation` 保存已审核局部字句或术语、原文锚点、修订文字和适用整理稿。`anchor` 保留 `original_text`、精确 UTF-8 哈希及已有输入单位标签；`corrected_text` 及其哈希保存确认后的文字。`term_glosses` 只保存明确记录的词义或简称解释，适用范围由该确认限定。

`scope`、`status`、`confirmation` 保留范围、摘录、结论、审核角色、日期、时区和听音事实。`review_timezone` 是观测标签，原样保存，不据此换算时间或推断真实身份。`scope=local_text_or_term` 只覆盖确认的字句或术语；适用不证明采用，采用不证明全文审核或内容使用权。

### 片段说话人与观点归属

`kind=segment_attribution` 保存人工审核认定的块或块内一句由谁说出、表达谁的观点，恰有一个 `applies_to` 文稿。原生 `anchor.paragraph_index` 就是该文稿 `blocks` 的从零开始位置；保留这一字面字段。`paragraph_text_sha256` 为 `block_text` 精确文字的 UTF-8 SHA-256；`excerpt=null` 表示整块，否则须为块内原文子串。`start`、`end`、`time_unit` 与目标块及文稿一致。

`speaker_role` 取 `primary_speaker`、`other_speaker`、`unknown`，主讲人由审核者认定，不由标题、上传者或识别标签推断。`viewpoint` 取 `own_view`、`quoted_or_read_aloud`、`explained_or_paraphrased`、`unknown`。没有记录表示未审核，与审核后仍未知不同。

`review` 保留审核者原话 `basis`、角色、日期、时区、看过视频和助手听音的事实及可选链接；`status=human_confirmed`。模型候选不写成人工归属。块文字改变后须重新审核、另建证据，不能只刷新旧哈希。归属不确认文字正确，文字确认不代替归属确认，两者都不自动改变全文质量状态。

## 工件、恢复位置与哈希

音频保存文件 SHA-256、大小、条目关联和恢复定位。`local_path` 指仓库相对恢复路径或已有工件路径。ZIP 描述仅在 `kind=archive` 资产中保存 `name`、`size_bytes`、`sha256`、`url`；音频 `downloads` 的 `archive_id` 直接指向该资产，配合原 `member_path`、`release_tag` 定位。恢复链限于音频到 ZIP，操作见[音频恢复](PRESERVATION.md#音频恢复)。

独立校验稿和 HTML 保留原 UTF-8 字符串、换行和文件字节，由文稿引用资产。识别块、词信息和快照继续内嵌。未保存过的响应字节不补造，已有识别块也不冒充供应商原始响应。

各种哈希按对象区分：

- 音频、ZIP 和工件 `sha256` 校验实际文件字节。
- `document_hash_input(document)` 显式取记录中存在的 `kind`、`inputs`、`method`、`language`、`model`、`time_unit`、`text`、`content`、`blocks`，以 `json_sha256` 计算。缺省保持缺省，null 保持 null；不含 `id`、`metadata`、`quality` 或摘要自身。只有 `transcript` 必须保存 `content_sha256`，输入引用使用相同目标载荷摘要。
- `recognition_chunks_sha256` 是识别块数组的独立规范 JSON 哈希，不替代文稿摘要。
- 文字锚点哈希校验指定原文字串的 UTF-8 字节。

规范 JSON 使用排序键、紧凑分隔符、未转义 Unicode，并拒绝 NaN。ID 不因结构整理重新分配；历史输入和来源摘要维持原事实。当前摘要转换映射见[整理证据](evidence/native-v3-cleanup-2026-11-17.json.gz)，实际执行结果以[实施记录](NATIVE-V3-CLEANUP.md)为准。批次字节、完整载荷与计划摘要见[哈希边界](INCREMENTAL-INGEST-SPEC.md#哈希边界)。

<a id="元数据派生值与旧格式投影"></a>

## 元数据、派生值与读取 Interface

**记录 ID** 是稳定、不透明的内部标识；新增真实不同结果使用新 ID。外部标识在 `identifiers` 命名空间内，不自动转成仓库引用。`metadata` 保留既有标量、对象或观测列表的原形；新增并列观测按所属字段约定保存，批次追加规则见[增量协议](INCREMENTAL-INGEST-SPEC.md#操作与合并规则)。对象或数组可作为一次完整观测，不递归展开或覆盖不同值。`created`、`ctime`、作者和上传者不因近似而合并；原日期、Unix 秒、模型、来源和哈希观测按事实保留。平台对象里的 `review`、`video_review`、`disable_preview` 不是人工审核状态。

唯一读取与写入 Interface：

| 名称 | 返回或作用 |
| --- | --- |
| `ENTITIES` / `JSONL_ENTITIES` | 四实体名称 / 三个 JSONL 实体名称 |
| `iter_records(root, entity, *, kind=None)` | 逐条返回原生记录及实际 `Path` |
| `load_document(root, id)` / `record_path(root, entity, id)` | 原生文稿 / 实际维护路径 |
| `input_ids(record, role)` / `block_text(document, block)` | 按角色取输入 / 还原块文字 |
| `resolve_input_text(document, block, entities)` | 解析内联输入或精确引用 |
| `document_hash_input(document)` / `json_sha256(value)` | 文稿摘要载荷 / 规范 JSON 摘要 |
| `validate_corpus(root)` / `schema_v3.validate_native(root)` | 原生实体、kind 与块计数 / 错误列表 |
| `write_record_updates(root, {entity: rows})` | 原生 upsert；候选整图校验后返回实际变化的仓内相对 `Path` 列表 |

`install_candidate_updates(root, candidate, paths)` 是唯一安装 primitive，目标和候选根互不嵌套；只安装明确路径，候选文件保留，候选中缺失的指定路径表示删除。每个文件先复制到临时文件再 `os.replace`，可捕获的 I/O 失败会尝试回滚。它不提供多文件事务原子可见性。记录写入 Interface 不提供删除操作；批次另加锁、持久中断标记及读回，见维护说明。

JSON/JSONL 导出直接返回原生记录。TXT、Markdown、字幕、CSV 和 SQLite 是派生结果；SQLite 仅保存四实体表及可重建正文索引，目录与 CSV 指向当前文稿文件。

## 质量、完整性与可用状态

| 名称 | 字段或值 | 限定含义 |
| --- | --- | --- |
| 结果完成 | is_complete | 输出已完成，不保证音频全覆盖、识别无遗漏或审核完成 |
| 全文人工复核 | is_fully_human_reviewed | 全文已经实际人工核查 |
| 待复核 | requires_review | 结果需要继续检查 |
| 字幕导出启用 | is_subtitle_export_enabled | 启用导出，仍须通过实际时间与序列化检查 |
| 识别异常区间 | recognition_issue_intervals | 已记录的识别或时间异常范围 |
| 正文可用 | transcript_text_available | 对应区间存在文字 |
| 可恢复音频 | availability=available | 有恢复定位，不承诺远端永久在线 |
| 不可获取音频 | availability=unavailable | 没有可用下载定位，不表示确认静音 |

false 表示明确否，null 表示原数据未说明；未知状态、原质量报告和人工或模型判断原样保留。局部确认不提升全文复核状态。`is_complete=false`、`partial_model_output` 等状态保留实际含义。`paragraphs_match_text=false` 是已有的质量观测，块与全文分别保留；`has_expand_prompt` 表示采集页面是否仍有展开提示，不等于校对疑点。

时间倒退、无效范围或不能无损表示为毫秒的数值使字幕导出失败；不排序、钳制或取整修复。`recognition_issue_intervals.start_seconds/end_seconds` 使用独立秒单位。既有报错、异常原因、识别块及模型证据分别保留；当前时间问题按当前原值派生，原报告并存，不伪造“已修复”。

`audio_assessment` 保存已有音频判断；用户明确确认无声时可记录 `silent_audio_confirmed` 和 `audio_assessment_evidence` 的原话、日期、时区与依据。确认静音、时间不可用、未返回词、正文存在、字幕不可用、缺失音频和全文复核互不推断。

`quality.input_quality` 是输入当时的判断，整理稿 `quality` 是结果自身状态；不能用当前上游覆盖历史快照。转录存在也不表示对应音频可恢复。

<a id="迁移与验收"></a>

## 当前整理与验收

本次处理的是既有四实体数据：清理旧字段依赖并采用唯一原生 Interface，不重新执行旧格式迁移。当前实施记录与逐条摘要映射分别见 [NATIVE-V3-CLEANUP](NATIVE-V3-CLEANUP.md) 和[压缩证据](evidence/native-v3-cleanup-2026-11-17.json.gz)。完成状态以其中实际检查结果为准。

执行[维护后检查](MAINTENANCE.md#维护后检查)，核对来源、全文、精确块文字、输入、时间、模型、质量、人工证据及工件字节。历史提交、入库收据、保存清单和冻结工件保持原字节，按自己的版本解释；新协议不重放历史收据。
