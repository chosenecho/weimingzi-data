# 保存范围与完整性基线

本文件定义仓库保存基线的第一阶段范围。完整性基线记录文件字节是否与基准时一致；它不证明来源真实、正文完整、内容权利状态已解决，也不证明远端副本仍可访问。

## 保存范围

| 类别 | 路径 | 处理 |
| --- | --- | --- |
| 权威维护数据 | data/**、selections/** | 纳入逐文件大小与 SHA-256 清单 |
| 解释与恢复上下文 | AGENTS.md、README.md、CONTENT-RIGHTS.md、维护说明、结构/术语/质量/下载说明、校验与恢复入口 | 纳入清单，确保数据可解释、可检查 |
| 入库与来源探测上下文 | 增量入库设计、批次 Schema/示例、入库实现与测试、Alibaba/Cloudflare 探测代码及验证记录 | 纳入清单；保存流程和来源探测证据，不把验证结果解释为采集完整性证明 |
| 仓库内 Markdown 导航 | 根目录、docs、functions、workers 等源码说明中的本地链接 | 仓库检查递归核对链接并跳过虚拟环境和构建缓存，避免只有 docs/ 内链接有效而源码操作说明断链 |
| 生成导航 | docs/INDEX.md、docs/catalog/**、docs/counts.json | 排除于权威数据清单；可从维护数据重建 |
| 本地缓存与导出 | .cache/**、SQLite、exports/** | 排除；属于派生工作数据 |
| 已恢复媒体 | media/audio/** | 不并入本清单；使用音频恢复工具按 data/audio.jsonl 的哈希单独核验 |
| 基线文件自身 | preservation/manifests/** | 不纳入自身清单；按独立版本化文件保存 |
| 当前基线选择器 | preservation/current-baseline.json | 单独版本控制；保存当前清单路径和摘要，避免循环哈希 |
| 校验事件日志 | preservation/checks/*.jsonl | 不纳入基线；按追加记录保留校验结果 |
| 恢复演练证据 | preservation/checks/restore-drill-2026-11-05.json、restore-release-sample-2026-11-05.json | 纳入支持上下文，分别保留合成样本与真实单卷抽样结果 |
| 远端发布包 | Release ZIP | 只有实际读取字节并验证归档与成员哈希后，才记录为当次已校验；URL 和索引状态本身不是可用性证明 |

清单将维护数据与解释上下文分别标记。范围扫描会逐项报告缺失目录、缺失上下文文件、重复路径、符号链接、不可读文件或非普通文件；`create` 遇到任一问题会以非零状态停止，不写出可被选中的不完整基线。保存计划、入库实现与其测试、探测配置及验证证据也列入解释上下文清单。检查不跟随符号链接。

## 建立与验证

在仓库根目录执行。BASELINE 替换为尚未使用的 `preservation/manifests/baseline-日期-v版本号.json` 路径：

    python tools/preservation_manifest.py create --output BASELINE
    python tools/preservation_manifest.py select-current --manifest BASELINE
    python tools/preservation_manifest.py check-current

`select-current` 只接受已存在、校验值有效且没有范围错误的版本化基线。它更新单独版本控制的当前基线选择器。`check-current` 读取选择器、校验所选清单并将结果追加到事件日志。

单次检查或核对指定历史基线时，可使用：

    python tools/preservation_manifest.py verify --manifest BASELINE --record
    python tools/preservation_manifest.py verify-log

不带路径的 `--record` 将通过、差异和无法读取基线等失败结果追加到 `preservation/checks/fixity.jsonl`。日志行包含 UTC 时间、基线摘要、文件差异以及前一条事件的 SHA-256，追加前会校验已有链并串行化写入。遇到不完整末行或链条校验失败时，下一次追加会停止并报错。发现文件差异时仍会写入失败事件，命令返回非零状态。`verify-log` 只读校验整条事件链并报告事件数与末条摘要。

## 定期运行

CI 和只读审计使用以下入口，核对当前选择器和文件字节而不追加事件。事件链仍需单独检查。

    python tools/preservation_manifest.py check-current --read-only
    python tools/preservation_manifest.py verify-log

Windows 脚本的成功和失败路径由 [test_preservation_check.py](../tests/test_preservation_check.py) 在临时仓库中执行验证，覆盖缺失基线、缺失选择器、文件变化、日志损坏和缺少 Python，并验证从其他目录调用及路径包含空格的情况。

建议每周运行一次，并在每次获准修改维护数据或支持文件后创建新基线。Windows 任务计划程序可调用 `tools/preservation_check.ps1`：程序设为 `powershell.exe`，参数为 `-NoProfile -ExecutionPolicy Bypass -File "<仓库根目录>\tools\preservation_check.ps1"`，起始位置设为仓库根目录；建议触发器为每周一上午 9:00（本机时区）。脚本检查当前基线并验证事件链；任一失败都会返回非零状态。事件 JSONL 保存逐文件差异，任务历史可用于发现运行失败。

如果检查失败，先查看 `preservation/checks/fixity.jsonl` 最后一行并调查差异。不要为了消除失败直接改写旧基线。确认改动获准后，创建新版本基线，再用 `select-current` 指向它。若日志链自身失败，先保留原日志并调查，不要追加覆盖。

周期检查采用[默认分支审计工作流](../.github/workflows/preservation-audit.yml)，每周一 01:00 UTC 执行并保留报告。Windows 脚本仍可用于本地留痕，本轮不注册指向临时工作树的系统任务。手动触发、报告回读和交接步骤见[运行说明](PRESERVATION-OPERATIONS.md)。实际触发和通过状态以远端运行记录为准。

恢复流程使用临时 ZIP 样本演练，不下载真实归档：

    python -m unittest tests.test_restore_audio -v

该测试在临时目录调用 `tools/restore_audio.py` 中的恢复逻辑，并核对恢复路径、成员集合、大小和哈希；也检查错误输入不会生成恢复目标、错误哈希不会覆盖已有文件。演练结果记录在 [restore-drill-2026-11-05.json](../preservation/checks/restore-drill-2026-11-05.json)。它验证的是本地恢复逻辑，不证明远端 Release ZIP 可读或真实语料已经恢复。

2026-11-05 的[真实单卷抽样记录](../preservation/checks/restore-release-sample-2026-11-05.json)另行读取了索引中最小的发布分卷。ZIP 为 134,967,542 字节，包含 6 个音频，共 134,966,536 字节；归档、ZIP 成员与恢复文件的大小和 SHA-256 均匹配。命令如下：

    python tools/restore_audio.py --archive missing-local-asr-2026-11-03/missing-local-audio-2026-11-03.zip
    python tools/restore_audio.py --archive missing-local-asr-2026-11-03/missing-local-audio-2026-11-03.zip --verify-only

这次抽样覆盖当时索引中 13 个可恢复分卷的 1 个、680 个音频的 6 个。抽样结果不等于全库恢复通过，也不构成独立保存副本；可重复检查使用相同入口，并保留新的时间、输入索引摘要和逐文件结果。

增量入库包的协议、路径和字节校验、冲突处理、候选安装及接收凭证由 `tests/test_ingest.py` 覆盖。运行 `python -m unittest discover -s tests -p test_ingest.py -v`；该测试使用临时目录和合成批次，不向远端投递或修改主语料。

每条文件记录包含仓库相对路径、类别、字节数和 SHA-256。清单记录创建时间、Git 提交、范围、排除项、汇总和自身校验值。验证会报告新增、缺失、变化或不可读取的路径；归档更新后应保留旧清单并为新的获准基线创建新文件，不应覆盖历史基线。

当前工具为路径列表和文件字节生成可重复排序的清单；生成时间和 Git 提交属于每次基线快照的上下文，故重新创建的新清单不会与旧清单逐字节相同。并发基线创建和当前选择器更新使用文件锁串行写入及唯一临时文件；已存在的基线不会被同名创建覆盖。清单自身的 manifest_sha256 仅用于发现清单意外损坏；它不是数字签名，不能单独防止攻击者同时改写文件和清单。基线应保存在受版本控制的历史记录中，并复制到独立保存位置。

事件链帮助发现链内的意外改写和不完整末行，不是数字签名。删去完整的末尾事件后，剩余链仍可能有效；能够整体改写仓库的人也能重建整条链。应把事件记录纳入版本历史或复制到独立保存位置，才能保留另一处证据。本地验证只证明当前检出文件与指定清单相符。第二保存副本、独立故障域、远端可用性和实际定期执行仍需分别建立与记录。媒体记录中 availability=available 仅代表存在恢复定位信息；只有下载并成功验证的文件才算完成实际恢复校验。

## 下一步门槛

各项能力及当前验收边界见[资料库验收矩阵](ARCHIVE-ACCEPTANCE.md)。

建立外部副本前，先确认保存范围、目标位置、责任人、访问控制、保留期和费用上限。最初的存储目标应与主仓库处于独立故障域。副本写入后需要回读，并对比本清单或单独的媒体清单；没有回读证据的复制任务不记为通过。

阶段顺序、验收条件和暂缓项见[保存能力迭代计划](PRESERVATION-ROADMAP.md)。
