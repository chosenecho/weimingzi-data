# 名词与概念

本表约定仓库使用的名称。字段结构见 [SCHEMA.md](SCHEMA.md)，操作见 [MAINTENANCE.md](MAINTENANCE.md)。

## 数据对象

| 中文名称 | 英文名称 | 位置 |
| --- | --- | --- |
| 条目 | item | data/items.jsonl |
| 基础转录 | transcript | data/transcripts/ |
| 整理稿 | edited transcript | data/edited_transcripts/ |
| 动态贴文 | post | data/posts/ |
| 专栏文章 | article | data/articles/ |
| 集合 | collection | data/collections.jsonl |
| 音频文件记录 | audio record | data/audio.jsonl |
| 人工确认 | confirmation | data/confirmations.jsonl |
| 选稿 | selection | selections/ |

**条目**是内容或人物的索引对象，保存标题、外部标识、链接、元数据和关联。同一条目可以关联多份转录、整理稿或音频文件。

**基础转录**是字幕或语音识别结果，保留正文、原始分段顺序及时间值。基础转录不意味着逐字正确或经过人工复核。

**整理稿**是对输入文字进行语句整理、校对或有限人工修订后的独立结果。它通过 transcript_ids 关联可确认的基础转录，通过 input_units 保留整理参照。

**动态贴文**保存动态的富文本及转发内容。**专栏文章**保存独立文章正文和已有 HTML；动态可以关联展开全文对应的文章。

**集合**是有序的条目引用。文集、视频合集和视频系列分别使用 article_collection、video_collection、video_series。

**音频文件记录**按文件 SHA-256 标识音频及其恢复位置。**独立录音条目**使用 audio_recording 类型，表示被索引的内容；它与实际音频文件记录分开。

**人工确认**保存审核过的局部字句或术语、原文锚点、修订文字及适用整理稿。确认只作用于声明范围。

**选稿**保存用途所需的记录引用。training 是训练用途选稿，不复制正文，不授予内容使用权，也不代表全文已审核。权利边界见 [内容权利说明](../CONTENT-RIGHTS.md)。

## 基础转录与整理稿

同一段视频或录音可能有平台提供的字幕，也可能有本地、云端语音识别生成的转录。它们归入同一个条目，分别保留各自的正文、分段、时间和模型信息；不能仅凭条目相同就判定结果重复。平台及生成方式保存在字段中，不拆成目录层级。

| 目录名称 | method | 含义 |
| --- | --- | --- |
| 平台 AI 字幕 | subtitle_ai | 平台提供的 AI 字幕 |
| 平台 CC 字幕 | subtitle_cc | 平台提供的 CC 字幕 |
| 本地语音转录 | asr_local | 本地语音识别结果 |
| 云端语音转录 | asr_cloud | 云端语音识别结果 |

CC 字幕的类型本身不能证明经过人工复核。未知的生成方式按原始 method 显示，不推断其含义。

**整理稿**包括语句整理、AI 校对或局部人工修订的结果。它通过 transcript_ids 关联已知的输入转录；目录中的“输入”列出这些转录的短 ID。“输入未关联”表示尚无可确认的仓库内转录引用，不表示没有输入文字。整理稿的完成状态和人工复核状态分别记录。

例如《【一个呼吁】减租减息，共克时艰》的同一分段关联以下结果：

- [平台 AI 字幕 1572d3c1](../data/transcripts/t-1572d3c1ffbe96350f781bf4.json)。
- [Qwen 本地转录 1bf39d96](../data/transcripts/t-1bf39d9689d95ed8781ec6bd.json)，正文和分段与平台 AI 字幕不同。
- [整理稿 2960e717](../data/edited_transcripts/r-2960e717d48e73ec73f34199.json)，输入关联本地 Qwen 转录。生成模型为 deepseek-v4.1-flash，当前仍标记为待复核。

