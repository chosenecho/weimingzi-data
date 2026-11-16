# 未明子资料库

维护未明子的视频、录音转录、整理稿、动态和专栏。归档数据采用 schema v3，统一为条目、文档、资产和标注四类实体；平台标识、原文链接和模型信息保留在记录中。

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
- [保存运行与交接](docs/PRESERVATION-OPERATIONS.md)
- [保存能力验收发布](https://github.com/chosenecho/weimingzi-data/releases/tag/preservation-2026-11-05)
- [许可证与适用范围](LICENSE)
- [内容权利说明](CONTENT-RIGHTS.md)

## 与训练工程协作

本仓库负责资料归档和来源校订。数据制作与模型训练在 [weimingzi-thought-model][training-project] 进行；正式 train/dev、来源证据和版本清单发布到独立私有仓库 `chosenecho/weimingzi-datasets`。

| 需要处理的内容 | 修改位置 |
| --- | --- |
| 原始正文、转录、整理稿和来源校订 | 本仓库的维护数据 |
| 筛选、问答审核、模型导出、训练与评测 | 制作和训练工程 |
| 已审核训练数据的新版本 | 私有正式数据仓库，由制作工程生成 |

下游按完整 Git 提交读取本仓库，不跟随本地未提交改动。训练选稿、发布 head 和段落收录策略由制作工程的 `configs/corpus/` 维护，命令见[消费配置交接](docs/RELEASE.md)。选中正文不表示全文人工批准，也不代替下游 SFT 内容与证据审核。来源修订完成后，下游重新制作、审核并发布新版本，已有冻结数据保持原字节。

跨仓库命令与审计流程见[多仓库工作流][training-workflow]。该流程沿用本仓库的[数据卡](docs/DATA-CARD.md)和[内容权利说明](CONTENT-RIGHTS.md)，不扩大内容许可范围。Agent 开始工作前读取 [AGENTS.md](AGENTS.md)。

## 仓库结构

```text
data/
  schema.json           schema_version=3 与四实体声明
  items.jsonl           内容条目、集合、外部标识和关联
  documents/            基础转录、整理稿、动态和专栏
  assets.jsonl          音频、ZIP 归档及独立文本资产的索引
  annotations.jsonl     有范围限定的人工确认与片段归属
  artifacts/            资产索引引用的独立参照稿和 HTML 文件
selections/
  topics.json           可选的资料专题查询规则
src/weimingzi_corpus/   本地维护工具
tools/                 命令入口与保存恢复工具
tests/                 数据契约与工具测试
docs/                  规则、自动生成的目录与计数
```

四实体 JSON、JSONL 及资产索引引用的文件是维护版本。文档正文只存一份 `text`，`blocks` 使用 Unicode 码点半开区间 `range` 引用正文；无法由正文精确切片还原的原块使用 `literal` 保存。来源和输入通过 `inputs` 关联，确认与归属通过标注的 `targets` 指向适用对象。

当前命令和 Python 兼容接口仍提供旧逻辑表视图，例如 `transcripts`、`edited_transcripts`、`collections`、`audio`；这些名称不表示 v3 中还存在同名物理文件。Markdown 目录由维护数据生成；TXT、Markdown 正文、字幕、CSV 和 SQLite 按需导出。音频文件通过 Releases 恢复到本地 `media/audio/`，不提交到 Git。

数据规模见自动生成的 [counts.json](docs/counts.json)。同一条目可以关联多份转录和整理稿；目录排序与训练选稿均不表示全文通过人工审核。

目录中的“平台 AI 字幕”“平台 CC 字幕”“本地语音转录”“云端语音转录”是不同的基础转录结果；“整理稿”是整理或校对后的独立结果。链接附有已知模型和短 ID，整理稿后的“输入”指出它关联的基础转录。具体区别与示例见[基础转录与整理稿](docs/GLOSSARY.md#基础转录与整理稿)。

## 使用

使用 uv 管理 Python 环境和项目依赖，`.python-version` 固定 Python 3.12，`uv.lock` 固定依赖解析结果；运行工具仅依赖标准库。

```sh
uv sync --locked
uv run python tools/corpus.py validate
uv run python tools/corpus.py generate
uv run python tools/check_repository.py
uv run python -m unittest discover -s tests -v
```

导出本地检索库后，可检索中文正文：

```sh
uv run python tools/corpus.py export --format sqlite --output .cache/exports/corpus.sqlite3
uv run python tools/corpus.py search 唯物主义
```

SQLite 是从归档记录生成的本地检索副本，不替代 JSON/JSONL 维护数据。检索结果用于定位正文；校对标注、附注等内容请按[维护说明](docs/MAINTENANCE.md)查询。代理操作本仓库前请先阅读[代理使用指南](docs/AGENT-GUIDE.md)。

入库格式、记录 ID 和其他导出方式见 [维护说明](docs/MAINTENANCE.md)。文档入口、合并去向和验收安排见[文档重构计划](docs/DOCUMENTATION-REFACTOR-PLAN.md)。

## 许可

本项目贡献者有权授权的原创代码和原创项目说明文档采用 MIT 许可。归档语料及其中的第三方内容不作统一再许可，已有的明确许可继续适用。完整范围见 [LICENSE](LICENSE)，内容使用与归属问题见 [内容权利说明](CONTENT-RIGHTS.md)。

[training-project]: https://github.com/chosenecho/weimingzi-thought-model/tree/codex/multi-repo-decoupling
[training-workflow]: https://github.com/chosenecho/weimingzi-thought-model/blob/dbb1113d5888d9f577ac5194ce0c74b542a939d9/docs/MULTI_REPO_WORKFLOW.md
