# BV1Jj411K79j P1 口误与改口确认

处理依据为 [issue #6 的评论](https://github.com/chosenecho/weimingzi-data/issues/6#issuecomment-6649160627)。用户说明已查看原视频，并定位为 33:52。评论发布于 2026-11-05，原文如下：

> 这里我看了一下原视频，这句话准确出处为33:52s处，结合上文的理解，这里应该是口误纠错"公益活动"为口误，说完后纠成了"公益小组"。所以想表达的意思是"公益小组不是目的，公益活动才是目的。"结合作者辩证唯物主义的立场，实践经常被强调。所以该段的实际含义是“"公益小组不是目的，公益活动才是目的。”

## 修订位置

[原整理稿](../../data/edited_transcripts/r-a2637d3db4784162ccfd1245.json)的 paragraphs[48] 包含：

> 那就讲到这里。我希望大家想清楚这件事情，一定要想清楚：公益活动、公益小组不是目的，公益活动才是目的。当然，这些小组的副产品就是小组本身：大家互相合作搭配越来越熟练，越来越有一种齐心做事情的愿望。

[新增修订稿](../../data/edited_transcripts/r-97fac763234451df943669a2.json)将该段整理为：

> 那就讲到这里。我希望大家想清楚这件事情，一定要想清楚：公益小组不是目的，公益活动才是目的。当然，这些小组的副产品就是小组本身：大家互相合作搭配越来越熟练，越来越有一种齐心做事情的愿望。

正文仅省去改口前的“公益活动、”。段落的 input_text、input_unit_labels、index、start=2025590、end=2048710 和其余段落保持原值，见上述两份记录。用户给出的 33:52 为视频回查位置，不替换原段落时间范围，也不作为新增逐字对齐结果。

## 确认与原始证据

[人工确认表](../../data/confirmations.jsonl)中的 a-813baf77c7e28b3973cd42e7 保存评论全文、链接和发布日期。记录还包含用户报告已查看原视频的事实，以及原段和修订段的 SHA-256。scope=local_text_or_term，status=user_confirmed；assistant_listened_to_audio=false 表示本次处理依据用户提供的核对结果。

该确认记录中的原段哈希为 be513b20ddac444ae163c94ef64a4b7f02d5a030d8ea3e579df458bcd04ed070。修订段哈希为 4f83f4a3ff00ed987731fa320425424702ae3a6d3db97ffc1e37981c17d7b76e。原段哈希与 issue #6 提供的下游冻结段哈希相同；下游可据此定位原段并选择新 revision。

修订稿通过 derived_from_id 指向原稿，并以 confirmation_ids 引用该确认。段落 issues 和整稿 notes_markdown 均保留本次修改说明及评论链接。原稿与以下基础转录保留原文件内容：

- [本地 ASR](../../data/transcripts/t-3e7e6612744243e2194ce4ea.json)：segments[249] 保留改口前后的识别文本。
- [平台字幕](../../data/transcripts/t-21876553f63d294a5a66ae8a.json)保留原分段。segments[775:778] 依次为“公益活动”“公益小组不是目的”“公益活动才是目的”。

## 下游选稿与复核范围

[训练选稿](../../selections/training.json)中该条目的 edited_transcript_id 改指修订稿，并引用本次局部确认。其他选稿条目保持原值，未增加选稿范围。

修订稿的 is_complete、requires_review=true、is_fully_human_reviewed=false 和 status=needs_review 均沿用原稿。用户对这一处改口的确认不扩展为全文人工复核。
