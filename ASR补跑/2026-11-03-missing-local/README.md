# 无本地产物 ASR 补跑

处理范围见 [输入清单.csv](输入清单.csv)，结果见 [处理报告.json](处理报告.json) 和 [分P目录.csv](分P目录.csv)。

完成 5 个视频、6 个分 P 的云识别，音频总时长为 16161.708676 秒。模型为 `qwen-audio-3.1-asr-flash`，71 个有效分块响应；最初欠费失败的两次响应另行保留。所有正文未经人工审核，本批尚未进行 AI 校对。

## 阅读入口

| BV | P | 正文 | 字幕 |
| --- | ---: | --- | --- |
| [BV14Qbk6zEis](../../视频/BV14Qbk6zEis/README.md) | 1 | [TXT](../../视频/BV14Qbk6zEis/P001/原始转录/asr-cloud-qwen-audio-3.1-asr-flash-20261103/transcript.txt) | [SRT](../../视频/BV14Qbk6zEis/P001/原始转录/asr-cloud-qwen-audio-3.1-asr-flash-20261103/transcript.srt) / [VTT](../../视频/BV14Qbk6zEis/P001/原始转录/asr-cloud-qwen-audio-3.1-asr-flash-20261103/transcript.vtt) |
| [BV15mu46tEyf](../../视频/BV15mu46tEyf/README.md) | 1 | [TXT](../../视频/BV15mu46tEyf/P001/原始转录/asr-cloud-qwen-audio-3.1-asr-flash-20261103/transcript.txt) | [SRT](../../视频/BV15mu46tEyf/P001/原始转录/asr-cloud-qwen-audio-3.1-asr-flash-20261103/transcript.srt) / [VTT](../../视频/BV15mu46tEyf/P001/原始转录/asr-cloud-qwen-audio-3.1-asr-flash-20261103/transcript.vtt) |
| [BV1F7t16iEW6](../../视频/BV1F7t16iEW6/README.md) | 1 | [TXT](../../视频/BV1F7t16iEW6/P001/原始转录/asr-cloud-qwen-audio-3.1-asr-flash-20261103/transcript.txt) | 时间戳待复核 |
| [BV1F7t16iEW6](../../视频/BV1F7t16iEW6/README.md) | 2 | [TXT](../../视频/BV1F7t16iEW6/P002/原始转录/asr-cloud-qwen-audio-3.1-asr-flash-20261103/transcript.txt) | [SRT](../../视频/BV1F7t16iEW6/P002/原始转录/asr-cloud-qwen-audio-3.1-asr-flash-20261103/transcript.srt) / [VTT](../../视频/BV1F7t16iEW6/P002/原始转录/asr-cloud-qwen-audio-3.1-asr-flash-20261103/transcript.vtt) |
| [BV1macKzUEmV](../../视频/BV1macKzUEmV/README.md) | 1 | [TXT](../../视频/BV1macKzUEmV/P001/原始转录/asr-cloud-qwen-audio-3.1-asr-flash-20261103/transcript.txt) | [SRT](../../视频/BV1macKzUEmV/P001/原始转录/asr-cloud-qwen-audio-3.1-asr-flash-20261103/transcript.srt) / [VTT](../../视频/BV1macKzUEmV/P001/原始转录/asr-cloud-qwen-audio-3.1-asr-flash-20261103/transcript.vtt) |
| [BV1wj411m7GK](../../视频/BV1wj411m7GK/README.md) | 1 | [TXT](../../视频/BV1wj411m7GK/P001/原始转录/asr-cloud-qwen-audio-3.1-asr-flash-20261103/transcript.txt) | [SRT](../../视频/BV1wj411m7GK/P001/原始转录/asr-cloud-qwen-audio-3.1-asr-flash-20261103/transcript.srt) / [VTT](../../视频/BV1wj411m7GK/P001/原始转录/asr-cloud-qwen-audio-3.1-asr-flash-20261103/transcript.vtt) |

直播 P1 在 4080—4320 秒、4560—4800 秒的原始时间戳异常，文字保留在正文，原响应保留在对应 chunk 文件；该 P 不提供 SRT/VTT。缺口与复核信息见 [分P目录.json](分P目录.json)。

## 未取得音频

[不可获取.csv](不可获取.csv) 保留 3 个 BV：`BV1i9bezLEHK`、`BV1mk8W6dEyx`、`BV1nioMY6Et8`。详情接口返回 62012 / 62002，分 P 接口返回 -404；核验记录见 [播放接口核验.json](播放接口核验.json)。用户确认在 B 站找不到，待补可访问来源。

## 音频和检索库

新增音频在 [本批 Release](https://github.com/chosenecho/weimingzi-data/releases/tag/missing-local-asr-2026-11-03)。在仓库根目录运行以下命令，校验分卷及每个音频的 SHA-256 后恢复目录：

```powershell
python fetch_media.py --manifest ASR补跑/2026-11-03-missing-local/media-manifest.json
```

[媒体清单](media-manifest.json) · [SQLite 云转录库](云转录库.sqlite3) · [增量文件校验清单](publication-manifest.json)。SQLite 中的 `transcripts` 与 `transcript_search` 分别提供正文和全文检索；各条目明确保存 `asr-cloud` 来源、模型及未人工审核状态。

原 metadata.json 为初始归档分组快照；本次实际上传者、CID 和音轨哈希保存在每个来源记录中。既有训练入口和人工确认版本保持原记录。
