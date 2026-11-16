# 资料库验收矩阵

本矩阵保留保存能力的验收条件与历史执行证据，不构成外部认证。下表运行状态对应所链接的 2026-11-05 验收记录，不代表后续提交已通过远端检查。每项验收保留输入、执行结果和证据位置；新提交按[维护后检查](MAINTENANCE.md#维护后检查)重新运行适用检查。文档合并和命令更新不改变历史结论或未完成门槛。

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
| 定期运行 | 默认分支周期执行、失败处置 | [周期审计](PRESERVATION.md#周期审计)、运行报告 | 手动通过；首次计划待验收 |
| 恢复能力 | 恢复字节、核对哈希并记录范围 | [音频恢复](PRESERVATION.md#音频恢复)、[逐项报告](../preservation/checks/restore-full-2026-11-05.json) | 当时有恢复定位的音频全量通过 |
| 独立副本 | 独立故障域、权限明确、逐项回读 | 副本清单、回读记录 | 暂缓 |
| 维护交接 | 责任人、访问恢复、保留与退出流程 | [交接说明](PRESERVATION.md#责任交接与保留退出)、接收记录 | 说明具备；人员待确定 |

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
- 周期运行：[审计工作流](../.github/workflows/preservation-audit.yml)、[周期审计操作](PRESERVATION.md#周期审计)。
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

## 本地验收

在仓库根目录运行以下命令，保存退出状态及输出。只读基线检查不追加事件，适用于 CI 和审计；操作性周检使用[保存说明的留痕入口](PRESERVATION.md#基线与事件链)。

```sh
uv sync --locked
uv run python tools/corpus.py validate
uv run python tools/corpus.py ingest validate-repository
uv run python tools/corpus.py generate --check
uv run python tools/check_repository.py
uv run python -m unittest discover -s tests -v
uv run python tools/preservation_manifest.py check-current --read-only
uv run python tools/preservation_manifest.py verify-log
git -c core.whitespace=cr-at-eol diff --check
```

获准修改导致生成目录过期时，按[维护说明](MAINTENANCE.md#维护后检查)重新生成后再验收；不要手改生成目录。除文件存在性，还要核对新链接的章节锚点。支持文件或保存范围改变时，完成校验后按[建立与验证](PRESERVATION.md#建立与验证)另建并选择新基线，保留旧清单、事件和历史证据。

Windows 脚本测试使用临时仓库，检查成功、资料变化、缺失基线、缺失选择器、日志损坏及缺少 Python 的退出状态。临时路径包含空格，调用目录与仓库目录不同，不修改正式语料。未安装 PowerShell 的环境会跳过该组测试，验收结果需保留跳过原因。

协议附件的独立检查命令见[合成示例](examples/INGEST-EXAMPLES.md)。该检查使用附加的 jsonschema 依赖，不改变核心工具只依赖 Python 标准库的约定。

## 持续运行门槛

持续保存服务验收前，需要保留周期工作流的手动验收及实际计划触发记录，并确定处理失败的责任人。工作流每次检出默认分支，不依赖当前隔离工作树；手动通过不能替代首次计划触发证据。历史计划首次触发日期为 2026-11-09，仅凭该日期已经过去，不把待验收项改为完成。

2026-11-05 的真实媒体验收实际读取了当时有恢复定位的全部分卷，并核对归档、成员和恢复结果的哈希。今后索引增加或修订时仍需重新验收；缺少恢复定位的音频不在这次通过范围内。第二保存副本按当前决定暂缓，该门槛不纳入已完成项。

维护交接的保存范围、凭据处理、保留与删除规则及退出流程见[交接说明](PRESERVATION.md#责任交接与保留退出)。责任人及替补、访问恢复和接收记录仍需确定。凭据值不进入仓库，交接记录只保存权限与恢复入口。

阶段安排与依赖见[历史迭代记录](PRESERVATION-ROADMAP.md)。本地验收通过后，仍按上述门槛逐项保留运行证据。
