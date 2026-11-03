# weimingzi-data

未明子相关视频文稿、字幕、音频与用户内容的可追溯归档，收录 B 站、YouTube 和用户补充材料。

[![Repository checks](https://github.com/chosenecho/weimingzi-data/actions/workflows/repository-checks.yml/badge.svg)](https://github.com/chosenecho/weimingzi-data/actions/workflows/repository-checks.yml)

**[视频目录](docs/VIDEO-INDEX.md)** · **[动态与专栏](data/user-content/README.md)** · **[音频下载](docs/DOWNLOAD.md)** · **[数据说明](docs/DATA-CARD.md)** · **[训练入口](docs/TRAINING.md)**

## 从哪里开始

| 需求 | 入口 |
| --- | --- |
| 按标题、BV 或分 P 查找文稿 | [分页视频目录](docs/VIDEO-INDEX.md) · [可筛选 CSV](metadata/catalog.csv) |
| 阅读动态、专栏、文集与合集 | [用户内容目录](data/user-content/README.md) |
| 查找用户补充音频及其文稿 | [补充音频目录](data/supplemental-audio/README.md) |
| 下载、恢复与校验音频 | [下载指南](docs/DOWNLOAD.md) |
| 获取选定的训练文稿 | [训练源说明](docs/TRAINING.md) · [机器索引](metadata/training-source.json) |
| 核对来源、质量状态和历史变更 | [数据说明](docs/DATA-CARD.md) · [批次与校验](docs/PROVENANCE.md) |

## 当前收录

<!-- archive-stats:start -->
| 内容 | 数量 | 核验入口 |
| --- | ---: | --- |
| 视频目录 | 1,701 个 BV | [视频索引](docs/VIDEO-INDEX.md) |
| B 站分 P | 1,979 | [catalog.csv](metadata/catalog.csv) |
| YouTube 音轨 | 18 | [catalog.csv](metadata/catalog.csv) |
| 训练选稿 | 1,966 份 | [训练索引](metadata/training-source.json) |
| 动态／专栏正文 | 2,756 条／71 篇 | [用户内容](data/user-content/README.md) |
| 文集／合集／系列 | 6／3／11 | [用户内容](data/user-content/README.md) |
| 已发布音频 | 680 份，13 个分卷 | [媒体清单](metadata/media/) |
| 用户补充音频 | 3 份 | [补充音频](data/supplemental-audio/README.md) |
<!-- archive-stats:end -->

统计由 [仓库检查工具](tools/check_repository.py) 从当前目录、索引与媒体清单生成；机器版本见 [dataset-summary.json](metadata/dataset-summary.json)。分 P、YouTube 音轨和补充音频使用不同统计单位，不合并为“视频总数”。内容采集时间以各批次记录为准。

## 下载

只阅读文字可以直接浏览目录，或克隆仓库：

```bash
git clone https://github.com/chosenecho/weimingzi-data.git
cd weimingzi-data
```

音频保存在 GitHub Releases。使用 Python 3.12 或更高版本，在仓库根目录运行：

```bash
python -X utf8 tools/fetch_media.py --list
python -X utf8 tools/fetch_media.py
```

默认恢复全部已发布音频到 `data/`，并校验 ZIP 与音频的 SHA-256；已通过校验的文件会复用。按批下载、缓存位置和离线校验见[下载指南](docs/DOWNLOAD.md)。

## 阅读与使用边界

- AI 阅读稿保留校对记录和原始识别版本；AI 校对及局部字句确认不表示全文已人工审核。
- 原识别缺口、无正文音轨和时间戳异常继续保留；状态含义及已知问题见[数据说明](docs/DATA-CARD.md)。
- 归档包含与未明子有关的转载、联合投稿和补充材料，实际上传者以各来源记录为准。
- 本仓库为非官方归档。内容权利归相应权利人，具体使用条件见[内容权利说明](CONTENT-RIGHTS.md)。

## 仓库维护

[目录结构](docs/STRUCTURE.md) · [更新记录](CHANGELOG.md) · [纠错与贡献](CONTRIBUTING.md) · [文档导航](docs/README.md)

本次整理更新于 **2026-11-04**。数据目录、机器索引和下载工具已按新结构迁移，历史路径对照保存在 [path-map.json](metadata/path-map.json)。
