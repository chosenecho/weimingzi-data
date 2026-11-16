# 维护与入库

本文集中说明本仓的入库、局部修订和检查。实体、时间、哈希及术语见[数据结构](SCHEMA.md)；批次字段、算法和外部投递设计见[增量协议](INCREMENTAL-INGEST-SPEC.md)。

## 维护前提

先运行 `git status --short`，保留已有改动；用 `uv sync --locked` 准备锁定环境，再通过 `uv run` 执行工具。本仓维护来源、原文、结构化记录和人工证据；监听、采集、下载、ASR、对齐、AI 校对、任务队列及失败重试由生产端负责。仓库本地入库命令不使用网络凭据。

增量服务范围固定为 `chosenecho/weimingzi-data`，目标 Bilibili UID 为 `23191782`。转发、文章及视频参照仍保留实际来源、作者和上传者；范围配置不替代逐条来源核对。云端发布任务的凭据、传输及 PR 职责见[发布与回执](#发布与回执)。

## 添加数据

按[数据结构](SCHEMA.md)生成记录。当前 `data/schema.json` 声明 v3，仅有四类维护实体：条目与有序集合在 [items.jsonl](../data/items.jsonl)，文稿在 [documents](../data/documents)，音频、归档及独立文本资产在 [assets.jsonl](../data/assets.jsonl)，人工确认与片段归属在 [annotations.jsonl](../data/annotations.jsonl)。先创建条目再加入文稿；已有内容沿用条目，不按平台或采集日期另建目录。

### 单表兼容输入

现有 `import --table` 接受旧逻辑表名和旧字段，由写入入口转换为四实体。可选逻辑表为 `items`、`audio`、`collections`、`transcripts`、`edited_transcripts`、`confirmations`、`attributions`、`posts`、`articles`。这些是现有 CLI 的输入协议，不是维护目录，也不表示新增了四实体直接导入接口。

```sh
uv run python tools/corpus.py import --table items incoming-items.jsonl
uv run python tools/corpus.py import --table transcripts incoming-transcript.json
uv run python tools/corpus.py import --table edited_transcripts incoming-edited-transcript.json
```

输入可以是单条 JSON、JSON 数组或 `.jsonl` 文件；空输入或同一输入中重复 ID 会报错。命令在隔离候选副本中校验完整数据及引用后才安装：已有 ID 与逻辑记录完全相同则跳过，同 ID 内容不同则报错。需要修订已有元数据时编辑对应原生维护记录，再执行[维护后检查](#维护后检查)；不把旧视图 JSON 覆盖到 `data/documents/`，也不按逻辑表名新建旧目录。

原生文稿只保存一份正文，块选择器、输入关系、历史快照和独立工件按[结构契约](SCHEMA.md#唯一正文与分块)维护；不为通过导出而重算、修整或重排原时间。同一条目真实不同的结果并列保存，没有文字或时间差异的导出副本不再入库。局部、缺失和待复核结果保留相应质量状态。

### 导入双视频结果包

`requested-video-results/v1` 结果 ZIP 使用独立适配入口，可重复执行；它与下文只接受目录的增量批次协议分开：

```sh
uv run python tools/corpus.py import-package .cache/incoming/requested-video-results.zip
```

适配器逐一核对清单文件、大小和 SHA-256，按 BVID、分 P、CID 匹配已有条目，在隔离候选副本中同时校验新增基础转录和整理稿。相同包重复导入不新增或替换旧结果。源包哈希、完整清单、视频快照和上游运行标识保存在 `metadata.source_package` 与 `metadata.upstream`。

正文、原段文字、候选改法、参照标签与完整独立校验稿分别保留。此包中 `is_complete` 表示全部输入段被整理块引用一次，不证明音频全覆盖或人工审核完成；两份整理稿均保留待复核状态。包内只有 ASR `model_id`，不足以确定模型名称，故规范记录的 `model` 为 null。字幕按原时间值校验，不排序或截断旧结果。

导入及检查成功后，结果 ZIP 可从当前仓库版本移除；规范记录保留源包 SHA-256、完整 manifest、各成员校验信息和上游定位，维护脚本不依赖仓库留存该 ZIP。以后重新导入时先把原包放入忽略目录，再传入路径。

## 增量批次

本地 `verify`、`plan`、`apply`、接收凭证和 `validate-repository` 已实现；对象存储交接、生产端 outbox、受信 GitHub 接收工作流与自动 PR 尚未启用。自动批次不修改人工确认、片段归属或训练选稿；现有单表兼容导入能力不扩大批次操作白名单。

### 交接包与输入版本

交接包由 `manifest.json` 和清单列明的每记录 JSON 文件组成。详细字段、路径及容量约束见[批次协议](INCREMENTAL-INGEST-SPEC.md#批次协议)和[机器可读 Schema](contracts/ingest-batch-v1.schema.json)。清单使用 `contract_version`、不可变 `batch_id`、`producer`、`source_scope`、`base_commit`、`created_at`、`requires_batches`、`sources`、`files` 和 `operations`；`operations` 表达目标逻辑表、记录、操作和前置条件，文件清单保存路径、字节数及 SHA-256。

当前接收载荷仍为 `record_schema_version=2`，完整记录保留 `schema_version=2`，字段语义参见[v2 协议参考](SCHEMA-V2.md)。适配器把它们写入当前四实体及资产引用的工件。文档更名或维护格式 v3 不改变该输入协议，包内 `records/transcripts/` 等路径不决定维护文件路径。

批次身份由移除自身字段后的规范清单计算，传输信息放在包外。清单、文件和操作封包后固定，重投原包不改生成时间；改变记录或操作生成新批次。拒绝越界、重复、未列明或不符合协议的路径。生产程序及代码版本、运行和上游对象身份须可追溯，凭据不进入包。

包只需包含本次记录和对已有记录的引用，不必独立构成完整语料；引用在与目标仓库合并后的完整候选库校验。包中缺少某记录不表示删除。生产端需先固定可检出的 `corpus export`、`corpus verify` 版本和 `--identity-from` 映射，再转换为批次操作；不使用导出的整个 `data/`、空确认表或空选稿覆盖维护库。设计时检查的生产端导出路径面向视频、字幕、ASR 和已提交 AI 修订；动态、图文、文章和图片仍需对应采集适配，并通过同一批次入口交付。

### 校验、规划与应用

规划与应用在 origin 指向目标仓库、工作区干净的专用 Git 检出目录执行。交接包交给批次命令处理，不直接把包内文件复制到维护数据目录。将下列批次、检出和报告路径替换为实际位置；报告必须在检出目录外，或位于被 Git 忽略的 `.cache/`，不能覆盖包内文件。

```sh
uv run python tools/corpus.py ingest verify /path/to/batch
uv run python tools/corpus.py --root /path/to/clean/checkout ingest plan /path/to/batch --report /tmp/ingest-plan.json
uv run python tools/corpus.py --root /path/to/clean/checkout ingest apply /path/to/batch --plan /tmp/ingest-plan.json
uv run python tools/corpus.py --root /path/to/clean/checkout ingest validate-repository
```

`verify` 只读检查清单、容量、原始文件哈希、来源范围与操作语义。`plan` 在隔离副本一次投影跨表操作，校验完整引用、媒体定位及人工保护，再生成目录和接收凭证候选；不改维护数据。报告列出新增、重复、冲突与拟修改文件，并绑定批次、实际目标提交、策略、内核代码和维护输入哈希。检查报告后再把同一报告交给 `apply`。

`apply` 取得本地目标写入锁，重新核对包、目标提交、策略、内核和文件基线，重新计算候选计划并与批准报告比较。只安装全部验证通过的结果，立即读回文件集及哈希。`validate-repository` 检查已入库批次凭证和类型化媒体字段；普通整库检查也调用它。本地应用成功只表示专用检出目录可供后续发布，不表示远端已接收。

### 候选结果与冲突

- `insert`：新 ID 新增；同 ID 且规范逻辑记录相同跳过。不同则报告冲突，不能用后到数据覆盖；新 ID 也须通过外部身份、音频哈希和重复转录检查。
- `enrich`：仅允许受信策略列明的表、字段和元数据键，按规范 JSON 判等追加观测，不递归合并；正文、模型、时间、质量与身份不靠补充操作改写。
- `attach_audio_distribution`：只给已确认同文件的已有音频追加合格定位，保持已有定位、恢复路径和关联；它不替代媒体上传后的回读核验。
- 新 ASR、AI 或真实文字修订按现有身份约定新增结果，保留原稿和来源链；删除、任意替换和人工维护进入单独维护流程。

一个冲突使整批不可应用，不安装碰巧成功的部分；需拆分时由生产端重新形成独立批次。基线移动后重新规划：互不影响的维护变更可在重算后继续，同记录的差异按上述规则处理，不自动选择一方。错误分类及前置哈希、后置条件的精确判定见[协议的错误与恢复](INCREMENTAL-INGEST-SPEC.md#错误分类与恢复)。

有业务差异的候选含 `ingest/receipts/<batch_id>.json`，凭证保存应用身份、操作及记录前后哈希，不提前写“已合并”。已有相同身份的凭证返回 `already_accepted`；无凭证但全部操作已满足时返回 `already_present`，不制造空业务差异或空凭证。后者的实际见证提交应由外部发布回执保存，不以不存在的凭证满足 `requires_batches`。

### 中断与重试

旧计划、工作区变化、未满足依赖或锁占用先排除对应原因，再重新规划；不编辑报告绕过校验，不仅因锁文件陈旧就删除它。安装前写入 `incomplete` 标记，全部读回成功才移除。进程、磁盘或读回故障造成中断时，该专用检出目录作废，从干净基线重建后重跑；发现标记即停止发布，不能推送半批数据。逐文件替换不是跨文件原子事务，不在有用户改动的日常工作树自动回滚。

损坏包、来源越界、身份歧义、CID 变化和内容冲突保留原包及报告，回生产端核对、重投影或重封包。自动重试不无限循环，也不凭失败响应推进发现游标。完整恢复行为见[协议错误表](INCREMENTAL-INGEST-SPEC.md#错误分类与恢复)。

## 分阶段交付

动态、图文、文章正文准备好即可交付；新视频先交条目和来源，下载、ASR、AI 整理完成后继续提交关联产物。单个视频失败不阻塞其他已完成内容，每批仍须满足完整引用校验。依赖批次须有已接收凭证，开放 PR 不表示依赖满足；已冻结包不再追加产物，后续进入新批次。

视频按平台视频及分 P 身份去重，媒体按文件 SHA-256 核对。Git 保存文字、结构化记录、清单和可验证定位，视频、音频、图片字节使用外部存储或 Release。音频恢复契约见[结构说明](SCHEMA.md#工件恢复位置与哈希)，恢复操作见[保存流程](PRESERVATION.md#音频恢复)；视频和图片定位使用[媒体 Schema](contracts/ingest-media-asset-v1.schema.json)。只有临时播放地址不算完成归档。

平台字幕、真实音频 ASR 和 AI 整理分别保存，不以字幕成功代替要求的音频 ASR。AI 结果保留模型、输入、完整性及待复核标记；自动接收不提升为人工审核完成。时间异常按原值保存，字幕导出仍按既有精度、范围和顺序检查。

## 发布与回执

以下是外部发布任务的设计要求，尚无已启用的自动 PR 服务。发布任务负责网络、对象存储与 GitHub 凭据；本地内核只读写文件。详细信封、outbox、权限和状态机见[GitHub 接收、PR 与重放](INCREMENTAL-INGEST-SPEC.md#github-接收pr-与重放)。

一个批次对应可追踪的分支和 PR，重复投递先对账并复用，无业务变化不建空 PR。首版串行维护自动入库 PR，其余 ready 批次留在持久 outbox。PR 展示来源范围、各表新增、重复及冲突、媒体定位、ASR 与 AI 状态和检查结果。推送仅限批准的数据、生成目录及批次凭证，不接受包中代码、工作流或凭据变更。

发布前执行[维护后检查](#维护后检查)，复查远端基线和机器人分支；并发更新重新规划，分支有人工作业则暂停，不强推覆盖。回执分别记录 `planned`、`pr_open`、`merged`、`rejected`、`failed` 及批次、PR、提交和实际记录身份。只有远端合并事实及目标分支中的凭证或操作结果能确认接收；PR 关闭未合并、事件送达或工作流成功均不替代它。失败尝试、完整日志和重试暂停留生产端。

上线前先验证跨表引用、重投、同 ID 冲突、过期计划、坏文件、越界路径、中断恢复和人工记录保留，再用合成包跑通完整 PR 与回执，最后接真实采集。发现层的动态列表和视频分页失败由生产端解决并保存证据：请求失败不表示无新内容，也不推进覆盖该页的扫描游标。发现、任务持久化、处理完成、仓库接收分别记账，PR 成功不证明已全量发现。

## 查询与导出入口

找正文、查关联、专题和派生导出使用[查询与导出](QUERY.md)：[找稿与关联](QUERY.md#找稿与关联)、[专题查询](QUERY.md#专题查询)、[导出正文与标注](QUERY.md#导出正文与标注)、[全文检索](QUERY.md#全文检索)。查看段落标注、附注和独立参照稿见[查看校对标注](QUERY.md#查看校对标注)。这些派生结果不作为维护源。

专题是可选查询配置；基础 `validate`、记录导入和批次入库不加载专题规则，显式专题查询、`generate` 和全仓检查才核对已有规则。

## 人工确认与局部修订

复核段落时结合精确块文字、输入快照、标签、时间及完整参照稿。复核后保留原校对标注，另建有依据、有适用范围的人工确认；不批量把标注算成未解决问题，也不把 AI 候选升级成人工术语释义。语义与字段见[人工证据](SCHEMA.md#人工证据与模型标注)。

在 `data/annotations.jsonl` 新增 `kind=confirmation`，保存原文字、修订文字、各自哈希、确认范围、核对依据和适用整理稿。`targets` 单向指向条目及文稿：`item` 表示条目，`applies_to` 表示适用；带 `confirmation_index` 的目标保留旧采用列表位置，其中带 `derived_from` 输入的修订文稿使用 `revision` 角色。原生文稿不新增第二份反向列表。

适用不证明正文已采用，采用不证明全文审核。只确认实际审核的字句或术语，全文未审核时保留原 `is_fully_human_reviewed` 状态。发生实际文字修订时新增整理稿结果及真实派生关系，保留原稿、输入快照、模型信息和局部证据，不让新上游覆盖历史快照。

本仓检查归档记录、引用和证据锚点；训练选稿、发布 head、确认应用和段落收录由 [README 所述制作工程](../README.md#与训练工程协作)维护。完成本仓检查后，下游锁定新的完整 Git 提交并更新其消费配置，不在本仓新增训练发布状态。

## 片段归属

审核者看过原视频或听过音频并给出结论后，在 `data/annotations.jsonl` 新增 `kind=segment_attribution`，通过 `targets` 指向条目和适用整理稿。每条针对一个块或块内一句：按 `range` 或 `literal` 还原精确段落文字，计算 UTF-8 SHA-256，复制对应 `start`、`end` 和文稿 `time_unit`；`review.basis` 保留审核者原话。旧逻辑视图仍称 `attributions`，枚举和锚点见[片段说话人与观点归属](SCHEMA.md#片段说话人与观点归属)。

审核后仍不明的归属写 `unknown`，与没有审核记录分开；模型建议不写入人工归属。文字改动使旧段落哈希失效，须重新审核后另建记录，不直接改旧哈希。文字确认与说话人、观点归属分别核对。

写入后执行[维护后检查](#维护后检查)。下游确需引用归属时，在制作工程对应 entry 用 `attribution_ids` 引用证据 ID，不能把没有记录的段落视作已确认。

## 维护后检查

完成数据或证据修改后运行：

```sh
uv run python tools/corpus.py validate
uv run python tools/corpus.py generate
uv run python tools/check_repository.py
uv run python -m unittest discover -s tests -v
```

`generate` 重建 [内容目录](INDEX.md)、[分类目录](catalog/)和 [counts.json](counts.json)，不手改生成文件；CI 检查它们与数据一致。全仓检查核对文档链接、已入库接收凭证和媒体字段，并显式检查已有专题配置。按修改范围完成适用检查后，交付时列明验证结果及未覆盖项。

保存范围或支持文件变化时，按[基线与事件链](PRESERVATION.md#基线与事件链)另建并核对保存基线；历史提交、旧收据、保存清单与冻结工件保持原字节。维护源的有效性不替代远端媒体可达性审计，后者按[周期审计](PRESERVATION.md#周期审计)执行。
