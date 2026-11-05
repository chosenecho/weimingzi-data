# 资料库验收矩阵

本矩阵是本项目的交付门槛，用于区分本地工具能力与持续保存服务的运行证据。它不构成外部认证。每项验收都要保留输入、执行结果和证据位置；没有执行记录的操作保持待验收。

| 维度 | 验收条件 | 证据入口 | 当前状态 |
| --- | --- | --- | --- |
| 保存范围 | 维护数据、上下文与排除项明确 | 范围说明、文件清单 | 本地已实现 |
| 身份与来源 | 记录身份、来源、派生关系可回查 | 结构、质量、入库合同 | 本地已实现 |
| 权利与使用 | 许可边界、限制与处理入口明确 | 权利说明、问题模板 | 规则具备 |
| 入库与修订 | 哈希核对、冲突保留、接收回读 | 入库实现、回归测试 | 本地已实现 |
| 文件完整性 | 版本化清单、差异检查、失败留痕 | 基线、事件链、校验工具 | 本地已实现 |
| 版本留存 | 获准改动与校验记录进入版本历史 | Git 历史、发布记录 | 发布前核对 |
| 检索与引用 | 派生索引可重建、命中可回到原记录 | 代理指南、导出与检索 | 本地已实现 |
| 自动检查 | 全量检查及只读基线检查通过 | CI 配置、运行结果 | 配置已接入 |
| 定期运行 | 固定位置、周期执行、失败处置 | 周检脚本、系统任务历史 | 系统任务待注册 |
| 恢复能力 | 从保存字节恢复并核对哈希，记录抽样范围 | 恢复工具、演练证据 | 合成及真实单卷抽样通过 |
| 独立副本 | 独立故障域、权限明确、逐项回读 | 副本清单、回读记录 | 暂缓 |
| 维护交接 | 责任人、访问恢复、保留与退出流程 | 交接记录、操作说明 | 待确定 |

权利规则的存在不表示归档内容已获得统一再发布许可。来源字段、校对标注与模型结果的含义按记录本身及[内容权利说明](../CONTENT-RIGHTS.md)、[数据卡](DATA-CARD.md)解释。

“配置已接入”只指仓库中的工作流配置，远端 CI 的通过结果需以实际运行记录为准。真实恢复记录覆盖 2026-11-05 索引中 13 个分卷的 1 个、680 个音频的 6 个，不能扩大解释为全库或独立副本恢复通过。

## 证据入口

- 保存范围：[保存说明](PRESERVATION.md)、[基线目录](../preservation/manifests/)。
- 当前状态：[基线选择器](../preservation/current-baseline.json)、[校验事件](../preservation/checks/fixity.jsonl)。
- 记录与入库：[数据结构](SCHEMA.md)、[入库入口](INCREMENTAL-INGEST.md)。
- 协议附件：[协议设计](INCREMENTAL-INGEST-SPEC.md)、[合成示例](examples/INGEST-EXAMPLES.md)。
- 修订操作：[维护说明](MAINTENANCE.md)、[代理指南](AGENT-GUIDE.md)、[入库测试](../tests/test_ingest.py)。
- 使用限制：[内容权利说明](../CONTENT-RIGHTS.md)。
- 问题处理：[问题入口](../.github/ISSUE_TEMPLATE/archive-problem.yml)。
- 数据反馈：[修订入口](../.github/ISSUE_TEMPLATE/data-correction.yml)。
- 自动检查：[CI 配置](../.github/workflows/checks.yml)、[完整性工具](../tools/preservation_manifest.py)。
- 周期运行：[Windows 周检脚本](../tools/preservation_check.ps1)。
- 脚本验收：[失败路径测试](../tests/test_preservation_check.py)。
- 恢复操作：[下载说明](DOWNLOAD.md)、[恢复工具](../tools/restore_audio.py)。
- 恢复验收：[恢复测试](../tests/test_restore_audio.py)。
- 演练结果：[合成演练记录](../preservation/checks/restore-drill-2026-11-05.json)。
- 真实抽样：[单卷恢复记录](../preservation/checks/restore-release-sample-2026-11-05.json)。

## 本地验收

在仓库根目录运行以下命令，保存退出状态及输出。只读基线检查不追加事件，适用于 CI 和审计；操作性周检仍使用保存说明中的留痕入口。

    python tools/corpus.py validate
    python tools/corpus.py ingest validate-repository
    python tools/check_repository.py
    python -m unittest discover -s tests -v
    python tools/preservation_manifest.py check-current --read-only
    python tools/preservation_manifest.py verify-log
    git diff --check

Windows 脚本测试使用临时仓库，检查成功、资料变化、缺失基线、缺失选择器、日志损坏和缺少 Python 的退出状态。临时路径包含空格，调用目录与仓库目录不同；不修改正式语料。未安装 PowerShell 的环境会跳过该组测试，验收结果需保留跳过原因。

设计附件的独立检查命令见[合成示例](examples/INGEST-EXAMPLES.md)。该检查使用附加的 jsonschema 依赖，不改变核心工具仅依赖 Python 标准库的约定。

## 持续运行门槛

持续保存服务验收前，需要在长期固定的仓库路径注册周期任务，保留实际触发、成功与失败的运行记录，并确定处理失败的责任人。当前隔离工作树不作为长期任务目标。

真实媒体的验收需要实际读取归档字节，核对归档、成员和恢复结果的哈希。当前仅完成单卷抽样，全库验收还需覆盖其余分卷并保留逐项记录。第二保存副本按当前决定暂缓；该门槛不纳入已完成项。

维护交接还需记录保存范围、责任人及替补、凭据恢复方式、保留与删除规则、退出时的交接方式。凭据值不进入仓库，交接记录只保存权限与恢复入口。

阶段安排与依赖见[迭代计划](PRESERVATION-ROADMAP.md)。本地验收通过后，仍按上述门槛逐项保留运行证据。
