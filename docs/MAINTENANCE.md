# 维护与入库

本文集中说明本仓的入库、局部修订和检查。实体、时间、哈希及读取 Interface 见[数据结构](SCHEMA.md)；批次字段、算法和外部投递设计见[增量协议](INCREMENTAL-INGEST-SPEC.md)。

## 维护前提

先运行 `git status --short`，保留已有改动；用 `uv sync --locked` 准备锁定环境，再通过 `uv run` 执行工具。本仓维护来源、原文、结构化记录和人工证据；监听、采集、下载、ASR、对齐、AI 校对、任务队列及失败重试由生产端负责。本地入库命令不使用网络凭据。

增量服务目标为 `chosenecho/weimingzi-data`，Bilibili UID 为 `23191782`。转发、文章及视频参照仍保留实际来源、作者和上传者；范围配置不替代逐条核对。待接入发布任务的传输及 PR 职责见[发布与回执](#发布与回执)。

## 添加数据

当前 `data/schema.json` 声明 v3：条目和有序集合在 [items.jsonl](../data/items.jsonl)，文稿在 [documents](../data/documents)，音频、归档及独立文本资产在 [assets.jsonl](../data/assets.jsonl)，人工确认与片段归属在 [annotations.jsonl](../data/annotations.jsonl)。按[原生结构](SCHEMA.md)生成记录，以 `kind` 区分业务类型。先创建条目，再加入文稿；已有内容沿用条目，不按平台或采集日期另建目录。

<a id="单表兼容输入"></a>

### 原生实体导入

```sh
uv run python tools/corpus.py import --entity items incoming-items.jsonl
uv run python tools/corpus.py import --entity documents incoming-document.json
uv run python tools/corpus.py import --entity assets incoming-assets.jsonl
uv run python tools/corpus.py import --entity annotations incoming-annotation.json
```

输入可为单条 JSON、JSON 数组或 `.jsonl`，内容必须是完整原生记录；记录不带 `schema_version`。空输入、输入内重复 ID 或未知实体报错。已有 ID 与原生值相同则跳过，同 ID 不同值则冲突。新增结果先在隔离候选副本中进行整图校验，再由唯一安装 primitive 按实际变化文件安装；单文件 `os.replace` 与可捕获 I/O 失败回滚不等于多文件原子事务。

需要维护已有记录时，按事实修改对应原生记录，或经 `write_record_updates(root, {entity: rows})` 原生 upsert 后执行[维护后检查](#维护后检查)。自动批次另受[操作权限](INCREMENTAL-INGEST-SPEC.md#操作与合并规则)限制。

文稿正文与块使用 `text`、`blocks`，关系使用 `inputs`，人工证据使用 `targets`。同一条目的真实不同结果并列保存；没有文字或时间差异的导出副本不另建结果。保留局部、缺失、待复核及原时间状态。

<a id="导入双视频结果包"></a>

归档来源包属于来源证据。当前入口只接收原生实体记录或下述原生批次目录；已有记录中的包摘要、完整清单、成员校验、视频快照和上游运行身份仍保留原事实。历史包、收据与证据保留原字节，按当时版本解释，不使用新协议重放。

## 增量批次

本地 `verify`、`plan`、`apply`、接收凭证和 `validate-repository` 已实现；云端传输、生产端 outbox、受信 GitHub 接收工作流与自动 PR 尚未启用。自动生产端不写人工确认、片段归属或全文审核事实。

### 交接包与输入版本

交接包由 `manifest.json` 和清单列明的每记录 JSON 组成。当前 `contract_version=2`、`record_schema_version=3`、`kind=weimingzi_native_increment`；字段和容量见[批次协议](INCREMENTAL-INGEST-SPEC.md#批次协议)、[机器 Schema](contracts/ingest-batch-v2.schema.json)及[合成示例](examples/INGEST-EXAMPLES.md)。载荷是完整四实体原生记录，路径为 `records/{entity}/{id}.json`。

清单绑定目标、来源范围、生产程序与代码版本、运行、创建时间、`base_commit`、依赖、来源快照、文件清单和操作。每条操作固定 `op`、`entity`、`record_id`、`path`、`payload_sha256`、`expected_record_sha256`、`source_refs`；`insert` 的预期摘要为 null，`replace` 为现有完整原生记录摘要。文件清单另校验实际字节数和字节 SHA-256。

批次身份由移除自身字段后的规范清单计算，传输信息放包外。封包后清单、文件和操作固定；重投原包不改时间，改变记录或操作就生成新批次。越界、重复、未列明路径及协议外字段会失败，凭据不进入包。

包只需携带本次记录和对已有记录的引用；合并后的候选库必须满足完整引用及来源绑定。缺少某记录不表示删除，空数组不用于覆盖维护库。生产端按当前原生契约形成载荷，并固定自身可检出的代码与运行身份。

### 校验、规划与应用

规划与应用在 origin 指向目标仓库、工作区干净的专用 Git 检出目录执行。交接目录交给批次命令处理，不直接复制到维护数据。报告路径必须在检出目录外或忽略的 `.cache/`，且不能覆盖包内文件。

```sh
uv run python tools/corpus.py ingest verify /path/to/batch
uv run python tools/corpus.py --root /path/to/clean/checkout ingest plan /path/to/batch --report /tmp/ingest-plan.json
uv run python tools/corpus.py --root /path/to/clean/checkout ingest apply /path/to/batch --plan /tmp/ingest-plan.json
uv run python tools/corpus.py --root /path/to/clean/checkout ingest validate-repository
```

`verify` 只读检查清单、容量、文件摘要、来源范围和操作形状。`plan` 在隔离候选库应用全部操作，校验实体图、媒体定位和人工保护，再生成目录与接收凭证候选；不改维护数据。`plan_version=2` 报告绑定批次、目标 HEAD、全部输入字节、策略和内核，列出新增、替换、未变化、冲突与拟修改路径。检查报告后把同一报告交给 `apply`。

`apply` 取得 `.git/weimingzi-ingest-lock` 独占锁，重查包、HEAD、输入、策略、内核和计划。全部候选校验通过后先持久写入 `.git/weimingzi-ingest-incomplete.json`，再通过唯一安装 primitive 逐文件替换，读回全部摘要并确认 HEAD 未变才删除标记。`validate-repository` 检查当前协议收据及类型化媒体字段；本地应用成功不表示远端已接收。

### 候选结果与冲突

- `insert` 新增 ID；同 ID 同完整原生值则未变化，不同值为冲突。新增仍须通过外部身份、音频文件身份和重复结果检查。
- `replace` 提交完整候选记录，并以 `expected_record_sha256` 做 CAS。只有追加允许的观测、URLs、relations、members、downloads，或真实同文件音频从 unavailable 转为 available，才符合自动替换权限。已有正文、输入、时间、模型、质量、身份和已知哈希均保留。
- 文字修订另建文稿，保留原结果与真实来源链；人工证据按人工维护流程新增。自动生产端不授予确认静音、局部人工确认、人工派生稿或全文人工审核。

目标已等于期望后置状态时先判 `unchanged`，不因旧前置摘要制造冲突。一个冲突使整批在安装前失败，需拆分时由生产端重新封包。基线移动或策略变化后重新规划，不自动选择冲突的一方。

有业务变化时生成 `ingest/receipts/<batch_id>.json`，版本为 `receipt_version=2`、`kind=weimingzi_native_receipt`。已有有效接收凭证返回 `status=replayed`，并用 `replay_status=accepted_state_present|accepted_state_changed` 区分历史接收状态是否仍在；变化列表保留接收与当前摘要，不改原凭证。无凭证且全部操作已满足时为 `already_present`，不制造空凭证；此状态不产生可供 `requires_batches` 使用的接收凭证。历史旧收据只作为不透明字节证据，不满足新批次依赖。

### 中断与重试

旧计划、工作区变化、未满足依赖或锁占用先排除原因，再重新规划。安装中断标记持续闭锁；进程、磁盘或读回故障后保留原包、报告和专用检出现场，从干净基线重建后重跑，不发布半批结果。逐文件替换不提供跨文件原子可见性，不能把“安装前整图校验”写成“多文件全有全无”。

损坏包、来源越界、身份歧义、CID 变化和内容冲突回生产端核对并重新封包。重试次数受限，失败响应不推进发现游标。完整退出码和恢复分类见[协议错误表](INCREMENTAL-INGEST-SPEC.md#错误分类与恢复)。

## 分阶段交付

动态、图文、文章正文准备好即可交付；新视频先交条目和来源，下载、ASR、AI 整理完成后继续提交关联产物。单个内容失败不阻塞其他已完成结果，每批仍须满足完整引用。依赖须有新协议有效接收凭证，开放 PR 不代表满足；冻结包不追加产物，后续进入新批次。

视频按平台视频及分 P 身份核对，媒体按文件 SHA-256 核对。Git 保存文字、结构化记录、清单和可验证定位，媒体字节使用外部存储或 Release。音频见[恢复契约](SCHEMA.md#工件恢复位置与哈希)和[保存流程](PRESERVATION.md#音频恢复)；视频及图片观测见[媒体 Schema](contracts/ingest-media-asset-v2.schema.json)。临时播放地址不算完成归档。

字幕、真实音频 ASR 与 AI 整理分别保存，不以字幕成功代替要求的音频 ASR。AI 结果保留模型、输入、完整性与待复核状态；原时间异常仍由导出按原值检查。

## 发布与回执

外部发布与自动 PR 仍为设计，详见[GitHub 接收、PR 与重放](INCREMENTAL-INGEST-SPEC.md#github-接收pr-与重放)。发布任务负责网络、对象存储及 GitHub 访问；本地内核只处理文件。

设计要求每批有可追踪的分支和 PR，重复投递先对账；串行发布，其余 ready 批次保留在持久 outbox。PR 展示来源、各实体变化、冲突、媒体定位、ASR/AI 状态及检查结果；只发布批准的数据、生成目录和凭证。发布前运行维护检查、复查远端基线与机器人分支；并发变化重新规划，维护者改动须保留。

外部回执分别记录 `planned`、`pr_open`、`merged`、`rejected`、`failed` 及实际 PR、提交和记录身份。远端合并及目标分支中的凭证或结果才证明接收；事件送达或工作流成功不替代它。发现、任务持久化、处理和仓库接收分别记账；上线前须以合成批次验证完整链路，历史探测不是上线证据。

## 查询与导出入口

找正文、关联、专题及派生导出见[查询与导出](QUERY.md)：[找稿与关联](QUERY.md#找稿与关联)、[专题查询](QUERY.md#专题查询)、[导出正文与标注](QUERY.md#导出正文与标注)、[全文检索](QUERY.md#全文检索)。块级标注、附注和独立稿见[查看校对标注](QUERY.md#查看校对标注)。

专题是可选查询配置；基础校验、记录导入及批次入库不加载专题规则，显式专题查询、`generate` 与全仓检查才核对已有规则。

## 人工确认与局部修订

复核时结合精确块文字、输入快照、标签、时间和完整参照稿。保留原标注，另建有依据、有适用范围的确认；不把 AI 候选升级为人工术语释义。字段见[人工证据](SCHEMA.md#人工证据与模型标注)。

在 `data/annotations.jsonl` 新增 `kind=confirmation`，保留原文、修订文字、各自哈希、范围和核对依据。`targets` 用 `item` 指条目，`applies_to` 指适用文稿，`revision` 指有 `derived_from` 且实际采用修订的文稿。只有 `revision` 带 `order`，同一文稿内唯一连续且从零开始；文稿不新增反向确认列表。

适用不证明采用，采用不证明全文审核。只确认实际审核的字句或术语，保留全文原质量状态。真实文字修订另建整理稿并保留原稿、历史输入、模型和局部证据；不随上游更新重写快照。

## 片段归属

审核者看过原视频或听过音频并给出结论后，新增 `kind=segment_attribution`。`targets` 指向条目和一个适用整理稿；`anchor.paragraph_index` 原生地指该文稿 `blocks` 位置。每条针对一个块或块内一句：用 `block_text` 还原精确文字并计算 UTF-8 SHA-256，复制对应 `start`、`end` 和文稿 `time_unit`，`review.basis` 保留原话。枚举及锚点见[片段说话人与观点归属](SCHEMA.md#片段说话人与观点归属)。

审核后仍不明写 `unknown`，与没有审核记录分开；模型建议不写成人工归属。文字改变后重新审核另建证据，不直接刷新旧哈希。文字确认与说话人、观点归属分别核对，未覆盖块保持未审核。写入后执行维护检查。

## 维护后检查

完成数据或证据修改后运行：

```sh
uv run python tools/corpus.py validate
uv run python tools/corpus.py generate
uv run python tools/check_repository.py
uv run python -m unittest discover -s tests -v
```

`generate` 重建 [内容目录](INDEX.md)、[分类目录](catalog/)和 [counts.json](counts.json)，不手改生成文件；CI 检查它们与数据一致。全仓检查核对文档链接及章节锚点、接收凭证、媒体字段和已有专题配置。交付时列明本次实际检查与未覆盖项，历史测试数不作为本次验证。

保存范围或支持文件变化时，按[基线与事件链](PRESERVATION.md#基线与事件链)另建并核对基线。历史提交、收据、清单与冻结工件保留原字节；当前原生整理见[实施记录](NATIVE-V3-CLEANUP.md)及[逐条证据](evidence/native-v3-cleanup-2026-11-17.json.gz)。维护数据有效性不替代远端媒体可达性，后者按[周期审计](PRESERVATION.md#周期审计)执行。