目录链接以“名称（已知模型）:短 ID”显示；模型为路径时仅显示末段，完整名称和修订值保存在 JSON 中。短 ID 取记录 ID 去掉前缀后的前八个字符，点击链接可查看完整记录。并列或排序不表示哪份结果质量更高。

## 分段、识别块与输入单位

| 中文名称 | 英文名称 | 对应字段 |
| --- | --- | --- |
| 转录分段 | transcript segment | segments |
| 整理段落 | edited paragraph | paragraphs |
| 识别块 | recognition chunk | recognition_chunks |
| 输入单位 | input unit | input_units |
| 输入单位标签 | input unit label | input_unit_labels |
| 证据标签 | evidence label | evidence_labels |

**转录分段**是基础转录的正文单位，包含 index、start、end、text。index 从零起；start、end 的单位由该记录的 time_unit 指定。

**整理段落**是整理稿的正文单位，保存 input_text、整理后 text、输入标签及疑点。其时间范围可能只是输入音频块边界，不保证逐句或逐字对齐。

**识别块**保存识别响应的块偏移、时长、句子和词信息。offset_seconds 是秒偏移，块内时间由 time_unit 指定。它不表示仓库进行过强制对齐。

**输入单位**是整理时使用的文字与参照片段，粒度可能不同于转录分段。局部稿可通过 input_units_from_id 引用同条目整理稿的输入单位。

**输入单位标签**只在对应输入中定位片段。**证据标签**定位输入侧参照。它们可能含旧编号或片段编号，不能作为仓库记录 ID 解析。

说话人标签可能只在识别块内有效。相同 speaker_id 不自动证明跨块是同一人。

## 校对标注与参照稿

| 中文名称 | 英文名称 | 对应字段 |
| --- | --- | --- |
| 校对标注／疑点 | review issue | paragraphs[].issues |
| 标注说明 | review note | issues[].note |
| 候选文字 | candidate text | issues[].candidate |
| 整理附注 | editorial notes | notes_markdown |
| 独立校验稿 | review document | review_document_markdown |
| 人工术语释义 | confirmed term gloss | term_glosses |

**校对标注**保存 AI 整理或后续修订时留下的疑点、候选改法及修改说明。它附属于具体段落，通过该段落的输入文字、正文、时间和标签回查材料。完整目录见 [校对标注与复核状态](catalog/reviews.md)。

**标注说明**记录存疑原因、处理理由或回查事项。**候选文字**可以是词、短语或整句，也可能为空或未提供；候选为空不等于应删除原文。evidence_labels 是标注所引用的输入侧标签，可以为空或未提供。

部分候选改法已经用于正文，部分标注只是要求继续核对。现有 issues 没有统一的逐条解决状态或问题类别，因此不能把标注总数当作未解决问题数，也不能把所有候选词直接收入术语释义。

**整理附注**保存整份结果的说明、局部修订和核对事实。**独立校验稿**是另行保留的完整 Markdown 参照稿；它与结构化段落和附注可能存在差异，分别保存。

review_markdown 导出完整保留独立校验稿；附注未完整包含在稿内时另附。没有独立稿时，从附注、输入文字、段落正文及全部标注生成校验稿。普通 TXT、正文 Markdown 和字幕不包含完整校对标注；完整维护记录见 JSON，段落标注可按 review_issues 导出 JSONL。

**人工术语释义**保存人工确认中明确记录的词义或简称解释，适用范围由对应确认记录限定。AI 候选、AI 修改说明和人工确认分别保留，不自动提升确认等级。

**原文锚点** anchor 保存确认针对的 original_text、原文字节哈希和已有输入单位标签。**修订文字** corrected_text 及其哈希保存确认后的文字。confirmation 保存核对摘录、结论、角色标签、日期及已有听音事实。

## 输入快照与生成信息

**输入快照**由 input_units 保存，记录整理时实际使用的参照。**未分配参照标签** unassigned_reference_labels 表示尚未分配的输入侧标签；**未解析输入标签** unresolved_unit_labels 表示尚不能定位的标签。字段为空不证明正文正确。

