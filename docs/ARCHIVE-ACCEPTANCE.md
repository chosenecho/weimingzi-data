# 资料库验收矩阵

后续版本从本页的[发布验收清单](#发布验收清单)核对候选与交付结果。首版的[产品需求](PDR.md)、[开发计划](PDP.md)、[交付规程](SOP.md)、[发布说明](releases/RELEASE-2026-11-18.md)与[验收记录](evidence/first-release-2026-11-18.md)供版本回查。周期审计与交接按[保存流程](PRESERVATION.md)执行。

## 发布验收清单

逐项记录适用性、预期与实测结果、执行日期和证据路径。适用项通过后发布；发布后登记回读结果。持续运行单独验收。产品验收条件见[产品需求](PDR.md#4-首版需求与验收)。

| 核对项 | 通过条件与应留证据 |
| --- | --- |
| 固定候选与基线 | 在干净检出中记录候选提交、基线路径和摘要、执行环境与样本。核验指定基线、当前选择器指向及事件链，保留退出状态和差异报告。见[基线与事件链](PRESERVATION.md#基线与事件链)及[本地验收](#本地验收)。 |
| 收录覆盖与缺口 | 按来源、时间窗和材料类型，以该版本识别的条目或分 P 对账。保留带日期的来源清单、可复算的五维汇总和可定位的缺口明细，注明分母、未知范围及部分取得情况。媒体恢复定位与本轮字节核验分别登记。见[收录盘点要求](PDR.md#pdr-05-收录盘点与缺口)及[首版覆盖示例](coverage/coverage-2026-11-18.md)。 |
| 断网重建与维护回归 | 用预取的锁定环境离线校验数据，重建目录和 SQLite，核对两次固定查询命中的记录 ID 集合及原生导出。保留样本、环境、规模、耗时和检查结果，并记录引用回查、入库重投与故障场景、质量和权利口径的抽查证据。见[全文检索](QUERY.md#全文检索)、[正文与标注导出](QUERY.md#导出正文与标注)、[增量批次](MAINTENANCE.md#增量批次)及[维护后检查](MAINTENANCE.md#维护后检查)。 |
| 媒体回读 | 对此次发布声明包含的音频，核对分卷、成员和恢复文件的字节数及 SHA-256。保留逐项报告、实际范围、失败和未执行项，按覆盖盘点的单位回填。历史结果注明原版本和范围。见[全量媒体审计](PRESERVATION.md#全量媒体审计)。 |
| 发布与回读 | 发布说明写明验收提交、基线、收录范围、实测恢复范围、已知缺口、未满足的要求及权利入口。发布后回读说明与交付文件，核对与所验版本一致，记录发布标识、位置和回读结果。见[发布条件](PDR.md#5-发布与持续运行)及[首版发布示例](releases/RELEASE-2026-11-18.md)。 |

## 保存能力与历史证据

下表保留保存能力的验收条件和证据。远端检查和媒体回读适用于报告所记的提交、基线及范围。四实体原生整理另见[实施记录](NATIVE-V3-CLEANUP.md)及[整理证据](evidence/native-v3-cleanup-2026-11-17.json.gz)。

| 维度 | 验收条件 | 证据入口 | 证据记录状态 |
| --- | --- | --- | --- |
| 保存范围 | 维护数据、上下文与排除项明确 | [保存范围](PRESERVATION.md#保存范围)、[文件清单](../preservation/manifests/) | 本地已实现 |
| 身份与来源 | 记录身份、来源、派生关系可回查 | [结构](SCHEMA.md)、[质量](DATA-CARD.md)、[入库协议](INCREMENTAL-INGEST-SPEC.md) | 本地已实现 |
| 权利与使用 | 许可边界、限制与处理入口明确 | [权利说明](../CONTENT-RIGHTS.md)、[问题模板](../.github/ISSUE_TEMPLATE/archive-problem.yml) | 规则具备 |
| 入库与修订 | 哈希核对、冲突保留、接收回读 | [维护操作](MAINTENANCE.md)、[回归测试](../tests/test_ingest.py) | 本地已实现 |
| 文件完整性 | 版本化清单、差异检查、失败留痕 | [基线与事件链](PRESERVATION.md#基线与事件链)、[校验工具](../tools/preservation_manifest.py) | 本地已实现 |
| 版本留存 | 获准改动与校验记录进入版本历史 | Git 历史、[发布及回读记录](../preservation/checks/release-2026-11-05.json) | 已合并并发布 |
| 检索与引用 | 派生索引可重建、命中可回到原记录 | [查询、导出与引用](QUERY.md) | 本地已实现 |
| 自动检查 | 全量检查及只读基线检查通过 | [CI 配置](../.github/workflows/checks.yml)、[远端验收记录](../preservation/checks/remote-validation-2026-11-05-v2.json) | 2026-11-05 远端通过 |
| 定期运行 | 维护机本地周检、失败处置 | [周期审计](PRESERVATION.md#周期审计)、运行报告 | 本地手动通过，首次计划待验收 |
| 恢复能力 | 恢复字节、核对哈希并记录范围 | [音频恢复](PRESERVATION.md#音频恢复)、[逐项报告](../preservation/checks/restore-full-2026-11-05.json) | 当时有恢复定位的音频全量通过 |
| 独立副本 | 独立故障域、权限明确、逐项回读 | 副本清单、回读记录 | 暂缓 |
| 维护交接 | 责任人、访问恢复、保留与退出流程 | [交接说明](PRESERVATION.md#责任交接与保留退出)、接收记录 | 首版负责人已登记，替补与接手者待指定 |

权利规则的存在不表示归档内容已获得统一再发布许可。来源字段、校对标注与模型结果的含义按记录本身及[内容权利说明](../CONTENT-RIGHTS.md)、[数据卡](DATA-CARD.md)解释。

Linux、Windows 和完整语料检查、合并后周期工作流的手动执行及报告回读，见[远端验收记录](../preservation/checks/remote-validation-2026-11-05-v2.json)。记录只适用于其中的提交与基线；后续提交仍需运行 CI。

[真实全量报告](../preservation/checks/restore-full-2026-11-05.json)覆盖当时索引中有恢复定位的 13 个分卷、680 个音频，共 12,189,678,232 字节。归档、ZIP 成员和恢复文件哈希全部匹配。它不涵盖缺少恢复定位的音频，也不构成独立副本恢复通过。

## 证据入口

- 保存范围：[保存说明](PRESERVATION.md#保存范围)、[基线目录](../preservation/manifests/)。
- 当前基线：[基线选择器](../preservation/current-baseline.json)、[校验事件](../preservation/checks/fixity.jsonl)。
- 记录与入库：[数据结构](SCHEMA.md)、[增量批次操作](MAINTENANCE.md#增量批次)。
- 协议附件：[增量协议](INCREMENTAL-INGEST-SPEC.md)、[合成示例](examples/INGEST-EXAMPLES.md)。
- 修订操作：[维护说明](MAINTENANCE.md)、[代理修改规则](../AGENTS.md)、[入库测试](../tests/test_ingest.py)。
- 检索与引用：[查询说明](QUERY.md)、[全文检索](QUERY.md#全文检索)。
- 使用限制：[内容权利说明](../CONTENT-RIGHTS.md)。
- 问题处理：[问题入口](../.github/ISSUE_TEMPLATE/archive-problem.yml)。
- 数据反馈：[修订入口](../.github/ISSUE_TEMPLATE/data-correction.yml)。
- 自动检查：[CI 配置](../.github/workflows/checks.yml)、[完整性工具](../tools/preservation_manifest.py)。
- 周期运行：[本地周期审计操作](PRESERVATION.md#周期审计)。
- 运行交接：[责任交接与保留退出](PRESERVATION.md#责任交接与保留退出)、[Windows 周检脚本](../tools/preservation_check.ps1)。
- 脚本验收：[失败路径测试](../tests/test_preservation_check.py)。
- 恢复操作：[音频恢复](PRESERVATION.md#音频恢复)、[恢复工具](../tools/restore_audio.py)。
- 恢复验收：[恢复测试](../tests/test_restore_audio.py)。
- 演练结果：[合成演练记录](../preservation/checks/restore-drill-2026-11-05.json)。
- 真实抽样：[单卷恢复记录](../preservation/checks/restore-release-sample-2026-11-05.json)。
- 本地中断：[未完成的全量尝试](../preservation/checks/restore-local-interrupted-2026-11-05.json)。
- 全量回读：[媒体审计工具](../tools/audit_audio_restore.py)、[远端工作流](../.github/workflows/media-restore-audit.yml)。
- 全量结果：[逐项恢复报告](../preservation/checks/restore-full-2026-11-05.json)。
- 发布验收：[标签及附件回读记录](../preservation/checks/release-2026-11-05.json)。

### 首版媒体统计勘误（2026-11-18）

[首版发布说明](releases/RELEASE-2026-11-18.md#已知限制)的媒体行混用了资产与盘点单位两种口径。按首版音频资产计，1,997 个中有 680 个具备恢复定位并完成字节核验，1,317 个在原生索引中标记为不可用。按覆盖盘点的媒体适用单位计，2,055 个中有 680 个完成字节核验，1,375 个没有恢复定位。其中 1,320 个分 P 共享上述 1,317 个不可用资产，另 55 条视频没有直接音频资产。详见[覆盖报告的媒体核验回填](coverage/coverage-2026-11-18.md#媒体核验回填)。

## 本地验收

在仓库根目录按[维护后检查](MAINTENANCE.md#维护后检查)运行固定候选的检查，按[保存流程](PRESERVATION.md#建立与验证)核对候选基线，并按[周期审计中的只读入口](PRESERVATION.md#周期审计)核对当前基线与事件链。保存退出状态、输出及适用测试的跳过原因。

获准修改导致生成目录过期时，按[维护说明](MAINTENANCE.md#维护后检查)重新生成后再验收；不要手改生成目录。除文件存在性，还要核对新链接的章节锚点。支持文件或保存范围改变时，完成校验后按[建立与验证](PRESERVATION.md#建立与验证)另建并选择新基线，保留旧清单、事件和历史证据。

Windows 脚本测试使用临时仓库，检查成功、资料变化、缺失基线、缺失选择器、日志损坏及缺少 Python 的退出状态。临时路径包含空格，调用目录与仓库目录不同，不修改正式语料。未安装 PowerShell 的环境会跳过该组测试，验收结果需保留跳过原因。

原生 Interface 验收另需核对四实体 kind、inputs/targets、精确块文字、快照、哈希和原工件字节，JSON/JSONL 导出须为原生记录，恢复只依赖 schema 与 assets。批次验收检查 contract 2/record 3、完整载荷 insert/replace、CAS 后置幂等、真实重放差异、锁和中断标记。单文件替换及回滚不记为多文件原子事务；历史旧收据保持不透明原字节，不用新协议重播。

协议附件的独立检查命令见[合成示例](examples/INGEST-EXAMPLES.md)。该检查使用附加的 jsonschema 依赖，不改变核心工具只依赖 Python 标准库的约定。

## 持续运行门槛

持续保存服务以维护机上固定检出的审计结果验收。负责人保存本地手动通过记录，以及至少一次实际按计划触发并通过的记录。计划证据包括任务历史、对应基线摘要、完整性检查事件和事件链校验结果。GitHub Actions 的旧运行保留为历史记录。

2026-11-05 的真实媒体验收实际读取了当时有恢复定位的全部分卷，并核对归档、成员和恢复结果的哈希。今后索引增加或修订时仍需重新验收；缺少恢复定位的音频不在这次通过范围内。第二保存副本按当前决定暂缓，该门槛不纳入已完成项。

维护交接的保存范围、凭据处理、保留与删除规则及退出流程见[交接说明](PRESERVATION.md#责任交接与保留退出)。首版负责人已登记。替补、接手者、访问恢复和接收记录仍需确定。凭据值不进入仓库，交接记录只保存权限与恢复入口。

阶段安排与依赖见[历史迭代记录](PRESERVATION-ROADMAP.md)。本地验收通过后，仍按上述门槛逐项保留运行证据。
