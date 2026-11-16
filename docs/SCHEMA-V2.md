# 数据结构

所有维护记录使用 UTF-8 JSON 或 JSONL，schema_version 为 2。数量见 [counts.json](counts.json)，校验入口为 [records.py](../src/weimingzi_corpus/records.py)。对象定义见 [名词与概念](GLOSSARY.md)。

## 命名约定

目录、字段和项目自定枚举使用 snake_case。布尔字段使用能直接表达判断的名称；未知状态保留 null，不转为 false。

仓库记录引用使用 *_id、*_ids；输入侧标签使用 *_label、*_labels；外部标识保留命名空间。原始富文本、供应商响应、术语键、提示词和正文内部的名称按原对象保留。

日期使用 *_on，日期时间使用 *_at；Unix 数值标明 *_unix_seconds。文件大小使用 size_bytes，采样率使用 sample_rate_hz。元数据中的 duration_ms、duration_seconds 保留各自单位，不统一换算原值。

## 条目与关系

data/items.jsonl 每行一个条目。kind 使用 video、video_part、audio_recording、post、article、person。视频与分 P 通过 parent_id、part_number 关联；part_number 从一开始。

| 字段 | 含义 |
| --- | --- |
| id | 仓库内稳定标识 |
| title | 展示标题 |
| identifiers | 外部标识及命名空间 |
| urls | 内容链接 |
| metadata | 并列元数据观测值 |
| relations | 关联条目、关系及依据 |

metadata 的每个键保存不同观测值的列表。对象或数组本身也可作为一次观测值，因此部分字段存在嵌套数组。补充元数据时保留已有不同值，不以采集批次覆盖其他值。

时长和发布时间的同义字段统一到 duration_ms、published_at_unix_seconds、published_at。链接和图片使用 source_url、youtube_url、bilibili_url、resolved_url、image_urls；上传者使用 uploader_id、uploader_name。

observed_at 保存日期时间字符串，observed_at_unix_seconds 保存秒数观测；原值不丢弃。

duration、cover、created、ctime 等原始字段的含义或类型可能不同，不能按名称近似直接合并。上传者与内容归属作者分别保留。平台信息作为字段存在，不形成目录层级。

relations 每项使用 target_item_id、kind 和可选 evidence。has_full_text 表示关联全文，references_video 和 references 表示参照。参照关系不证明音频相同，音频同一性按文件 SHA-256 判断。

audible_rerecording_of 从有声重录版指向原条目，保存确认依据和日期。它表示重录关系，不证明音轨相同或时间轴逐段对应；文稿仍归属于实际有声版本。覆盖查询将该关系列入 cross_source。

## 基础转录

data/transcripts/<id>.json 保存一份转录结果。item_id 指向条目；method、model、language 描述结果。method 使用 asr_local、asr_cloud、subtitle_ai、subtitle_cc 等项目自定值。

audio_ids 引用 data/audio.jsonl 中的文件记录。音频记录的 item_ids 则关联内容条目；两类引用不互相代替。

model 为对象或 null；对象包含 name 和可选 revision。模型名、路径或修订值原样保存。language 保留已知原值，不能仅凭字幕类型推断语言编码。

text 是全文，segments 保存原始顺序的分段。每段含 index、start、end、text；index 从零起。time_unit 为 ms 或 s，作用于正文分段。说话人标签及块偏移按记录保存，不自动建立跨块人物身份。

content_sha256 校验 item_id、method、language、model、time_unit、text、segments 组成的规范 JSON。编码使用 sort_keys=True、ensure_ascii=False、紧凑分隔符，并拒绝 NaN。字段结构调整后重新计算哈希，已有记录 ID 保持不变。

quality.timing_issues 必须准确描述存储时间值的问题。校验不排序、截断、取整或修补原值。quality.is_subtitle_export_enabled 为 false 时禁用字幕导出；为 true 或 null 时仍须通过时间精度及序列化检查。

recognition_chunks 保存补充识别块。每项含 id、offset_seconds、duration_seconds、time_unit、text、sentences，以及已有质量信息。sentences 和 words 保留供应商字段及块内时间。recognition_chunks_sha256 单独保护这些信息，不替代正文分段。

## 整理稿与输入单位

data/edited_transcripts/<id>.json 每份结果包含 text、paragraphs、model、notes_markdown、is_complete、quality。transcript_ids 关联可确认的基础转录，无法确认的关系留空。

| 段落字段 | 含义 |
| --- | --- |
| index | 从零起的段落索引 |
| input_text | 整理时的输入文字 |
| text | 整理后正文 |
| input_unit_labels | 输入单位标签 |
| issues | 校对疑点、候选文字及修改说明 |
| start / end | 回查用时间范围 |

