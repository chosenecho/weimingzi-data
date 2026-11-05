# 未明子资料库

维护未明子的视频、录音转录、整理稿、动态和专栏。数据按内容类型统一存放，平台标识、原文链接和模型信息放在记录字段中。

- [浏览全部内容](docs/INDEX.md)
- [校对标注与复核状态](docs/catalog/reviews.md)
- [名词与概念](docs/GLOSSARY.md)
- [数据结构](docs/SCHEMA.md)
- [维护与入库](docs/MAINTENANCE.md)
- [代理使用指南](docs/AGENT-GUIDE.md)
- [音频下载](docs/DOWNLOAD.md)
- [数据质量与使用限制](docs/DATA-CARD.md)
- [资料库验收矩阵](docs/ARCHIVE-ACCEPTANCE.md)
- [保存范围与完整性基线](docs/PRESERVATION.md)
- [保存能力迭代计划](docs/PRESERVATION-ROADMAP.md)
- [许可证与适用范围](LICENSE)
- [内容权利说明](CONTENT-RIGHTS.md)

## 仓库结构

```text
data/
  items.jsonl           内容条目、外部标识、标题和关联
  transcripts/          带时间的基础转录
  edited_transcripts/    整理稿、段落参照和疑点
  posts/                动态富文本及关联专栏
  articles/             专栏正文与富文本
  collections.jsonl     文集、合集、系列及成员顺序
  audio.jsonl           音频哈希、可用状态和下载位置
  confirmations.jsonl   有范围限定的人工确认
selections/
  training.json         训练选稿的条目引用
src/weimingzi_corpus/   本地维护工具
tools/                 命令入口
tests/                 数据契约与工具测试
docs/                  规则、自动生成的目录与计数
```

JSON、JSONL 是维护版本。Markdown 目录由它们生成；TXT、Markdown 正文、字幕、CSV 和 SQLite 按需导出。音频文件通过 Releases 恢复到本地 `media/audio/`，不提交到 Git。

数据规模见自动生成的 [counts.json](docs/counts.json)。同一条目可以关联多份转录和整理稿；目录排序与训练选稿均不表示全文通过人工审核。

目录中的“平台 AI 字幕”“平台 CC 字幕”“本地语音转录”“云端语音转录”是不同的基础转录结果；“整理稿”是整理或校对后的独立结果。链接附有已知模型和短 ID，整理稿后的“输入”指出它关联的基础转录。具体区别与示例见[基础转录与整理稿](docs/GLOSSARY.md#基础转录与整理稿)。

## 使用

使用 Python 3.12 或更高版本，工具仅依赖标准库。

```sh
python tools/corpus.py validate
python tools/corpus.py generate
python tools/check_repository.py
python -m unittest discover -s tests -v
```

导出本地检索库后，可检索中文正文：

```sh
python tools/corpus.py export --format sqlite --output .cache/exports/corpus.sqlite3
python tools/corpus.py search 唯物主义
```

SQLite 是从归档记录生成的本地检索副本，不替代 JSON/JSONL 维护数据。检索结果用于定位正文；校对标注、附注等内容请按[维护说明](docs/MAINTENANCE.md)查询。代理操作本仓库前请先阅读[代理使用指南](docs/AGENT-GUIDE.md)。

入库格式、记录 ID 和其他导出方式见 [维护说明](docs/MAINTENANCE.md)。

## 许可

本项目贡献者有权授权的原创代码和原创项目说明文档采用 MIT 许可。归档语料及其中的第三方内容不作统一再许可，已有的明确许可继续适用。完整范围见 [LICENSE](LICENSE)，内容使用与归属问题见 [内容权利说明](CONTENT-RIGHTS.md)。
