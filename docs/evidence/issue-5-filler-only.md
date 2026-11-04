# BV1CP4y1s7BM P2 的文本质量核查

核查日期：2026-11-05。原转录见 [t-79e1eb0ea7c54df6013b144c.json](../../data/transcripts/t-79e1eb0ea7c54df6013b144c.json)。

原转录的 text 是“嗯。”重复 22 次，共 44 个字符，见[存储文本与分段](../../data/transcripts/t-79e1eb0ea7c54df6013b144c.json)。

segments 只有一项，其文字与 text 相同，时间范围为 0 至 3675000 毫秒，见上述记录。原 timing_issues 为空；这些时间值通过结构检查，不代表正文有实质内容。

原始条目及上游定位见该记录的 item_id、metadata.transcript_id=1881 和 metadata.video_part_id=1438。对应 P2 条目为 i-00971e5f62c6b8a2afc33acc，CID 为 377196179。条目元数据时长 3803000 毫秒，见 [items.jsonl](../../data/items.jsonl)。

## 已补充的质量状态

quality.content_assessment 将该结果标记为 filler_only，依据仅为已存储文本。eligible_as_substantive_transcript=false 表示不能把它计作有实质内容的转录；source_audio_checked=false 表示这次核查没有测量音频，不据此判定静音或识别失败的原因。

text、segments、model、content_sha256、原 metadata、audio_ids 和原复核标记均保留。内容哈希仍为 65c4b62ded7f6b0fa878f8e2a5fd72207fca2c3742a28474ade904968544a4da；assessment 中保存相同哈希以定位本次核查对象。

[覆盖查询](../COVERAGE.md)会分别返回总转录数、text_present_transcripts、filler_only_transcripts 和 empty_transcripts。该 P2 当前只有这份直接转录，无直接整理稿；仅有记录不代表已有实质文稿。

    python tools/corpus.py coverage BV1CP4y1s7BM --part 2

## 备用音频与后续处理

[issue #5](https://github.com/chosenecho/weimingzi-data/issues/5)在 2026-11-04 更新：用户确认已从其他渠道获得对应音频。该确认提供了可继续核对的来源，但 issue 未提供文件路径、下载位置或哈希。

提交 3a1ee20f2531ec117fc5376b7f596374e982389f 的双视频包只包含 BV1cq4y1t7TN 和 BV1oq4y1q7rg 的结果，不包含本 P2 音频。

仓库音频索引中对应记录仍为 unavailable，local_path=null，见 [audio.jsonl](../../data/audio.jsonl)。音频 ID 为：

    m-3f2f3ca7b3260f48f3799764aedf950fdbf3e718952b7d2117766983fe21b4e3

本次未定位到备用文件，尚未完成重新转录和整理。取得文件路径或下载位置后，应先记录来源、SHA-256、解码信息和时长，核对其与本 P2 的内容对应关系。再生成独立转录及整理稿，保留旧结果与新旧关系；不能排序或截断原时间值，也不能把填充词扩写成正文。
