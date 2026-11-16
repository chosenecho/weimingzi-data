# 未明子资料库

维护未明子的视频、录音转录、整理稿、动态和专栏。归档数据采用 schema v3，统一为条目、文档、资产和标注四类实体；平台标识、原文链接和模型信息保留在记录中。

| 要做的事 | 入口 |
| --- | --- |
| 浏览资料、查看校对状态 | [内容目录](docs/INDEX.md)、[校对目录](docs/catalog/reviews.md) |
| 找稿、专题查询、导出和全文检索 | [查询与导出](docs/QUERY.md) |
| 理解实体、字段、时间与项目术语 | [数据结构](docs/SCHEMA.md) |
| 入库、修订和人工证据维护 | [维护流程](docs/MAINTENANCE.md)、[批次协议](docs/INCREMENTAL-INGEST-SPEC.md) |
| 恢复音频、保存校验、周期审计与交接 | [保存流程](docs/PRESERVATION.md) |
| 核对限制、质量与权利范围 | [数据卡](docs/DATA-CARD.md)、[内容权利](CONTENT-RIGHTS.md)、[许可证](LICENSE) |
| 检查资料库验收和证据 | [验收矩阵](docs/ARCHIVE-ACCEPTANCE.md) |

代理开始维护前阅读 [AGENTS](AGENTS.md)。历史实现和发布记录从验收矩阵进入，当前操作按上表对应任务说明执行。

## 与训练工程协作

本仓库负责资料归档和来源校订。数据制作与模型训练在 [weimingzi-thought-model][training-project] 进行；正式 train/dev、来源证据和版本清单发布到独立私有仓库 `chosenecho/weimingzi-datasets`。

| 需要处理的内容 | 修改位置 |
| --- | --- |
| 原始正文、转录、整理稿和来源校订 | 本仓库的维护数据 |
| 筛选、问答审核、模型导出、训练与评测 | 制作和训练工程 |
| 已审核训练数据的新版本 | 私有正式数据仓库，由制作工程生成 |

下游锁定本仓完整 Git 提交，不跟随本地未提交改动。制作工程中的 `configs/corpus/training.json` 维护选稿，`release.json` 维护发布 head、确认引用和段落排除，`consumption-handoff.json` 记录原始提交、配置哈希和投影核对。消费字段、校验及导出命令以该工程的 `docs/CORPUS_CONSUMPTION.md` 为准。

本仓先修订资料、保留原记录及依据，并完成维护检查；下游随后更新锁定提交和消费配置，再制作、审核与发布新版本。消费规则失效由下游处理，不阻断有效资料入库。选稿不改变全文人工审核状态，也不授予第三方内容使用权。确认与片段归属分别按原文、哈希、时间和适用范围引用。

原始交接来自完整提交 `2cdba19147d7df4b05ebcc53b89f83afe4297be5`，按 Git 对象原字节核对。其[历史发布文档][historical-release]仅用于复现当时策略：`clean` 的局部确认可能使整段进入投影，`full` 保留未被配置排除的 head 段落，两者均不证明全文审核通过。已有冻结训练包、版本和历史审批保持原字节。

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

四实体 JSON、JSONL 及资产索引引用的文件是维护版本。正文定位、实体关系和兼容接口的逻辑视图区别统一见[数据结构](docs/SCHEMA.md)。目录与各类导出由维护数据生成，音频通过[保存流程](docs/PRESERVATION.md#音频恢复)恢复到本地，不提交到 Git。

数据规模见自动生成的 [counts.json](docs/counts.json)。同一条目可以关联多份转录和整理稿；目录排序与训练选稿均不表示全文通过人工审核。

目录中的识别方式、模型和输入标记见[基础转录与整理稿](docs/SCHEMA.md#基础转录与整理稿)。

## 使用

使用 uv 管理 Python 环境和项目依赖，`.python-version` 固定 Python 3.12，`uv.lock` 固定依赖解析结果；运行工具仅依赖标准库。

```sh
uv sync --locked
uv run python tools/corpus.py --help
```

找稿和检索先按[查询流程](docs/QUERY.md#全文检索)生成本地索引；正文索引、校对标注和独立参照稿各有对应入口。入库与修订后的完整检查步骤见[维护流程](docs/MAINTENANCE.md#维护后检查)。文档各章节的合并去向和验收记录见[文档重构记录](docs/DOCUMENTATION-REFACTOR-PLAN.md)。

## 许可

本项目贡献者有权授权的原创代码和原创项目说明文档采用 MIT 许可。归档语料及其中的第三方内容不作统一再许可，已有的明确许可继续适用。完整范围见 [LICENSE](LICENSE)，内容使用与归属问题见 [内容权利说明](CONTENT-RIGHTS.md)。

[historical-release]: https://github.com/chosenecho/weimingzi-data/blob/2cdba19147d7df4b05ebcc53b89f83afe4297be5/docs/RELEASE.md
[training-project]: https://github.com/chosenecho/weimingzi-thought-model/tree/codex/multi-repo-decoupling
[training-workflow]: https://github.com/chosenecho/weimingzi-thought-model/blob/dbb1113d5888d9f577ac5194ce0c74b542a939d9/docs/MULTI_REPO_WORKFLOW.md