issues 是标注数组，每项保存 note，可带 candidate、evidence_labels。note 为说明文字；candidate 为字符串，允许空字符串或不提供。evidence_labels 为字符串数组，允许空数组或不提供，表示输入侧证据标签，不是仓库记录 ID。

标注可能记录未确定的内容，也可能说明已经用于正文的修改。当前没有统一的逐条解决状态和问题类别；不能仅凭标注存在、候选为空或全文待复核标记推断其解决状态。issues 的次序和各项原文全部保留。

time_unit 描述段落时间单位。时间范围可能来自较长的输入音频块，不表示逐字、逐句对齐。paragraphs_match_text 表示段落正文与全文的一致性。不同措辞作为独立结果保留。

notes_markdown 保存整份结果的附注，review_document_markdown 保存独立的校验参照稿。后者存在时，review_markdown 导出保留其完整内容；附注未完整包含在稿中时追加附注。结构化段落、附注和独立稿分别存储，不互相覆盖。

input_units 保存整理时的输入参照。base 包含 upstream_transcript_id、content_sha256、method、language、segments；其中每段使用 label、start_ms、end_ms、text 及已有字符范围和块标记。upstream_transcript_id 属于输入快照，不作为内部转录外键。

input_units.unassigned_reference_labels 保存未分配参照标签。局部稿可用 input_units_from_id 引用同条目另一份整理稿的输入单位。quality.unresolved_unit_labels 列出尚不能解析的输入标签。

is_complete=false 表示结果未完成或只覆盖部分输入。partial_model_output 标记保留在质量状态中。完成状态不等于音频全量覆盖、全文复核或无遗漏。

derived_from_id 表示实际文字或注释修订关系，目标必须为同条目整理稿，且不得成环。confirmation_ids 关联适用的人工确认。多份整理稿并列归档，发布 head 由下游消费配置决定，见[消费配置交接](RELEASE.md)；原始稿本身不改字节。

## 动态、文章和集合

data/posts/<id>.json 的 content 保留完整富文本对象，包括转发内容、图片和卡片。article_item_ids 关联展开全文对应的专栏文章；纯文本导出不替代富文本。

data/articles/<id>.json 保存 text 和已有 html。确有差异的文本可使用 text_variant 保留。quality.has_expand_prompt 标记采集页面是否仍有展开提示，不能按文件存在推断全文完整。

data/collections.jsonl 的 kind 使用 article_collection、video_collection、video_series。members 按 position 保存有序 item_id 引用，position 从一开始。成员不复制正文。

集合外部编号分别使用 identifiers.bilibili_article_list、bilibili_season、bilibili_series；命名空间说明编号含义。

## 音频恢复索引

data/audio.jsonl 按音频文件 SHA-256 合并记录。kind 为 audio，item_ids 关联条目。

| 字段 | 含义 |
| --- | --- |
| availability | available 或 unavailable |
| sha256 | 音频文件 SHA-256 |
| size_bytes | 音频文件字节数 |
| local_path | 本地恢复相对路径 |
| downloads | 归档下载位置 |

available 表示索引具有恢复位置，需保存 size_bytes、local_path、downloads。unavailable 保存已知文件标识及缺失说明，不表示文件确认静音。

每个 downloads 成员包含 release_tag、archive、member_path。archive 保存 ZIP 的 name、size_bytes、sha256、url。member_path 必须使用远端 ZIP 内原成员名。完整规则见 [DOWNLOAD.md](DOWNLOAD.md)。

## 人工确认

data/confirmations.jsonl 用 item_id、edited_transcript_ids 关联条目和整理稿。局部确认保存 anchor、corrected_text、对应哈希及 term_glosses；scope、status 和 confirmation 说明范围、状态与核对事实。

anchor 使用 original_text、original_text_sha256、input_unit_label。term_glosses 保存术语释义，键保留原文。scope=local_text_or_term 限定局部字句或术语，不表示全文通过审核。

confirmation 包含 excerpt、resolution、reviewer_label、reviewed_on、review_timezone 和已有听音事实。reviewer_label 是原记录中的角色说明，不推断真实身份。reviewed_on 保留日期，review_timezone 明确为 Asia/Hong_Kong。

确认必须属于对应条目、适用于记录中列明的整理稿，并能定位到原文或修订文字。局部确认不改变 quality.is_fully_human_reviewed，也不授予第三方内容使用权。

