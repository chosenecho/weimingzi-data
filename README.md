# weimingzi-data

未明子相关的转录、字幕、校对稿、动态与文章数据。收录 B 站、部分 YouTube 和用户提供的音频材料，按内容分类。

**[分类目录](docs/INDEX.md)** · **[主目录 CSV](metadata/catalog.csv)** · **[动态与文章](data/user-content/README.md)** · **[音频下载](docs/DOWNLOAD.md)**

## 查找材料

| 需求 | 入口 |
| --- | --- |
| 按主题查找正文和补充版本 | [分类目录](docs/INDEX.md) |
| 搜索标题、标识、文件路径和质量字段 | [catalog.csv](metadata/catalog.csv) |
| 读取 JSON、CSV、SQLite 等资料 | [数据集目录](data/datasets/README.md) |
| 了解字段和质量限制 | [数据说明](docs/DATA-CARD.md) |
| 使用选定训练文稿 | [选稿说明](docs/TRAINING.md) |
| 接收、编辑和导出语料 | [离线语料工具](docs/CORPUS.md) · [AI 使用指南](docs/AI-GUIDE.md) |

## 目录

~~~text
data/
  transcripts/<主题>/<内容条目>/   转录、字幕、校对稿及补充版本
  datasets/<材料类别>/            清单、数据库、校对及文本修订数据
  user-content/                  动态、文章、文集与合集
metadata/                        主目录、选稿、质量事项和媒体恢复索引
docs/                            分类导航与使用说明
src/、profiles/                  离线语料工具与导出规则
tools/、tests/                   下载、目录生成与检查
projects/                        专项工具与说明
~~~

同一主题的材料放在一起，同一内容的补充版本放在条目内。所有条目和数据集登记到一份 [catalog.csv](metadata/catalog.csv)。分类以该表为准，完整约定见[目录结构](docs/STRUCTURE.md)。

## 当前收录

<!-- archive-stats:start -->
| 内容 | 数量 | 入口 |
| --- | ---: | --- |
| 转录材料 | 2,000 份 | [分类目录](docs/INDEX.md) |
| 内容条目 | 1,703 个，8 类 | [主目录](metadata/catalog.csv) |
| 数据集 | 6 组 | [分类目录](docs/INDEX.md) |
| 训练选稿 | 1,966 份 | [选稿索引](metadata/training-source.json) |
| 动态／文章正文 | 2,756 条／71 篇 | [用户内容](data/user-content/README.md) |
| 文集／合集／系列 | 6／3／11 | [用户内容](data/user-content/README.md) |
| 可恢复音频 | 680 份，13 个分卷 | [下载指南](docs/DOWNLOAD.md) |
<!-- archive-stats:end -->

统计由[检查工具](tools/check_repository.py)核对文件和目录后生成，机器版本见 [dataset-summary.json](metadata/dataset-summary.json)。材料数、内容条目数、动态数和文章数分别计数。

## 下载与维护

文字、字幕、清单和数据库保存在 Git，音频通过 GitHub Releases 分发。需要 Python 3.12 或更高版本：

~~~sh
git clone https://github.com/chosenecho/weimingzi-data.git
cd weimingzi-data
python -X utf8 tools/fetch_media.py --list
python -X utf8 tools/fetch_media.py
python -X utf8 tools/check_repository.py --verify-hashes
~~~

新增材料时归类并登记主目录，再生成导航、运行检查。操作见[贡献说明](CONTRIBUTING.md)。持续采集相关工具与说明见 [UID 23191782 项目](projects/uploader-23191782/README.md)。

AI 阅读稿和局部字句确认不代表全文已经人工审核。引用发言时请核对原文与可用音频。第三方内容的使用条件见[内容权利说明](CONTENT-RIGHTS.md)。

[文档导航](docs/README.md)
