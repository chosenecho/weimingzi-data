# 文档重构计划与实施记录

状态：文档重构已实施，逐节去向和本地验收入口已核对。日期：2026-11-17。原始计划见 [bbcf77a 中的版本](https://github.com/chosenecho/weimingzi-data/blob/bbcf77a0b9e78584c9721ea682c8319903fdf15d/docs/DOCUMENTATION-REFACTOR-PLAN.md)。

本次只重构当前资料仓库的说明、生成导航及链接检查。目标是让读者按任务找到唯一的说明入口，减少同义定义、操作命令和运行状态的重复维护；不改变归档记录、人工审核状态、时间值、批次输入协议或已冻结工件。

## 一、目标入口与职责

根目录 [README](../README.md)负责资料用途、快速开始和任务导航，[AGENTS](../AGENTS.md)负责代理修改边界、证据回查和验收入口。14 份当前手工说明合并为以下 7 份；本实施记录、生成目录和历史参考不计入这 7 份。

| 当前任务说明 | 唯一职责 |
| --- | --- |
| [SCHEMA.md](SCHEMA.md) | 四实体、正文定位、引用、哈希与术语 |
| [MAINTENANCE.md](MAINTENANCE.md) | 入库、局部修订、人工证据、候选校验与中断恢复 |
| [QUERY.md](QUERY.md) | 找稿、关联、专题、正文与标注导出、SQLite 检索 |
| [PRESERVATION.md](PRESERVATION.md) | 保存范围、音频恢复、基线、事件链、周期审计、失败处置及交接 |
| [DATA-CARD.md](DATA-CARD.md) | 来源、质量限制、适用范围和内容权利入口 |
| [INCREMENTAL-INGEST-SPEC.md](INCREMENTAL-INGEST-SPEC.md) | 实际批次协议、字段与哈希边界、错误及外部发布设计状态 |
| [ARCHIVE-ACCEPTANCE.md](ARCHIVE-ACCEPTANCE.md) | 可执行验收矩阵、证据位置和持续运行门槛 |

合并后的当前说明不保留旧文件名跳转页。下表中的旧页面名及原章节名是迁移标识，不是当前导航；完整原文仍可在原始提交中读取。

## 二、逐节去向

### 结构与术语

| 原页面与章节 | 当前去向及保留内容 |
| --- | --- |
| SCHEMA：四类维护实体 | [四类维护实体](SCHEMA.md#四类维护实体)，保留实体边界和维护布局 |
| SCHEMA：唯一正文与分块 | [唯一正文与分块](SCHEMA.md#唯一正文与分块)，保留 Unicode 码点半开区间、literal 与原块粒度 |
| SCHEMA：输入与关系 | [输入与关系](SCHEMA.md#输入与关系)，保留角色、单向关系和历史输入快照 |
| SCHEMA：人工证据与模型标注 | [人工证据与模型标注](SCHEMA.md#人工证据与模型标注)及其三个子节，分别解释标注、确认与归属 |
| SCHEMA：工件、恢复位置与哈希 | [工件、恢复位置与哈希](SCHEMA.md#工件恢复位置与哈希)，保留文件字节、规范 JSON 和原文锚点的不同边界 |
| SCHEMA：元数据、派生值与旧格式投影 | [同名章节](SCHEMA.md#元数据派生值与旧格式投影)，保留缺省/null/false 差异、观测字段及有限可逆配方 |
| SCHEMA：迁移与验收 | [迁移与验收](SCHEMA.md#迁移与验收)，保留独立临时迁移、逐记录往返、下游导出和旧冻结字节要求 |
| GLOSSARY：数据对象 | [四类维护实体](SCHEMA.md#四类维护实体)，区分条目、文稿、资产、标注和可重建派生物 |
| GLOSSARY：基础转录与整理稿 | [基础转录与整理稿](SCHEMA.md#基础转录与整理稿)，保留平台字幕、真实音频 ASR、整理结果与模型来源区别 |
| GLOSSARY：分段、识别块与输入单位 | [正文与分块](SCHEMA.md#唯一正文与分块)及[输入关系](SCHEMA.md#输入与关系)，保留原单位、时间和引用解释 |
| GLOSSARY：校对标注与参照稿 | [校对标注与参照稿](SCHEMA.md#校对标注与参照稿)，保留候选、说明、参照、附注与独立稿的差异 |
| GLOSSARY：输入快照与生成信息 | [输入与关系](SCHEMA.md#输入与关系)，历史快照不随上游更新，来源路径不用于猜测模型 |
| GLOSSARY：标识、元数据与派生结果 | [元数据、派生值与旧格式投影](SCHEMA.md#元数据派生值与旧格式投影)，保留 ID、来源标识及原生/投影区别 |
| GLOSSARY：质量、完整性与可用状态 | [质量、完整性与可用状态](SCHEMA.md#质量完整性与可用状态)，不从局部确认、空文本或下载定位推断其他结论 |
| GLOSSARY：下载定位 | [工件、恢复位置与哈希](SCHEMA.md#工件恢复位置与哈希)，操作集中到保存说明 |

### 维护与增量接收

| 原页面与章节 | 当前去向及保留内容 |
| --- | --- |
| MAINTENANCE：添加数据 | [添加数据](MAINTENANCE.md#添加数据)及[单表兼容输入](MAINTENANCE.md#单表兼容输入)，保留候选库、同 ID 比较、真实不同结果并列及原时间 |
| MAINTENANCE：导入双视频结果包 | [同名章节](MAINTENANCE.md#导入双视频结果包)，保留 ZIP 适配、哈希、视频身份、模型未知、完整性限定和源包移除后的追溯依据 |
| MAINTENANCE：增量批次 | [增量批次](MAINTENANCE.md#增量批次)，集中实际校验、规划、应用、冲突、凭证和中断步骤 |
| MAINTENANCE：导出与检索、查看校对标注 | [正文与标注导出](QUERY.md#导出正文与标注)、[标注查看](QUERY.md#查看校对标注)和[全文检索](QUERY.md#全文检索)，原维护页只保留入口 |
| MAINTENANCE：人工确认与下游选稿 | [人工确认与局部修订](MAINTENANCE.md#人工确认与局部修订)；下游职责迁入 [README](../README.md#与训练工程协作) |
| MAINTENANCE：片段归属 | [片段归属](MAINTENANCE.md#片段归属)，保留审核原话、原文哈希、时间、unknown、另建修订及与文字确认的区分 |
| INCREMENTAL-INGEST：职责边界 | [维护前提](MAINTENANCE.md#维护前提)，保留目标范围、本地无网络凭据及生产端职责 |
| INCREMENTAL-INGEST：现有能力与缺口 | [增量批次](MAINTENANCE.md#增量批次)和[发布与回执](MAINTENANCE.md#发布与回执)，区分已实现本地内核与未启用外部发布 |
| INCREMENTAL-INGEST：交接包 | [交接包与输入版本](MAINTENANCE.md#交接包与输入版本)，保留 v2 载荷、不可变清单、身份映射和完整候选引用 |
| INCREMENTAL-INGEST：命令与合并规则 | [校验、规划与应用](MAINTENANCE.md#校验规划与应用)、[候选结果与冲突](MAINTENANCE.md#候选结果与冲突)、[中断与重试](MAINTENANCE.md#中断与重试) |
| INCREMENTAL-INGEST：分阶段交付 | [分阶段交付](MAINTENANCE.md#分阶段交付)，保留文字先行、依赖凭证、字幕与音频 ASR 独立、AI 待复核及媒体回读边界 |
| INCREMENTAL-INGEST：PR 与回执 | [发布与回执](MAINTENANCE.md#发布与回执)，保留串行 PR、幂等、重算、禁止强推及远端接收对账要求 |
| INCREMENTAL-INGEST：上线前验证 | [发布与回执](MAINTENANCE.md#发布与回执)及[维护后检查](MAINTENANCE.md#维护后检查)，保留合成验收、真实接入顺序和发现游标失败语义 |

### 查询、专题与代理规则

| 原页面与章节 | 当前去向及保留内容 |
| --- | --- |
| COVERAGE：分层文稿覆盖查询正文 | [找稿与关联](QUERY.md#找稿与关联)，保留四层、一跳、完整哈希身份、原路径、去重、所有变体及纯填充词筛查限制 |
| COVERAGE：回归案例 | [回归案例](QUERY.md#回归案例)，保留五组具体条目、来源关系和 issue/人工证据入口 |
| TOPICS：专题索引的维护与导出全文 | [专题查询](QUERY.md#专题查询)，保留五类规则、四种角色、非关键词导入特例、跨层计数与基础校验独立性 |
| AGENT-GUIDE：项目范围、开始前 | [AGENTS 职责与任务入口](../AGENTS.md#职责与任务入口)及[开始与修改](../AGENTS.md#开始与修改)，保留未知状态、已有改动和生成物保护 |
| AGENT-GUIDE：查找和引用 | [AGENTS 检索与引用](../AGENTS.md#检索与引用)及 [QUERY 全文检索](QUERY.md#全文检索)，保留短词、索引范围、证据回查、时间单位和引用字段要求 |
| AGENT-GUIDE：下游消费 | [AGENTS 验收与下游交接](../AGENTS.md#验收与下游交接)、[README 分工](../README.md#与训练工程协作)和[专题查询](QUERY.md#专题查询) |
| AGENT-GUIDE：保存和修改 | [AGENTS 开始与修改](../AGENTS.md#开始与修改)、[维护后检查](MAINTENANCE.md#维护后检查)及[原生/投影读取](QUERY.md#导出正文与标注)，保留输入快照、人工证据和原时间规则 |
| RELEASE：交接位置 | [README 与训练工程协作](../README.md#与训练工程协作)，保留三个消费配置位置、完整 Git 提交及原始交接提交 |
| RELEASE：下游命令 | [README 下游消费说明入口](../README.md#与训练工程协作)，当前命令由下游文档维护，旧算法保留不可变历史文档入口 |
| RELEASE：资料更新后的流程 | [README 与训练工程协作](../README.md#与训练工程协作)，保留来源先修订、下游重新制作审核、full/clean 限定、局部证据与冻结字节边界 |

### 保存、恢复与交接

| 原页面与章节 | 当前去向及保留内容 |
| --- | --- |
| PRESERVATION：保存范围 | [保存范围](PRESERVATION.md#保存范围)，保留权威、支持、生成物、缓存、媒体和独立选择器分类 |
| PRESERVATION：建立与验证 | [基线与事件链](PRESERVATION.md#基线与事件链)，保留范围错误、并发、摘要、事件追加和非签名边界 |
| PRESERVATION：定期运行 | [周期审计](PRESERVATION.md#周期审计)，保留只读与留痕入口及 Windows 脚本调用 |
| PRESERVATION：下一步门槛 | [责任交接与保留退出](PRESERVATION.md#责任交接与保留退出)及[持续运行门槛](ARCHIVE-ACCEPTANCE.md#持续运行门槛)，保持未完成状态 |
| DOWNLOAD：音频下载全文 | [音频恢复](PRESERVATION.md#音频恢复)，保留 schema/自定义索引、归档引用、原成员名、字节哈希、不可用状态和缓存路径 |
| PRESERVATION-OPERATIONS：周期检查 | [周期审计](PRESERVATION.md#周期审计)，保留触发时间、只读权限、报告回读、90 天期限及计划触发证据限制 |
| PRESERVATION-OPERATIONS：失败处置 | [失败处置与恢复](PRESERVATION.md#失败处置与恢复)，保留报告、损坏字节、事件链失败和另建基线要求 |
| PRESERVATION-OPERATIONS：恢复与回读 | [失败处置与恢复](PRESERVATION.md#失败处置与恢复)及[历史恢复证据](PRESERVATION.md#历史恢复证据与范围)，区分合成、抽样、全量和中断证据 |
| PRESERVATION-OPERATIONS：全量媒体审计 | [全量媒体审计](PRESERVATION.md#全量媒体审计)，保留临时逐卷、并发限制、不可覆盖检查点、依赖变化与范围边界 |
| PRESERVATION-OPERATIONS：责任与访问交接 | [责任与访问](PRESERVATION.md#责任与访问)，保留负责人待定、凭据不入库、接收回读及第二副本暂缓状态 |
| PRESERVATION-OPERATIONS：保留与退出 | [保留与退出](PRESERVATION.md#保留与退出)，保留历史不清理、缓存条件、权利请求与退出接收范围 |

### 保留的协议、质量和验收说明

| 原页面与章节 | 当前去向及保留内容 |
| --- | --- |
| DATA-CARD 全文 | [数据卡](DATA-CARD.md)，保留来源、质量限制、适用范围和许可入口；只修订导航 |
| SPEC：设计决策与依据、运行拓扑（FC 采集适配层） | [协议原章节](INCREMENTAL-INGEST-SPEC.md#设计决策与依据)，保留范围、生产端历史观察及待接入云资源说明 |
| SPEC：发现与阶段交付（首次建立基线、各阶段的提交条件） | [同名章节](INCREMENTAL-INGEST-SPEC.md#发现与阶段交付)，保留发现、任务持久化、处理与接收分别记账 |
| SPEC：身份映射与确定性投影 | [同名章节](INCREMENTAL-INGEST-SPEC.md#身份映射与确定性投影)，保留身份匹配、前置哈希和来源映射 |
| SPEC：批次协议（哈希边界、路径和容量规则） | [同名章节](INCREMENTAL-INGEST-SPEC.md#批次协议)，保持 v2 输入版本、字节/规范 JSON 哈希及容量约束 |
| SPEC：操作与合并规则（insert、enrich、attach_audio_distribution、人工维护保护） | [同名章节](INCREMENTAL-INGEST-SPEC.md#操作与合并规则)，保留受限操作和保护字段，不扩大维护权限 |
| SPEC：媒体、全文与可用性 | [同名章节](INCREMENTAL-INGEST-SPEC.md#媒体全文与可用性)，保留媒体回读、完整正文和质量独立性 |
| SPEC：本地入口与候选库算法 | [同名章节](INCREMENTAL-INGEST-SPEC.md#本地入口与候选库算法)，保留实际已实现内核，操作命令集中到维护页 |
| SPEC：GitHub 接收、PR 与重放（投递信封、生产端 outbox、发布过程） | [同名章节](INCREMENTAL-INGEST-SPEC.md#github-接收pr-与重放)，明确仍为外部发布设计 |
| SPEC：接收凭证与状态机 | [同名章节](INCREMENTAL-INGEST-SPEC.md#接收凭证与状态机)，保留重放、already_present 与真实接收证据差异 |
| SPEC：错误分类与恢复、运行状态与保留策略 | [错误分类与恢复](INCREMENTAL-INGEST-SPEC.md#错误分类与恢复)及[运行状态与保留策略](INCREMENTAL-INGEST-SPEC.md#运行状态与保留策略)，保留退出码、暂停与恢复路径 |
| SPEC：模块与实施顺序、验收矩阵 | [模块与实施顺序](INCREMENTAL-INGEST-SPEC.md#模块与实施顺序)及[验收矩阵](INCREMENTAL-INGEST-SPEC.md#验收矩阵)，区分本地完成项与外部待办 |
| ARCHIVE-ACCEPTANCE：证据入口、本地验收、持续运行门槛 | [验收矩阵](ARCHIVE-ACCEPTANCE.md)，保留证据、检查命令和未完成门槛，只更新导航与 uv 用法 |

## 三、实现边界

当前流程以 schema v3 四实体为主线；逻辑输入协议和旧字段投影按实际接口解释。缺失、null、false、待复核、适用、实际采用和全文审核分别保留，不以合并说明为由改变语义。完整操作只在所属任务页展开，入口页面提供目的和链接。

当前 Python 操作统一通过 `uv sync --locked` 和 `uv run`；两份保存审计工作流也使用同一锁定环境。历史日志和原始引文不改字面。当前统计读取生成结果，不在手工说明重复维护；历史恢复数量继续标注具体日期和证据范围。

生成器改为指向结构、查询和标注的新章节，并通过生成命令更新目录。链接检查递归核对仓库本地文件和 Markdown 章节，支持中文、编码路径、同页链接、重复标题、显式锚点和目录 README；代码示例与注释不作为导航。它不是完整 Markdown 渲染器。

保持原字节的历史 Markdown 仅按明确文件名单豁免其中的旧链接：v2 结构、保存迭代记录及两份既有问题证据。`data/artifacts/` 是归档原内容，不解释为仓库导航。当前说明即使放在 evidence、decisions 或 preservation 目录，也仍检查；从当前说明链接到历史文件时仍核对目标及章节。

## 四、历史与保存范围

[v2 结构](SCHEMA-V2.md)、[保存迭代记录](PRESERVATION-ROADMAP.md)、[既有证据](evidence/)、[机器契约](contracts/)、[结构决策](decisions/)及旧保存清单不改原文。[示例](examples/)继续描述实际输入协议。[内容目录](INDEX.md)、[分类目录](catalog/)和[计数](counts.json)由工具重建。

支持文件清单移除已合并的八份旧说明，加入查询页和贡献入口。范围变更另建版本化保存基线，不重写旧清单；选择器独立更新，事件日志只追加。验收对照实施前逐文件大小和 SHA-256，要求维护数据及历史文件相同，原日志前缀相同，只允许新增本轮基线及追加事件。

## 五、验收步骤

在仓库根目录执行：

```sh
uv sync --locked
uv run python tools/corpus.py validate
uv run python tools/corpus.py generate
uv run python tools/check_repository.py
uv run python -m unittest discover -s tests -v
uv run python tools/preservation_manifest.py check-current --read-only
uv run python tools/preservation_manifest.py verify-log
git -c core.whitespace=cr-at-eol diff --check
```

另按[基线与事件链](PRESERVATION.md#基线与事件链)创建、选择并留痕核对本轮新基线。新基线需无新增、缺失、变化或不可读项，事件链需通过；旧基线原字节和原事件前缀需与实施前相同。远端媒体回读及外部接收服务不因本次文档验收升级为已完成状态。
