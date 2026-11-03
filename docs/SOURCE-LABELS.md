<!-- generated: tools/check_source_labels.py -->
# 补充材料与来源标记

机器清单见 [source-labels.json](../metadata/source-labels.json)，按 `folder` 与 [catalog.csv](../metadata/catalog.csv) 或 [audio.csv](../metadata/audio.csv) 关联。每条都有音频 SHA-256、来源记录和批次依据。

`audio_only` 表示收到的材料只有音频，不表示现在没有文稿；`audio_track` 表示从平台视频取得的音轨。来源类别与正文、字幕、AI 校对、人工复核状态分别记录，标签不表示训练批准。

## 用户补充的仅音频材料

用户提供 MP3 后入库，当前均有 ASR 转录与 AI 校对稿，未经人工审核。接收时间见各条 `source.json`；入库依据见[回执](../data/audio/入库回执.json)。`asr-cloud` 是识别方式，材料来源为 `user_supplied`。

| 材料 | 标记 | BV 关系 | 当前产物 |
| --- | --- | --- | --- |
| [1-2-1-2神义论](../data/audio/1-2-1-2神义论/README.md) | `user_audio_supplement` · `audio_only` | 无已确认 BV 对应 | ASR + AI 草稿 |
| [1-2-1神创论](../data/audio/1-2-1神创论/README.md) | `user_audio_supplement` · `audio_only` | BV1hf4y1k7sX：同章节补充 | ASR + AI 草稿 |
| [1-2-1-1自然神论](../data/audio/1-2-1-1自然神论/README.md) | `user_audio_supplement` · `audio_only` | 无已确认 BV 对应 | ASR + AI 草稿 |

神创论的 BV 关联依据是用户文件名章节与旧条目标题，不证明音轨相同；自然神论与神义论不补造 BV。依据见各条[来源记录](../data/audio/README.md)。

## YouTube 补充音轨

以下材料从 YouTube 音轨识别，按原始清单的 BV 参考关系归档；不表示从 B 站下载，也不表示与某个分 P 或音轨逐一相同。批次见 [youtube-index.csv](../metadata/sources/youtube-index.csv) 和[识别审计](../metadata/sources/youtube-audit.json)。

