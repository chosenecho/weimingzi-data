# 新增音频与 YouTube AI 校对

已完成 3 份补充音频及 17 份有正文的 YouTube 转录，共 20 份独立 AI 阅读稿。使用 OpenCode Go `deepseek-v4.1-flash`，10 个 worker。

[校对目录](校对目录.csv) · [完整报告](校对报告.json) · [SQLite 校对库](校对库.sqlite3)

AI 校对稿未经人工审核，不是新的 ASR 或逐字字幕。原始音频、正文、原始响应和已有异常标记保留；疑点见各稿 review.md。

YouTube `EMkOxG97L-w` 无识别正文，未发送付费校对请求。`3BWV_a28S3c`、`v44IMpnZ1ws`、`xts9IFlc57U` 的原识别缺口或时间戳问题仍需复核；本次覆盖其中已有的全部文字，包括时间戳异常分块的正文。

| 来源 | 标题 | 状态 | 入口 |
| --- | --- | --- | --- |
| supplemental_audio | 1-2-1-1自然神论 | succeeded | [阅读稿](../../补充音频/1-2-1-1自然神论/AI校对/opencode-go-deepseek-v4.1-flash/ai-draft.md) |
| supplemental_audio | 1-2-1-2神义论 | succeeded | [阅读稿](../../补充音频/1-2-1-2神义论/AI校对/opencode-go-deepseek-v4.1-flash/ai-draft.md) |
| supplemental_audio | 1-2-1神创论 | succeeded | [阅读稿](../../补充音频/1-2-1神创论/AI校对/opencode-go-deepseek-v4.1-flash/ai-draft.md) |
| youtube | 【现实观察】激流系地下活动的两种方式 | succeeded | [阅读稿](../../视频/BV132KjeMEAV/YouTube/xmPlkYpsyGU/AI校对/opencode-go-deepseek-v4.1-flash/ai-draft.md) |
| youtube | 【植青小屋】小屋工作年度总结+盖世工坊新品介绍 | succeeded | [阅读稿](../../视频/BV19bkzYyEEk/YouTube/xts9IFlc57U/AI校对/opencode-go-deepseek-v4.1-flash/ai-draft.md) |
| youtube | 蜂蜜的前世今生｜正禾助农项目实录·重庆站 | succeeded | [阅读稿](../../视频/BV1A3S7BCEX5/YouTube/XRyRYKhNB3w/AI校对/opencode-go-deepseek-v4.1-flash/ai-draft.md) |
| youtube | 橙满枝头路难行   正禾助农项目实录 · 江西站 | succeeded | [阅读稿](../../视频/BV1DJB5BJEAY/YouTube/zT72evsuwjw/AI校对/opencode-go-deepseek-v4.1-flash/ai-draft.md) |
| youtube | 【一脉相承】阳和平对小草的政治灌输：“就是菲律宾的那个游击队员的事，我好长时间接受不了，因为周道远，就是我的前女友，她非常愤怒” | succeeded | [阅读稿](../../视频/BV1eNNWexEFx/YouTube/v44IMpnZ1ws/AI校对/opencode-go-deepseek-v4.1-flash/ai-draft.md) |
| youtube | 【现象学】胡塞尔《现象学的观念》演讲一：哲学与自然思维/实证科学的差别 | succeeded | [阅读稿](../../视频/BV1gh411Y7Xm/YouTube/vWS5ZZ9kmSo/AI校对/opencode-go-deepseek-v4.1-flash/ai-draft.md) |
| youtube | 【实事求是】把一些龌龊扫到角落里倒掉 | succeeded | [阅读稿](../../视频/BV1Gs4y1A7Ss/YouTube/V195SPrt5Bc/AI校对/opencode-go-deepseek-v4.1-flash/ai-draft.md) |
| youtube | 【主义主义】无声版：神创论（1 2 1） | skipped_empty | 无 ASR 正文，跳过 |
| youtube | 【行动建议】我对于阳和平老师的21万粉丝中的同情、认可、践行MLM主义的支持者的一个呼吁 | succeeded | [阅读稿](../../视频/BV1jG4y137dx/YouTube/0iLy_lI8H4Y/AI校对/opencode-go-deepseek-v4.1-flash/ai-draft.md) |
| youtube | 植青俱乐部青年解放指南｜抵近观察支教一线 | succeeded | [阅读稿](../../视频/BV1KBCMBrEaL/YouTube/xoVCjtKkCcg/AI校对/opencode-go-deepseek-v4.1-flash/ai-draft.md) |
| youtube | 【主义主义】农业的去本地化（4 3 4 1）——“适千里者，三月聚粮”，计划性生产集群的实现 | succeeded | [阅读稿](../../视频/BV1oq4y1q7rg/YouTube/LhbZtt3hmSE/AI校对/opencode-go-deepseek-v4.1-flash/ai-draft.md) |
| youtube | 【极限求生】读懂激流网几人的濒死操作：这根本不是性骚扰、名誉权的事儿，这是生死存亡的事儿 | succeeded | [阅读稿](../../视频/BV1QSPSe4EcL/YouTube/LDlmGVgO9bY/AI校对/opencode-go-deepseek-v4.1-flash/ai-draft.md) |
| youtube | 做现实的理想主义者｜正禾晨生支教项目实录·重庆站 | succeeded | [阅读稿](../../视频/BV1RDSTBNEMo/YouTube/3BWV_a28S3c/AI校对/opencode-go-deepseek-v4.1-flash/ai-draft.md) |
| youtube | 【一百分钟哲学】所谓的中国思想、中国哲学、中国传统智慧 | succeeded | [阅读稿](../../视频/BV1Wt4y1z7C8/YouTube/GPL8YTWB_hI/AI校对/opencode-go-deepseek-v4.1-flash-recovery-v2/ai-draft.md) |
| youtube | 腊肉飘香，铺就增收路｜正禾助农项目实录 | succeeded | [阅读稿](../../视频/BV1yxmsBbEi6/YouTube/a0jurXgtgZw/AI校对/opencode-go-deepseek-v4.1-flash/ai-draft.md) |
| youtube | 【人神共愤】阳大教主，停止你们团伙对小草的荡妇羞辱！ | succeeded | [阅读稿](../../视频/BV1Z5Pze6EfK/YouTube/EWNGZEvi0YQ/AI校对/opencode-go-deepseek-v4.1-flash/ai-draft.md) |
| youtube | 【植青俱乐部】项目记录 1 2023 10 | succeeded | [阅读稿](../../视频/BV1ZC4y1j7HK/YouTube/FxPwfHeF8dY/AI校对/opencode-go-deepseek-v4.1-flash/ai-draft.md) |
| youtube | 【实事求是】我就想问阳和平一个问题 | succeeded | [阅读稿](../../视频/BV1zR4y1C7iB/YouTube/qhBRyfIkH3E/AI校对/opencode-go-deepseek-v4.1-flash/ai-draft.md) |