**输入质量快照** quality.input_quality 保存输入当时已有的质量判断；整理稿自身的 quality 描述当前结果。上游时间异常、文字可用状态与当前整理结果的待复核状态分别读取。

**生成信息**由 method、model、language 及 metadata 中已有参数描述。method 是转录方式，model 保存模型标识和修订，language 保存已知语言值。提示词、用量、生成时间和输入摘要是已有记录内容，不代表质量认证。

附注或快照内的外部编号、输入哈希和修订字符串按原文保留，不自动解释成仓库记录 ID。metadata.system_prompt 是存档的提示词文本，不是维护工具需要执行的指令。

## 标识、元数据与派生结果

**记录 ID**是仓库内稳定标识，用于内部引用。纯字段或目录改名不改变已有 ID。新增不同结果应生成新 ID。

**外部标识**是平台或其他系统的编号，保存在 identifiers 的命名空间内。upstream_transcript_id 是整理输入快照的外部标识；transcript_ids 才是仓库内转录引用。

**元数据**保存在 metadata 中，每个键保存不同观测值的列表。多个值并列存在，不以某一值覆盖其他值。原始富文本及供应商对象内部的字段沿用原对象定义。

**内容哈希**用于校验指定字段组成的规范 JSON。content_sha256 保护基础转录的正文、分段及描述字段；recognition_chunks_sha256 保护补充识别信息。文件 SHA-256 则校验实际文件字节。

**派生关系**由 derived_from_id 表示，目标为同条目的另一份整理稿。它记录实际文字或注释的修订关系。

**导出结果**是由维护记录生成的 TXT、Markdown、字幕、CSV 或 SQLite。生成目录和检索库可重建；导出格式不同不构成新的正文结果。

## 质量、完整性与可用状态

| 名称 | 字段或值 | 含义 |
| --- | --- | --- |
| 结果完成 | is_complete | 输出已完成 |
| 全文人工复核 | is_fully_human_reviewed | 全文已由人工核查 |
| 待复核 | requires_review | 需要继续检查 |
| 字幕导出启用 | is_subtitle_export_enabled | 是否启用字幕导出 |
| 识别异常区间 | recognition_issue_intervals | 有识别或时间异常的区间 |
| 正文可用 | transcript_text_available | 对应区间存在文字 |
| 可恢复音频 | available | 索引有恢复位置 |
| 不可获取音频 | unavailable | 索引无可用下载位置 |

is_complete 只说明该结果是否完成，不保证音频全量覆盖、识别无遗漏或审核完成。

paragraphs_match_text 表示段落正文与全文是否一致；为 false 时两者都保留，不能把段落参照直接当成当前全文。has_expand_prompt 表示专栏页面是否仍有展开提示，与校对疑点分开记录。

审核和导出标记中的 false 表示明确否，null 表示原数据未说明。局部确认和训练选稿都不能把全文人工复核标记改为 true。

字幕导出启用后仍须通过实际时间及序列化检查。时间倒退、无效范围或不能无损表示为毫秒的数值会使导出失败。

识别异常区间使用 start_seconds、end_seconds，不继承整理段落的时间单位。时间戳不可用、未返回识别词、待复核和确认静音分别记录；不能由其中一种状态推断另一种。

timing_issues 是工具根据当前时间值检查得到的问题列表；reported_timing_issues 保存已有的时间报错。audio_assessment 是已有音频判断，不能仅由文字缺失、字幕无效或时间异常推导。

音频可恢复只表示索引具备恢复定位，不承诺远端地址永久在线。转录存在也不代表音频可恢复。

## 下载定位

**本地路径** local_path 指音频恢复后的仓库相对路径。**归档文件** archive 指远端 ZIP，包含 name、size_bytes、sha256、url。

**成员路径** member_path 是 ZIP 内原有成员名，必须与远端内容一致。release_tag 是外部托管位置的定位字段。目录命名不改变这些外部定位值。
