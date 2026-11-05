# 保存运行与交接

## 周期检查

[Preservation audit 工作流](../.github/workflows/preservation-audit.yml)每周一 01:00 UTC（香港时间 09:00）检出默认分支，核对当前基线和事件链。
它使用只读权限，不自动提交日志、改写基线或修复文件。也可从 Actions 页面手动触发；首次计划触发日期为 2026-11-09，实际执行以 Actions 记录为准。

每次运行保存 run.json、fixity.json 和 event-chain.json，记录提交、触发方式、运行标识、逐文件差异及日志链结果。工作流中的保留期为 90 天；检查失败时也尝试上传已有报告。Actions 运行结果与归档日志分别保存。

在仓库根目录手动触发并取回报告：

    gh workflow run preservation-audit.yml --ref main
    gh run list --workflow preservation-audit.yml --limit 5
    gh run view RUN_ID --exit-status
    gh run download RUN_ID --dir .cache/audit-RUN_ID

RUN_ID 替换为实际运行标识。取回后核对 run.json 的提交与预期版本，再检查两份结果的通过状态、差异和事件链末条摘要。失败任务的日志通过 `gh run view RUN_ID --log-failed` 查看。需要长期保留的运行结果，应在过期前导出到获准的位置；Actions artifact 不作为独立保存副本。

## 失败处置

| 现象 | 处理 |
| --- | --- |
| 文件新增、缺失或变化 | 保留报告，对照获准提交调查 |
| 选择器或清单不可读 | 核对版本历史与摘要，保留损坏字节 |
| 日志链失败 | 停止追加，调查第一条失配记录 |
| 工作流未触发或启动失败 | 检查 Actions 开关、计划记录及权限 |
| artifact 缺失 | 保留任务日志，重新执行只读检查 |
| 恢复哈希失败 | 保留失败输入和结果，不覆盖已有文件 |

文件差异只有在确认对应改动获准后才能成为新基线。先运行数据和工具校验，再另建版本化清单、选择新基线、追加检查事件，最后提交这些变更。旧清单和失败事件保持原样。不要通过排序时间戳、截断记录、替换来源或删除失败事件消除错误。

本地需要留痕时运行 `tools/preservation_check.ps1`，或执行保存说明中的 `check-current` 与 `verify-log`。调查期间的重复查看用 `check-current --read-only`；它不会向日志追加事件。

## 恢复与回读

从记录的发布定位下载媒体，先核对归档摘要，再核对成员集合、大小、哈希及恢复路径。恢复工具和实际单卷证据见[保存说明](PRESERVATION.md)。全部音频仍需逐卷读取和记录；索引中的可恢复定位不等同于字节已经核验。

仓库内容可从获准 Git 提交重新检出，使用该提交自己的当前基线核验。SQLite、导航和其他导出由维护数据重建；不把缓存或导出反向当作维护数据。恢复到新位置后再次核对文件字节和事件链。

## 全量媒体审计

[Media restore audit 工作流](../.github/workflows/media-restore-audit.yml)在临时运行环境逐卷下载、恢复和核对哈希。每卷核对后释放其临时目录，保留逐项报告；不会把这些临时字节计为长期副本。工作流可手动执行，修改审计实现的 PR 也会触发验收。

    gh workflow run media-restore-audit.yml --ref main
    gh run list --workflow media-restore-audit.yml --limit 5
    gh run download RUN_ID --dir .cache/media-audit-RUN_ID

本地也可使用同一入口，OUTPUT 必须是 preservation/checks/ 下尚未使用的 JSON 路径：

    python tools/audit_audio_restore.py --temporary-media --workers 1 --output OUTPUT

临时模式只允许单个工作线程。未指定 `--temporary-media` 时，恢复字节留在本地缓存和 media/audio/；可使用 `--archive release-tag/archive.zip` 限定范围。已有报告不会覆盖；重试时换用新路径，并保留原失败结果。

最终 report.json 包含输入索引摘要、工具摘要、选择范围、归档、成员及恢复文件结果。每卷完成时另写一份不可覆盖的 .parts/ 检查点；任务中断时这些记录只证明已完成部分，不能替代最终报告。先核对输入索引与工具版本，再检查总报告的 ok、index_unchanged 及每个归档和文件的结果。

全量只涵盖音频索引中有恢复定位的记录，不包含缺失或未提供恢复来源的音频。一次回读通过也不证明未来可访问、内容准确、时间对齐或权利状态。

2026-11-05 的[全量报告](../preservation/checks/restore-full-2026-11-05.json)已经通过，并由[远端与发布验收记录](../preservation/checks/remote-validation-2026-11-05-v2.json)固定输入和运行结果。重试或新增媒体时建立新的版本化报告，保留已有结果。

## 责任与访问交接

| 事项 | 交接内容 | 当前状态 |
| --- | --- | --- |
| 维护负责人及替补 | 处理失败、批准修订、执行回读 | 待指定 |
| 仓库访问 | 管理权限持有人、恢复入口、替补接管 | 待确认交接记录 |
| Actions 处置 | 失败通知接收者、报告下载与保存 | 待指定 |
| 媒体访问 | 发布定位、哈希、访问异常处理 | 已有工具与单卷证据 |
| 第二副本 | 独立位置、权限、容量及费用边界 | 按当前决定暂缓 |

仓库只记录权限角色和恢复入口，不保存密码、令牌、会话或恢复码。负责人更换时，接收者应在自己的访问环境完成一次只读检查和一次媒体回读，并记录提交、输入、结果和差异；完成后再撤销离任者权限。现有权限可用不表示交接已完成。

## 保留与退出

版本化清单、校验事件和恢复证据随 Git 历史保留，本轮不清理旧版本。恢复缓存只有在报告已经保存、恢复定位仍可回查后才可清理；它不承担第二副本职责。涉及内容权利或删除请求时按[内容权利说明](../CONTENT-RIGHTS.md)处理，记录请求范围、处理依据和受影响版本，不静默删除历史证据。

停止维护前，交接维护数据、解释上下文、基线、事件和媒体恢复定位，列明未完成项及访问限制；接收者回读核验后记录接收范围。负责人、保留责任及退出接收方未明确前，[验收矩阵](ARCHIVE-ACCEPTANCE.md)中的维护交接保持待验收。
