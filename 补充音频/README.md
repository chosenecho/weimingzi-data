# 未明子补充音频库

三条用户提供的 MP3 已转录并写入本目录 SQLite 库；音频、正文、字幕和原始响应按原文件名归档。

模型：`qwen-audio-3.1-asr-flash`；文本未经人工校对。

[可筛选目录](../补充音频目录.csv) · [SQLite 数据库](本地音频库.sqlite3)

| 音频 | 时长 | 句段 | 正文字符 |
| --- | ---: | ---: | ---: |
| [1-2-1神创论](1-2-1神创论/README.md) | 920.241 秒 | 152 | 4300 |
| [1-2-1-1自然神论](1-2-1-1自然神论/README.md) | 1927.765 秒 | 347 | 9341 |
| [1-2-1-2神义论](1-2-1-2神义论/README.md) | 1993.234 秒 | 384 | 7476 |

库表：`recordings`、`transcripts`、`transcript_segments`、`provider_requests`、`assets`、`external_associations`、`ingestion_batches`、`transcript_search`。

原生产库不支持本地补充音频或 asr-cloud 来源，本批据实存入独立 SQLite 补充库，避免伪装成本地 GPU ASR 或虚构 BV；已纳入统一合集索引及文件校验。

## AI 校对稿

上述三条补充音频已生成 `deepseek-v4.1-flash` 阅读稿，原 ASR 入库记录保留。见 [统一校对目录及可检索校对库](../AI校对补跑/2026-11-03-opencode-go/README.md)；各音频 README 也有阅读稿和原文对照入口。未经人工审核。