训练选稿和发布视图指针由制作工程的 configs/corpus/ 维护，字段与命令见[消费配置交接](RELEASE.md)。本仓基础校验不读取这些配置。selections/topics.json 仅保存资料专题查询规则，见[专题查询](TOPICS.md)。

## 片段说话人与观点归属

data/attributions.jsonl 保存人工确认的片段归属，kind=segment_attribution，ID 前缀 s-。每条记录用 item_id、edited_transcript_id 指向一个条目和一份整理稿。

anchor 保存 paragraph_index（零起）、paragraph_text_sha256、excerpt、start、end、time_unit。paragraph_text_sha256 是该段 text 的 UTF-8 SHA-256；excerpt 为 null 表示整段，否则须是段内原文子串。start、end、time_unit 与该段及整理稿一致，供回查时间位置。段落文字改动后哈希不再匹配，校验失败，须重新审核后另建记录。

speaker_role 取 primary_speaker、other_speaker、unknown。primary_speaker 指审核者认定的本条主讲人，不由上传者、标题或识别说话人标签推断。

viewpoint 取 own_view（说话人陈述本人观点）、quoted_or_read_aloud（朗读来信、引述他人原话）、explained_or_paraphrased（讲解或转述他人观点）、unknown（已审核但无法判断）。

review 保存 basis、reviewer_label、reviewed_on、review_timezone、reviewer_reported_watched_original_video、assistant_listened_to_audio，可选 source_url。basis 保留审核者原话。status 只接受 human_confirmed；模型候选不写入本表。

没有归属记录表示未审核，与 unknown 不同。归属记录不确认文字正确，不改变 quality，也不授予内容使用权；文字确认不能升级为归属确认。下游作为作者本人参照时，只采用 speaker_role=primary_speaker 且 viewpoint=own_view 的范围。

## 质量与异常区间

quality.is_fully_human_reviewed、requires_review、is_subtitle_export_enabled 使用布尔值或 null。仅实际核查全文后才能标记全文人工复核；局部确认不能扩张范围。

recognition_issue_intervals 保存识别或时间异常区间，使用 start_seconds、end_seconds、reason 及已有证据。这个秒单位独立于正文和段落的 time_unit。

证据引用中的 transcript_id 指向基础转录，recognition_chunk_ids 指向其识别块。transcript_text_available 标明对应区间是否存在正文。

quality.audio_assessment、reported_timing_issues 等已有判断分别保留。无识别词、时间异常、确认静音、不可用字幕和音频缺失不相互推断。输入质量快照保存在 quality.input_quality，仍使用相同字段约定。

用户明确确认原分 P 无声时，可将 audio_assessment 记录为 silent_audio_confirmed。

audio_assessment_evidence 保存 basis=user_confirmation、原话、confirmed_on、时区及证据位置。条目级判断保存为 metadata 中的观测值；转录级质量判断与其依据分别保留。

确认无声不改变音频索引的文件可恢复状态，也不代表整理稿已人工复核。

metadata.review_status 是已有的结果状态观测。平台对象中的 review、video_review、disable_preview 等原始名称不自动解释成校对或人工审核状态。

## ID、导出与更新

id 是稳定、不透明的内部标识。现有 i-、t-、r-、d-、a-、c-、m-、s- 前缀继续用于定位记录，引用同时校验目标表；纯命名调整不生成新记录。

新增不同结果时生成新 ID。元数据补充、JSON 排版、文件位置或导出格式不同，不构成新的正文结果。校验拒绝重复 ID、失效引用及跨条目派生。

SQLite 为可重建的检索结果，各维护表保存 id、item_id、record_json，content_search 索引正文；不包含下游选稿配置。CSV 的 record_path 指向维护 JSON，不是音频 local_path。

review_issues 导出为 JSONL，每行保存一个完整的 issue 对象。定位字段为 edited_transcript_id、item_id、paragraph_index、issue_index、record_path。

两个 index 均从零开始，定位到原记录 paragraphs[paragraph_index].issues[issue_index]。不生成独立维护 ID，不推断问题类别或解决状态。

docs/catalog/reviews.md 列出全部整理稿的标注数量、待复核状态、完成状态、附注及独立稿存在情况。counts.json 中的标注计数如下；这些数量均不代表未解决问题数量。

| 计数字段 | 统计对象 |
| --- | --- |
| review_issues | 段落校对标注 |
| paragraphs_with_review_issues | 含标注段落 |
| edited_transcripts_with_review_issues | 含标注整理稿 |
| edited_transcripts_with_notes | 有附注的整理稿 |
| edited_transcripts_with_review_documents | 有独立校验稿的整理稿 |
