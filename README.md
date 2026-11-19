# 未明子资料库

维护未明子的视频、录音转录、整理稿、动态和专栏。归档数据采用 schema v3，统一为条目、文稿、资产和标注四类实体；平台标识、原文链接和模型信息保留在记录中。

| 要做的事 | 入口 |
| --- | --- |
| 浏览资料、查看校对状态 | [内容目录](docs/INDEX.md)、[校对目录](docs/catalog/reviews.md) |
| 找稿、专题查询、导出和全文检索 | [查询与导出](docs/QUERY.md) |
| 理解实体、字段、时间与项目术语 | [数据结构](docs/SCHEMA.md) |
| 入库、修订和人工证据维护 | [维护流程](docs/MAINTENANCE.md)、[批次协议](docs/INCREMENTAL-INGEST-SPEC.md) |
| 恢复音频、保存校验、周期审计与交接 | [保存流程](docs/PRESERVATION.md) |
| 核对限制、质量与权利范围 | [数据卡](docs/DATA-CARD.md)、[内容权利](CONTENT-RIGHTS.md)、[许可证](LICENSE) |
| 验收发布候选、查历史发布证据 | [发布验收清单](docs/ARCHIVE-ACCEPTANCE.md#发布验收清单) |

代理开始维护前阅读 [AGENTS](AGENTS.md)。

<a id="与训练工程协作"></a>

## 仓库职责

本仓库负责资料归档、来源校订、检索和可核验恢复。原文、模型结果、人工局部确认和片段归属分别保存；选用某份资料不改变其质量或全文审核状态，也不扩大内容许可。维护与验收只以本仓当前四实体契约为准。

## 仓库结构

```text
data/
  schema.json           schema_version=3、四实体与 Unicode 码点区间声明
  items.jsonl           内容条目、有序集合、外部标识和关联
  documents/            transcript、edited_transcript、post、article
  assets.jsonl          audio、html、review_document、archive
  annotations.jsonl     confirmation、segment_attribution
  artifacts/            资产引用的独立参照稿和 HTML 原字节
selections/
  topics.json           可选的资料专题查询规则
src/weimingzi_corpus/   本地维护工具
tools/                 命令入口与保存恢复工具
tests/                 数据契约与工具测试
docs/                  当前说明、历史证据及生成目录与计数
```

四实体 JSON、JSONL 及资产引用的工件是维护版本。记录使用原生 `kind`、`inputs`、`blocks` 和 `targets`，结构与读取 Interface 见[数据结构](docs/SCHEMA.md)。JSON/JSONL 导出保持原生记录；目录、CSV、字幕和全文索引是派生结果。音频通过[保存流程](docs/PRESERVATION.md#音频恢复)恢复到本地，不提交到 Git。

数据规模见自动生成的 [counts.json](docs/counts.json)。同一条目可以关联多份转录和整理稿，并列或排序不表示质量高低或全文已人工审核。识别方式、模型和输入标记见[基础转录与整理稿](docs/SCHEMA.md#基础转录与整理稿)。

## 使用

使用 uv 管理 Python 环境和项目依赖，`.python-version` 固定 Python 3.12，`uv.lock` 固定依赖解析结果；运行工具仅依赖标准库。

```sh
uv sync --locked
uv run python tools/corpus.py --help
uv run python tools/corpus.py validate
uv run python tools/corpus.py export --entity documents --id RECORD_ID --format json --output .cache/exports/document.json
```

找稿和检索先按[查询流程](docs/QUERY.md#全文检索)生成本地索引；正文索引、校对标注和独立参照稿各有对应入口。入库与修订后的检查见[维护流程](docs/MAINTENANCE.md#维护后检查)。当前原生整理的执行与证据见[实施记录](docs/NATIVE-V3-CLEANUP.md)；历史证据、收据和冻结工件保留原字节，按其自身版本解释。

## 许可

本项目贡献者有权授权的原创代码和原创项目说明文档采用 MIT 许可。归档语料及其中的第三方内容不作统一再许可，已有的明确许可继续适用。完整范围见 [LICENSE](LICENSE)，内容使用与归属问题见 [内容权利说明](CONTENT-RIGHTS.md)。
