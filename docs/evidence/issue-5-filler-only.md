# BV1CP4y1s7BM P2 无声源与 P1 有声重录版

核查日期：2026-11-05。原转录见 [t-79e1eb0ea7c54df6013b144c.json](../../data/transcripts/t-79e1eb0ea7c54df6013b144c.json)。

## 用户确认

用户于 2026-11-05 在本次对话确认，时区为 Asia/Hong_Kong。原话：

> BV1CP4y1s7BM P2就是没声音的，BV1CP4y1s7BM P1是p2的有声重录版

P2 按用户确认的无声源记录；P1 是对应的有声重录版。此判断的依据是用户确认，并非本次重新听音或波形测量。

## 原转录证据

原转录的 text 是“嗯。”重复 22 次，共 44 个字符，见[存储文本与分段](../../data/transcripts/t-79e1eb0ea7c54df6013b144c.json)。

segments 只有一项，其文字与 text 相同，时间范围为 0 至 3675000 毫秒，见上述记录。原 timing_issues 为空；这些时间值通过结构检查，不代表正文有实质内容。

原始条目及上游定位见该记录的 item_id、metadata.transcript_id=1881 和 metadata.video_part_id=1438。对应 P2 条目为 i-00971e5f62c6b8a2afc33acc，CID 为 377196179。条目元数据时长 3803000 毫秒，见 [items.jsonl](../../data/items.jsonl)。

## 已补充的质量状态

quality.content_assessment 将该结果标记为 filler_only，依据仅为已存储文本。eligible_as_substantive_transcript=false 表示不能把它计作有实质内容的转录。source_audio_checked=false 保留当时未测量音频的事实，文本筛查本身不判定静音。

本次另补充 quality.audio_assessment=silent_audio_confirmed。audio_assessment_evidence 保存 basis=user_confirmation、上述原话、确认日期、时区和本文件位置；条目 metadata 也保留相同判断及依据。这项用户确认与原文本筛查分别保存。

text、segments、model、content_sha256、原 metadata、audio_ids 和原复核标记均保留。内容哈希仍为 65c4b62ded7f6b0fa878f8e2a5fd72207fca2c3742a28474ade904968544a4da；assessment 中保存相同哈希以定位本次核查对象。

[覆盖查询](../COVERAGE.md)会分别返回总转录数、text_present_transcripts、filler_only_transcripts 和 empty_transcripts。该 P2 当前只有这份直接转录，无直接整理稿；P1 的可读文稿通过重录关系作为相关覆盖返回。

    python tools/corpus.py coverage BV1CP4y1s7BM --part 2 --include-records

## P1 已有文稿与关联范围

P1 条目为 i-8520cf119fcad17735d1fb60，CID 为 377219995，见 [items.jsonl](../../data/items.jsonl)。已有文稿为：

- [本地 ASR 转录](../../data/transcripts/t-f87ba197d7b776c27aa62a58.json)。
- [平台 AI 字幕转录](../../data/transcripts/t-0e80e9989a8827ed4f481269.json)。
- [整理稿](../../data/edited_transcripts/r-3dd2af3cb9bf5fcc38f95caf.json)。

该整理稿 is_complete=true，requires_review=true，is_fully_human_reviewed=false；完成状态和复核状态分别保留。

P1 的 audible_rerecording_of 关系指向 P2，保存用户确认依据。查询 P2 时，cross_source 返回 P1 文稿；direct 仍只包含实际归属于 P2 的记录。重录关系不证明同一音轨或逐段时间对应，P1 的正文、输入转录和时间轴均保留在 P1。

## 处理结论与历史说明

本问题按“原分 P 已确认无声，内容查有声重录版 P1”处理，不再等待另一个 P2 备用音频文件，也不要求从无声 P2 补出实质转录或整理稿。

[issue #5](https://github.com/chosenecho/weimingzi-data/issues/5)在 2026-11-04 的说明曾提到其他渠道音频。本次 2026-11-05 的用户确认明确了可用版本为 P1，取代此前等待备用文件的处理路径。

仓库音频索引中对应记录仍为 unavailable，local_path=null，见 [audio.jsonl](../../data/audio.jsonl)。音频 ID 为：

    m-3f2f3ca7b3260f48f3799764aedf950fdbf3e718952b7d2117766983fe21b4e3

这里的 unavailable 表示仓库文件恢复位置缺失，与用户确认原分 P 无声分别记录。旧转录和原质量标记继续保留；P1 整理稿的完成状态也不提升为人工审核通过。