| 材料 | YouTube ID | 参考 BV | 当前产物 |
| --- | --- | --- | --- |
| [【行动建议】我对于阳和平老师的21万粉丝中的同情、认可、践行MLM主义的支持者的一个呼吁](../data/youtube/0iLy_lI8H4Y/README.md) | [0iLy_lI8H4Y](https://www.youtube.com/watch?v=0iLy_lI8H4Y) | BV1jG4y137dx | ASR + AI 草稿 |
| [做现实的理想主义者｜正禾晨生支教项目实录·重庆站](../data/youtube/3BWV_a28S3c/README.md) | [3BWV_a28S3c](https://www.youtube.com/watch?v=3BWV_a28S3c) | BV1RDSTBNEMo | ASR + AI 草稿；需复核 |
| [【主义主义】无声版：神创论（1 2 1）](../data/youtube/EMkOxG97L-w/README.md) | [EMkOxG97L-w](https://www.youtube.com/watch?v=EMkOxG97L-w) | BV1hf4y1k7sX | 无识别正文；无 AI 稿；需复核 |
| [【人神共愤】阳大教主，停止你们团伙对小草的荡妇羞辱！](../data/youtube/EWNGZEvi0YQ/README.md) | [EWNGZEvi0YQ](https://www.youtube.com/watch?v=EWNGZEvi0YQ) | BV1Z5Pze6EfK | ASR + AI 草稿 |
| [【植青俱乐部】项目记录 1 2023 10](../data/youtube/FxPwfHeF8dY/README.md) | [FxPwfHeF8dY](https://www.youtube.com/watch?v=FxPwfHeF8dY) | BV1ZC4y1j7HK | ASR + AI 草稿 |
| [【一百分钟哲学】所谓的中国思想、中国哲学、中国传统智慧](../data/youtube/GPL8YTWB_hI/README.md) | [GPL8YTWB_hI](https://www.youtube.com/watch?v=GPL8YTWB_hI) | BV1Wt4y1z7C8 | ASR + AI 草稿 |
| [【极限求生】读懂激流网几人的濒死操作：这根本不是性骚扰、名誉权的事儿，这是生死存亡的事儿](../data/youtube/LDlmGVgO9bY/README.md) | [LDlmGVgO9bY](https://www.youtube.com/watch?v=LDlmGVgO9bY) | BV1QSPSe4EcL | ASR + AI 草稿 |
| [【主义主义】农业的去本地化（4 3 4 1）——“适千里者，三月聚粮”，计划性生产集群的实现](../data/youtube/LhbZtt3hmSE/README.md) | [LhbZtt3hmSE](https://www.youtube.com/watch?v=LhbZtt3hmSE) | BV1oq4y1q7rg | ASR + AI 草稿 |
| [【实事求是】把一些龌龊扫到角落里倒掉](../data/youtube/V195SPrt5Bc/README.md) | [V195SPrt5Bc](https://www.youtube.com/watch?v=V195SPrt5Bc) | BV1Gs4y1A7Ss | ASR + AI 草稿 |
| [蜂蜜的前世今生｜正禾助农项目实录·重庆站](../data/youtube/XRyRYKhNB3w/README.md) | [XRyRYKhNB3w](https://www.youtube.com/watch?v=XRyRYKhNB3w) | BV1A3S7BCEX5 | ASR + AI 草稿 |
| [腊肉飘香，铺就增收路｜正禾助农项目实录](../data/youtube/a0jurXgtgZw/README.md) | [a0jurXgtgZw](https://www.youtube.com/watch?v=a0jurXgtgZw) | BV1yxmsBbEi6 | ASR + AI 草稿 |
| [【实事求是】我就想问阳和平一个问题](../data/youtube/qhBRyfIkH3E/README.md) | [qhBRyfIkH3E](https://www.youtube.com/watch?v=qhBRyfIkH3E) | BV1zR4y1C7iB | ASR + AI 草稿 |
| [【一脉相承】阳和平对小草的政治灌输：“就是菲律宾的那个游击队员的事，我好长时间接受不了，因为周道远，就是我的前女友，她非常愤怒”](../data/youtube/v44IMpnZ1ws/README.md) | [v44IMpnZ1ws](https://www.youtube.com/watch?v=v44IMpnZ1ws) | BV1eNNWexEFx | ASR + AI 草稿；需复核 |
| [【现象学】胡塞尔《现象学的观念》演讲一：哲学与自然思维\|实证科学的差别](../data/youtube/vWS5ZZ9kmSo/README.md) | [vWS5ZZ9kmSo](https://www.youtube.com/watch?v=vWS5ZZ9kmSo) | BV1gh411Y7Xm | ASR + AI 草稿 |
| [【现实观察】激流系地下活动的两种方式](../data/youtube/xmPlkYpsyGU/README.md) | [xmPlkYpsyGU](https://www.youtube.com/watch?v=xmPlkYpsyGU) | BV132KjeMEAV | ASR + AI 草稿 |
| [植青俱乐部青年解放指南｜抵近观察支教一线](../data/youtube/xoVCjtKkCcg/README.md) | [xoVCjtKkCcg](https://www.youtube.com/watch?v=xoVCjtKkCcg) | BV1KBCMBrEaL | ASR + AI 草稿 |
| [【植青小屋】小屋工作年度总结+盖世工坊新品介绍](../data/youtube/xts9IFlc57U/README.md) | [xts9IFlc57U](https://www.youtube.com/watch?v=xts9IFlc57U) | BV19bkzYyEEk | ASR + AI 草稿；需复核 |
| [橙满枝头路难行   正禾助农项目实录 · 江西站](../data/youtube/zT72evsuwjw/README.md) | [zT72evsuwjw](https://www.youtube.com/watch?v=zT72evsuwjw) | BV1DJB5BJEAY | ASR + AI 草稿 |

本表全部标记为 `youtube_supplement` · `audio_track`。有正文的条目有 AI 草稿，均未经人工审核；AI 校对批次见[处理记录](../provenance/ai-proofreading/2026-11-03-opencode-go/README.md)。时间戳异常和未返回词语的区间保留在审计与原始响应中。

`EMkOxG97L-w` 无识别正文、未做 AI 校对；历史静音检测结果见 [audio-validation.json](../data/youtube/EMkOxG97L-w/audio-validation.json)。用户补充的有声神创论音频另列，未覆盖该音轨。

## 后补的 B 站 ASR

首次汇总时没有本地产物，后续从 B 站取得音频并补跑云识别。批次、下载来源与复核区间见[补跑记录](../provenance/asr/2026-11-03-missing-local/README.md)；标记仅作用于下列分 P。

| 材料 | BV / 分 P | 当前产物 |
| --- | --- | --- |
| [【在野志】第17期：集体时期的水渠与现代高标准农田，为什么都失败了？](../data/bilibili/BV14Qbk6zEis/P001/README.md) | BV14Qbk6zEis P1 | ASR；无 AI 稿 |
| [微信视频2026-08-07](../data/bilibili/BV15mu46tEyf/P001/README.md) | BV15mu46tEyf P1 | ASR；无 AI 稿 |
| [0-随便聊聊](../data/bilibili/BV1F7t16iEW6/P001/README.md) | BV1F7t16iEW6 P1 | ASR；无 AI 稿；需复核 |
| [1-随便聊聊](../data/bilibili/BV1F7t16iEW6/P002/README.md) | BV1F7t16iEW6 P2 | ASR；无 AI 稿 |
| [植青2025年度总结-修改4](../data/bilibili/BV1macKzUEmV/P001/README.md) | BV1macKzUEmV P1 | ASR；无 AI 稿 |
| [【勇者招募】GEIST与红庄爱心小屋双线翻修！植青俱乐部预热招募，来就送会员体验卡。](../data/bilibili/BV1wj411m7GK/P001/README.md) | BV1wj411m7GK P1 | ASR；无 AI 稿 |

本表全部标记为 `bilibili_asr_backfill` · `audio_track`，未经人工审核。`BV1F7t16iEW6` P1 保留时间戳异常，本条没有 SRT/VTT；不要通过排序或截断时间戳补造字幕。

## 给 AI 与数据处理脚本

- 读取 `source-labels.json` 的 `schema` 和 `records`，以 `record_id` 为稳定身份、`folder` 为关联键；不要只看父目录里的 BV 猜来源。清单只覆盖这里列出的补充批次，未列出条目不能据此推定来源或人工审核状态。
- 保留 `category`、`source_platform`、`input_media`、`batch_id`、`source_record` 和 `audio_sha256`；正文质量另看 `quality` 和原记录。导出训练集或知识库时随 lineage 保留来源。
- `source_received_at` 取自音频接收记录，`source_downloaded_at` 取自下载记录；批次名中的日期不是视频发表日，也不一定是 Git 提交日。YouTube 批次已有于首次汇总，后续另加 AI 校对；不要把 AI 校对完成时间当作抓取时间。
- 来源标记位于 README 的 `source-labels` 区块；源响应、历史清单、AI 文稿与训练选稿均未因加标签而改写。

维护标记：在仓库根目录运行 `python -X utf8 tools/check_source_labels.py --update`，再运行不带 `--update` 的同一命令检查。新增批次应补充明确的来源依据；检查不会调用模型、下载音频或改生产状态。

返回[仓库首页](../README.md) · [批次与校验](PROVENANCE.md)。
