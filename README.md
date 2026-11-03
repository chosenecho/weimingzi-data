# weimingzi-data

未明子相关的 B 站、部分 YouTube 和用户补充音频转录归档，同时保存动态、专栏与处理记录。

[![Repository checks](https://github.com/chosenecho/weimingzi-data/actions/workflows/repository-checks.yml/badge.svg)](https://github.com/chosenecho/weimingzi-data/actions/workflows/repository-checks.yml)

**[跨平台转录目录](docs/SOURCE-INDEX.md)** · **[B 站视频目录](docs/VIDEO-INDEX.md)** · **[动态与专栏](data/user-content/README.md)** · **[音频下载](docs/DOWNLOAD.md)**

## 阅读与取用

| 需求 | 入口 |
| --- | --- |
| 查找 B 站、YouTube 或补充音频的正文 | [跨平台目录](docs/SOURCE-INDEX.md) · [统一 CSV](metadata/source-index.csv) |
| 按 BV 或分 P 浏览 | [分页视频目录](docs/VIDEO-INDEX.md) |
| 核对来源与处理状态 | [数据说明](docs/DATA-CARD.md) · [补充来源标记](docs/SOURCE-LABELS.md) |
| 恢复并校验原始音频 | [下载指南](docs/DOWNLOAD.md) |
| 使用已有训练选稿 | [选稿说明](docs/TRAINING.md) · [训练索引](metadata/training-source.json) |
| 接收新交付包、编辑语料、导出训练或知识库数据 | [离线语料工具](docs/CORPUS.md) · [AI 使用指南](docs/AI-GUIDE.md) |

AI 阅读稿保留原始转录与处理版本。AI 校对、局部字句确认和训练选稿均不等于全文通过人工审核；无正文、识别缺口和时间戳异常按原状态保留。引用发言应对照来源与可用音频。

## 仓库结构

~~~text
data/          按 bilibili、youtube、audio、user-content 保存材料
metadata/      当前索引、复核状态与媒体恢复清单
provenance/    来源快照、处理批次、纠错与迁移证据
docs/          阅读目录、数据说明与维护文档
src/           离线语料工具 weimingzi_corpus
profiles/      训练与知识库导出规则
tools/         下载、索引生成与仓库检查
tests/         工具与语料契约验证
projects/      持续采集等专项设计
~~~

来源决定存放位置；章节、标题和跨平台关联由索引描述。YouTube 以自身 ID 独立保存，BV 关联只作参考。完整约定见[目录结构](docs/STRUCTURE.md)。

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
| 用户补充音频 | 3 份 | [补充音频](data/audio/README.md) |
<!-- archive-stats:end -->

统计由[仓库检查工具](tools/check_repository.py)核对目录与清单后生成，机器版本见 [dataset-summary.json](metadata/dataset-summary.json)。各来源使用不同统计单位；内容采集时间以各批次记录为准。

## 下载与检查

文字材料直接存放在 Git，音频通过 GitHub Releases 分发。需要 Python 3.12 或更高版本：

~~~sh
git clone https://github.com/chosenecho/weimingzi-data.git
cd weimingzi-data
python -X utf8 tools/fetch_media.py --list
python -X utf8 tools/fetch_media.py
python -X utf8 tools/check_repository.py --verify-hashes
~~~

下载工具按当前媒体清单恢复到 `data/`，校验 ZIP 与音频 SHA-256，复用已校验文件。维护流程见[贡献说明](CONTRIBUTING.md)。

UID `23191782` 的持续采集方案见[增量监听项目](projects/uploader-23191782/README.md)，目前处于设计阶段。

本仓库为非官方归档，包含转载、联合投稿和补充材料；实际来源以各条记录为准。内容权利见[说明](CONTENT-RIGHTS.md)。

[文档导航](docs/README.md) · [更新记录](CHANGELOG.md) · [批次与校验](docs/PROVENANCE.md) · [平台迁移记录](provenance/layout-migration/2026-11-04-platforms/README.md)
