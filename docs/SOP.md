# 未明子资料库首版交付操作规程（SOP）

**版本** v0.1 · **状态** 执行草案

本规程供维护者、盘点执行者和验收执行者使用，覆盖首版准备、盘点、回归、恢复、发布及运行交接。先完成 M1，再开展可并行的 M2 和 M3，两项交付齐备后进入 M4。发布验收与持续运行验收分别登记。需求和阶段交付以产品文档为准。[产品需求](PDR.md) · [开发计划](PDP.md)

## M1 确定版本、范围和样本

1. **维护者登记本轮执行人和候选版本。** 记录维护者、盘点执行者、验收执行者及计划日期。先查看当前工作区状态，再在独立目录检出获准的候选提交。下列命令在该检出目录的仓库根执行，第一条预期无输出。一般报告和派生输出放在忽略的 `.cache/` 或登记的外部位置。媒体审计报告按 M4 指定路径保存。

   ```sh
   git status --short
   git rev-parse HEAD
   uv --version
   uv sync --locked
   uv run python --version
   ```

2. **维护者准备验收输入。** 记录候选提交、对应基线路径及 `manifest_sha256`、操作系统、Python 与 uv 版本。事先取得指定版本的仓库、锁定环境和验收样本。准备后验证环境可启动。真实媒体回读安排在 M4，并提前确认可用磁盘和访问入口。[基线与事件链](PRESERVATION.md#基线与事件链)
3. **盘点执行者编制来源清单。** 从已有归档登记渠道、来源入口、时间窗、材料类型、盘点日期、证据位置和未核实范围。用一组同时涉及视频分 P、正文和媒体的样本试对账，记录平台标识、分 P、对应的库内 ID、匹配依据和统计单位。逐维度明确哪些条目适用、怎样判定已取得以及缺口如何记录。[数据结构](SCHEMA.md) · [PDR-05 收录盘点与缺口](PDR.md#pdr-05-收录盘点与缺口)

**完成条件** 候选版本和基线可定位，样本可按平台标识、分 P 或库内 ID 回查，各统计维度有明确口径。保存候选版本记录、来源清单初稿和样本对账结果，交给 M2 和 M3 的执行人。

## M2 盘点收录覆盖和缺口

1. **固定对账单位。** 按来源清单逐条匹配，以条目或分 P 为统计单位。有多份文稿时，保留各原生记录 ID，汇总时按该单位计数。分 P 的基础转录和整理稿以直接关联为依据，其他来源文稿可作为补充证据另记。[找稿与关联](QUERY.md#找稿与关联)
2. **记录逐项状态。** 分别检查元数据、基础转录、整理稿、媒体和人工复核。明细按渠道、来源标识、分 P 和维度记录适用性、状态、库内 ID 及证据位置。每个适用维度选填已有、部分取得、缺失或未知。不适用项注明依据并从该维度分母排除。确认未收录记为缺失，状态待核实记为未知。人工复核分别记录局部证据和全文复核状态。媒体同时记录恢复定位，由 M4 回填字节核验结果与报告位置。[资料质量状态](DATA-CARD.md) · [音频恢复](PRESERVATION.md#音频恢复)
3. **复算汇总并登记缺口。** 按渠道、材料类型和维度核对适用总数等于四种状态之和。覆盖率注明分子口径，适用总数为零时记为不适用。来源尚未盘清时，分母只取已识别的适用条目或分 P，并列出未核实的来源范围。逐项记录缺口、证据、负责人和处理顺序，区分影响验收的问题和后续补档事项。

**完成条件** 交付带日期的来源清单、可从明细复算的覆盖报告及可定位记录的缺口清单。交验时标明对应提交和盘点口径版本。

## M3 验收本地使用与维护

验收执行者先固定样本 ID、查询条件、预期结果和证据路径。维护者处理缺陷，修复后登记候选版本变更和复验范围。以下命令中的 `RECORD_ID`、`ITEM_ID`、`SOURCE_ID`、`BATCH_DIR` 等大写值按所在步骤替换。示例输出目录 `.cache/sop/` 用于本轮新建的工作目录。

### 独立读取、重建和引用（PDR-01、PDR-02）

1. 用 M1 准备好的环境在干净检出目录断开网络。执行资料校验、目录生成、SQLite 导出和固定全文查询。`--offline --no-sync` 用于复用已准备的 uv 环境。

   ```sh
   uv run --offline --no-sync python tools/corpus.py validate
   uv run --offline --no-sync python tools/corpus.py generate
   uv run --offline --no-sync python tools/corpus.py generate --check
   uv run --offline --no-sync python tools/corpus.py export --format sqlite --output .cache/sop/corpus.sqlite3
   uv run --offline --no-sync python tools/corpus.py search 唯物主义 --database .cache/sop/corpus.sqlite3 --limit 20
   uv run --offline --no-sync python tools/corpus.py export --entity documents --id RECORD_ID --format jsonl --output .cache/sop/record.jsonl
   ```

2. 保存首次结果，将派生的 `corpus.sqlite3` 改名留存，再用原命令导出到原路径。以同一查询词和限制值重跑，核对两次命中的记录 ID 集合一致。核对 JSONL 与原生文稿对应，记录规模、环境、查询及重建耗时。[全文检索](QUERY.md#全文检索) · [导出正文与标注](QUERY.md#导出正文与标注)
3. 从条目 ID、精确平台标识、专题和正文四个入口找稿。用同一视频的两个分 P 核对 `direct` 与 `cross_source` 指向的实际文稿和关系依据。用候选版本中存在的样本替换下列参数。例如可先核对查询文档中的 `BV1CP4y1s7BM` 案例，再确定本轮预期结果。[回归案例](QUERY.md#回归案例)

   ```sh
   uv run --offline --no-sync python tools/corpus.py coverage ITEM_ID --include-records --output .cache/sop/item.json
   uv run --offline --no-sync python tools/corpus.py coverage SOURCE_ID --part 1 --include-records --output .cache/sop/part-1.json
   uv run --offline --no-sync python tools/corpus.py coverage SOURCE_ID --part 2 --include-records --output .cache/sop/part-2.json
   uv run --offline --no-sync python tools/corpus.py topic ismism --output .cache/sop/topic.json
   ```

4. 从一次命中回到原生维护文稿，按记录 ID、仓库相对路径和字段或块标出引用。复核完整上下文、来源、模型、质量，以及适用的原时间值和单位。记录一次无命中的查询条件、检索范围和可继续检查的原生记录入口。[数据结构](SCHEMA.md) · [全文检索范围](QUERY.md#全文检索)

### 批次入库演练（PDR-03）

1. 在独立、干净的演练检出目录准备合成批次。`origin` 和包的目标须符合固定策略，包的来源范围及 `base_commit` 要与演练输入对应。分别存放批次和报告，仓内示例用于参考封包格式。先跑入库回归，测试会构建临时演练库及合成批次，覆盖成功、重投和故障场景。[增量批次](MAINTENANCE.md#增量批次) · [合成示例](examples/INGEST-EXAMPLES.md) · [入库回归测试](../tests/test_ingest.py)

   ```sh
   uv run python -m unittest discover -s tests -p test_ingest.py -v
   ```

2. 使用与演练库匹配的合成包时，在该检出目录执行下列命令。先核对计划中的版本、目标 HEAD、操作与拟修改路径，确认计划通过后，应用时传入同一份报告。回读四实体变更和对应 `batch_id` 的接收凭证，登记前后摘要。

   ```sh
   uv run python tools/corpus.py ingest verify "BATCH_DIR"
   uv run python tools/corpus.py ingest plan "BATCH_DIR" --report .cache/sop/ingest-plan.json
   uv run python tools/corpus.py ingest apply "BATCH_DIR" --plan .cache/sop/ingest-plan.json
   uv run python tools/corpus.py ingest validate-repository
   ```

3. 将首次接收结果固定在演练库的提交中，保持检出干净。原包重投时用新报告重新规划并应用，预期得到 `status=replayed` 和 `replay_status=accepted_state_present`，首次凭证的字节保持一致。用独立夹具验证来源或摘要冲突、过期计划在安装前终止，并核对原资料摘要。用测试的故障注入验证写入中断后的闭锁和干净基线重跑。保留各场景的包、日志、计划及凭证，归档为演练证据。[候选结果与冲突](MAINTENANCE.md#候选结果与冲突) · [中断与重试](MAINTENANCE.md#中断与重试)

### 原文、人工证据与权利（PDR-04、PDR-07）

1. 抽一条有多份文稿及局部确认的条目。查原稿、历史输入快照和锚定文字，按 `inputs`、`targets` 及原生块定位核对确认适用稿和实际采用稿。另记全文人工复核字段及其原值。引用证据记录 ID、适用范围和定位。[人工确认](SCHEMA.md#人工确认) · [人工确认与局部修订](MAINTENANCE.md#人工确认与局部修订)
2. 用已有样本或字幕测试夹具读回异常原时间值，并尝试 SRT 或 VTT 导出。验收时核对导出返回非零退出状态、报出具体错误，且前后源记录摘要一致。再核对原时间值和正文仍可读。[正文导出与字幕要求](QUERY.md#导出正文与标注) · [字幕回归测试](../tests/test_corpus.py)
3. 导出一份含模型输出的文稿及一份含人工证据的文稿，连同其引用核对来源、模型、质量及证据适用范围。抽查 `null` 与 `false` 的显示或导出值，确认能区分未知与明确否定。检查交付说明可打开内容权利页。[数据卡](DATA-CARD.md) · [内容权利说明](../CONTENT-RIGHTS.md)

**完成条件** 提交样本清单、断网重建及查阅记录、批次规划与回执、异常场景和导出核对结果。按 PDR 编号逐项记录实测结论、证据路径及复测结果。

## M4 核验恢复并发布候选版本

1. **维护者固定交付版本。** 对齐 M2 覆盖报告、M3 验收记录和首版候选提交，登记对应基线路径及摘要。版本或范围有变时，先更新受影响的报告并重验。验收执行者从同一提交在新目录核对数据和支持文件，并按 M3 复核派生重建。[PDR-06 版本核验与恢复](PDR.md#pdr-06-版本核验与恢复)

   ```sh
   uv run python tools/preservation_manifest.py verify --manifest "BASELINE"
   uv run python tools/preservation_manifest.py check-current --read-only
   uv run python tools/preservation_manifest.py verify-log
   uv run python tools/corpus.py validate
   uv run python tools/corpus.py ingest validate-repository
   uv run python tools/corpus.py generate --check
   uv run python tools/check_repository.py
   uv run python -m unittest discover -s tests -v
   ```

   `BASELINE` 为登记的基线文件。核对候选版本当前选择器指向同一基线，并保存退出状态、差异和适用测试的跳过原因。若生成目录不一致，按维护流程在修订目录修复后重新固定候选版本。[本地验收](ARCHIVE-ACCEPTANCE.md#本地验收) · [维护后检查](MAINTENANCE.md#维护后检查)

2. **验收执行者回读音频。** 列出索引中可定位的分卷，对照发布准备声明后连接媒体来源。全量按下列命令执行，对声明只涵盖部分分卷的情形以可重复的 `--archive RELEASE_TAG/ARCHIVE.zip` 限定，保存实际选择范围。`REPORT_PATH` 置于 `preservation/checks/` 下，使用尚未占用的版本化 JSON 路径。

   ```sh
   uv run python tools/restore_audio.py --list
   uv run python tools/audit_audio_restore.py --temporary-media --workers 1 --output "REPORT_PATH"
   ```

   若私有 GitHub 仓库的附件直链返回 404，先用已登录且具备读取权限的 GitHub CLI 预取对应分卷。下例使用索引中的发布标签与附件名。先下载到临时文件并核对索引所记的 ZIP 字节数与 SHA-256，再放入 `.cache/media/RELEASE_TAG/ARCHIVE.zip`。审计时去掉 `--temporary-media`，使工具使用候选目录的预取缓存。普通模式会保留 ZIP 和恢复文件，运行前确认磁盘空间；它不构成独立保存副本。

   ```sh
   gh release download "RELEASE_TAG" --repo OWNER/REPO --pattern "ARCHIVE.zip" --output "ARCHIVE.zip.prefetch"
   ```

   核对报告的索引及工具摘要、选择范围、`ok`、`index_unchanged`、`index_dependencies_unchanged`，逐卷检查 ZIP、成员、恢复文件的大小及 SHA-256。按本轮逐项通过结果，以与 M2 一致的单位回填实际字节核验数量。从历史报告引用的结果注明原提交和范围。中断时留存检查点和日志，以新路径重跑并分别记录已核验、失败和未执行范围。[全量媒体审计](PRESERVATION.md#全量媒体审计)

3. **维护者核对发布门槛。** 逐项复核 PDR-01 至 PDR-07 的适用性和结果。适用项失败或待验证时，在验收记录中标明并继续复验。发布说明附候选版本、基线、收录范围和缺口、实际核验媒体范围、未满足要求、证据位置及内容权利入口。记录查询、重建和恢复的规模、环境及耗时。媒体验收沿用现有音频恢复链。[PDR 发布条件](PDR.md#5-发布与持续运行) · [资料库验收矩阵](ARCHIVE-ACCEPTANCE.md) · [内容权利说明](../CONTENT-RIGHTS.md)
4. **维护者发布并回读。** 全部适用项通过后，登记发布标识、对应提交及基线。逐项回读发布说明和已交付文件，核对可取得的版本与所验版本一致。保留发布位置、回读结果和报告位置。

## 持续运行与交接

1. **维护者登记责任与访问入口。** 指定负责人、替补和接手者，记录本地周检失败处置人、媒体异常处置人、访问角色及恢复入口。凭据由项目使用的访问管理渠道保管。[责任与访问](PRESERVATION.md#责任与访问)
2. **负责人执行并回读本地周检。** 先在固定维护检出手动运行并登记结果。取得实际计划触发的结果后，把任务历史与同次运行的完整性事件对应，核对检出版本、触发时间、基线摘要、退出状态和事件链末条摘要。[周期审计](PRESERVATION.md#周期审计)

   ```powershell
   uv run --offline --no-sync powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File tools/preservation_check.ps1
   ```

   任务计划程序中的登记示例：任务名 `weimingzi-preservation-weekly`，每周一 09:00 触发，程序为 `uv.exe`，参数为上例 `uv` 之后的全部内容，起始位置为维护检出根目录。用 `Get-ScheduledTaskInfo` 取实际运行时间和退出状态，与同次追加的完整性事件核对。

3. **接手者完成只读验证和媒体回读。** 用自己的访问环境在新目录检出登记版本，运行 M4 的基线及事件链检查，并按 M4 回读选定分卷。记录版本、输入、差异、结果、证据和接收人。负责人核对交接回执，通过后办理权限交接。档案恢复时间目标和可接受的数据回退窗口按实际运行结果另定。[持续运行门槛](ARCHIVE-ACCEPTANCE.md#持续运行门槛) · [责任交接与保留退出](PRESERVATION.md#责任交接与保留退出)

## 异常处置与记录

| 情况 | 处置和复验起点 |
| --- | --- |
| 来源或摘要冲突 | 保留原包和报告，回生产端核对。包内容或操作有变时重新封包，从 `verify` 开始。 |
| 计划过期或锁被占用 | 保存现场，确认候选 HEAD、输入及运行状态。排除原因后生成新计划。 |
| 安装中断或读回失败 | 保留批次、日志、报告及闭锁现场，由维护者从干净基线重建演练库后重跑。 |
| 基线差异 | 保存差异报告。查明获准的范围变化后，另建并核验基线。 |
| 事件链异常 | 保留原始日志，停止追加并核查首个失配点。 |
| 媒体哈希失败或回读中断 | 保留报告和检查点。核对失败卷、成员及来源版本后，用新报告路径复验。 |
| 本地周检未触发 | 核查调度器、运行账户、检出路径和任务历史。 |
| 本地周检结果缺失 | 保存任务历史，补作只读检查并登记。 |

进一步处置按仓库现有流程执行。[入库错误分类](INCREMENTAL-INGEST-SPEC.md#错误分类与恢复) · [保存失败处置](PRESERVATION.md#失败处置与恢复)

每轮可复制以下记录骨架。范围或统计口径有变化时同步更新来源清单、覆盖报告和发布说明。证据应留在获准的位置，并能凭版本和路径取回。

```text
阶段 / PDR 编号
执行人 / 复核人 / 执行日期
候选提交 / 基线路径及摘要 / 盘点口径版本
输入样本、范围及环境
预期结果 / 实测结果 / 耗时及规模
状态（待执行、通过、失败、待复验、不适用）及依据
证据路径 / 交付物路径
未覆盖范围 / 受影响版本 / 复验结果
```
