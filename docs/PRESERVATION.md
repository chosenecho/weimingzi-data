# 保存、恢复与运行交接

本页定义文件保存范围、完整性基线、音频恢复、周期审计及交接。完整性基线只记录文件字节是否与基准时一致，不证明来源真实、正文完整、内容权利状态已解决或远端副本仍可访问。能力与未完成门槛见[资料库验收矩阵](ARCHIVE-ACCEPTANCE.md)，历史阶段安排见[保存能力迭代记录](PRESERVATION-ROADMAP.md)。

当前命令在仓库根目录执行，首次使用先运行 `uv sync --locked`。下列日期与恢复数量属于所链接的历史证据；当前可恢复数量和字节数以生成的 [counts.json](counts.json)及 `--list` 输出为准，不在本页重复维护。

## 保存范围

| 类别 | 路径 | 处理 |
| --- | --- | --- |
| 归档数据与专题规则 | data/**、selections/** | 纳入逐文件大小与 SHA-256 清单 |
| 解释与恢复上下文 | AGENTS.md、README.md、CONTENT-RIGHTS.md、结构、维护、查询、质量与保存说明、校验及恢复入口 | 纳入清单，确保数据可解释、可检查 |
| 入库上下文 | 增量协议、批次 Schema/示例、入库实现与测试 | 纳入清单；范围以本仓当前维护文件为准 |
| 仓库内 Markdown 导航 | 根目录、docs 及源码说明中的本地链接 | 仓库检查递归核对链接，跳过虚拟环境和构建缓存 |
| 生成导航 | docs/INDEX.md、docs/catalog/**、docs/counts.json | 排除于权威数据清单，可从维护数据重建 |
| 本地缓存与导出 | .cache/**、SQLite、exports/** | 排除，属于派生工作数据 |
| 已恢复媒体 | media/audio/** | 不并入清单，按 data/assets.jsonl 中的字节哈希单独核验 |
| 基线文件自身 | preservation/manifests/** | 不纳入自身清单，作为独立版本化文件保存 |
| 当前基线选择器 | preservation/current-baseline.json | 单独版本控制，保存当前清单路径和摘要，避免循环哈希 |
| 校验事件日志 | preservation/checks/*.jsonl | 不纳入基线，按追加记录保留校验结果 |
| 恢复及发布证据 | preservation/checks/ 中明确列入 SUPPORT_FILES 的 JSON | 纳入支持上下文，保留合成、抽样、全量回读、中断及发布验收结果 |
| 远端发布包 | Release ZIP | 实际读取字节并验证归档与成员哈希后，才记录为当次已校验；URL 和索引状态不是可用性证明 |

`selections/` 当前只保存专题查询规则；支持文件清单只覆盖本仓维护职责。具体范围以[清单工具](../tools/preservation_manifest.py)的 `CANONICAL_ROOTS`、`SUPPORT_FILES` 为准，包含保存计划、入库实现与测试及仍由本仓维护的配置和验证证据。范围或职责变更后另建基线，旧清单与旧事件继续按原字节保留。

范围扫描将维护数据与解释上下文分别标记，逐项报告缺失目录、缺失上下文文件、重复路径、符号链接、不可读文件或非普通文件，不跟随符号链接。`create` 遇到任一范围问题会以非零状态停止，不写出可被选中的不完整基线。不要只检查 `docs/` 内导航而遗漏源码说明中的本地链接。

## 基线与事件链

### 建立与验证

完成适用的数据、工具及文档检查后，将 `BASELINE` 替换为尚未使用的 `preservation/manifests/baseline-日期-v版本号.json` 路径：

```sh
uv run python tools/preservation_manifest.py create --output BASELINE
uv run python tools/preservation_manifest.py select-current --manifest BASELINE
uv run python tools/preservation_manifest.py check-current
```

`select-current` 只接受已存在、校验值有效且没有范围错误的版本化基线，更新单独版本控制的选择器。`check-current` 读取选择器、核对所选清单，并将结果追加到事件日志。核对指定历史基线或单次记录时使用：

```sh
uv run python tools/preservation_manifest.py verify --manifest BASELINE --record
uv run python tools/preservation_manifest.py verify-log
```

每条文件记录包含仓库相对路径、类别、字节数和 SHA-256；清单还记录创建时间、Git 提交、范围、排除项、汇总及自身校验值。验证报告新增、缺失、变化或不可读取的路径。`git_commit` 是创建时已检出的 HEAD，可能早于随后收录清单的提交；实际字节以 `entries` 中的路径和摘要为准。[已发布快照](../preservation/checks/release-2026-11-05.json)另行固定标签、完整源提交和附件回读结果。后续证据使用新基线，不移动既有发布标签。

路径列表与文件字节按可重复顺序生成；创建时间和 Git 提交属于每次快照上下文，因此新清单不与旧清单逐字节相同。并发创建和选择器更新通过文件锁串行写入，使用唯一临时文件；同名创建不覆盖已存在的基线。

### 事件写入与证据边界

不带路径的 `--record` 将通过、差异及无法读取基线等失败结果追加到 `preservation/checks/fixity.jsonl`。每行包含 UTC 时间、基线摘要、文件差异和前一事件的 SHA-256；追加前校验已有链，并串行化写入。发现文件差异仍写入失败事件，命令返回非零状态。不完整末行或链校验失败会阻止后续追加。`verify-log` 只读校验整条链，报告事件数和末条摘要。

清单的 `manifest_sha256` 用于发现意外损坏，不是数字签名；它不能单独阻止文件与清单被同时改写。事件链也不是签名：删去完整末尾事件后，剩余链仍可能有效；能整体改写仓库的人也能重建整条链。基线与事件应进入版本历史，并复制到独立保存位置以保留另一处证据。

本地核验只证明当前检出文件与指定清单相符。第二副本、独立故障域、远端可用性与定期实际执行各自需要证据。`availability=available` 只代表存在恢复定位，只有下载并成功核验的文件才算完成实际恢复校验。

## 音频恢复

### 索引、下载与逐文件核验

v3 音频和 ZIP 归档资产统一维护在 [data/assets.jsonl](../data/assets.jsonl)，由 [data/schema.json](../data/schema.json)声明版本。音频下载项通过 `archive_id` 引用同一索引的归档资产；`sha256`、`size_bytes` 描述对应音频或 ZIP 的实际文件字节，不以结构化 JSON 摘要代替文件哈希。字段说明见[工件、恢复位置与哈希](SCHEMA.md#工件恢复位置与哈希)。

```sh
uv run python tools/restore_audio.py --list
uv run python tools/restore_audio.py
uv run python tools/restore_audio.py --verify-only
```

工具固定读取当前原生 `data/schema.json` 和 `data/assets.jsonl`，audio 的 `downloads[].archive_id` 直接解析同一索引的完整 archive 资产。恢复只依赖这两个文件，不依赖文稿、条目或人工标注的有效性；不接受自定义索引路径。

`--list` 列出可恢复文件总数、总字节数和分卷标识。按需将 `RELEASE_TAG/ARCHIVE.zip` 替换为其中的实际标识；`--archive` 可重复使用：

```sh
uv run python tools/restore_audio.py --archive RELEASE_TAG/ARCHIVE.zip
uv run python tools/restore_audio.py --archive RELEASE_TAG/ARCHIVE.zip --verify-only
```

ZIP 缓存于 `.cache/media/`，音频按哈希恢复到 `media/audio/`，两者不入库。工具依次核对 ZIP 字节数和 SHA-256、成员集合、成员大小、音频文件 SHA-256；已有正确文件直接复用。恢复路径可调整，但 `downloads[].member_path` 必须继续使用远端 ZIP 的原成员名，`release_tag` 保持原发布标识。

`availability=unavailable` 没有可用下载地址，工具会跳过；外部存储键只保留已知标识，不表示当前可下载。文本与音频可用状态独立：存在转录不表示仓库能恢复对应音频。

### 全量媒体审计

留存逐项恢复证据使用[媒体审计工具](../tools/audit_audio_restore.py)。本地命令中的 `OUTPUT` 必须是 `preservation/checks/` 下尚未使用的 JSON 路径：

```sh
uv run python tools/audit_audio_restore.py --temporary-media --workers 1 --output OUTPUT
```

临时模式逐卷恢复，核对后释放每卷临时目录，只允许 `--workers 1`。不指定 `--temporary-media` 时，恢复字节保留在本地缓存和 `media/audio/`；普通模式 `--workers` 接受 1 至 4，默认 2。可用可重复的 `--archive RELEASE_TAG/ARCHIVE.zip` 限定范围。已有报告及对应 `.parts/` 目录不覆盖；重试使用新路径并保留原失败结果。

最终报告包含实际读取 assets 索引的路径、字节数与 SHA-256、schema 依赖、原生读取/校验模块及恢复审计工具摘要、选择范围、逐归档、逐成员和逐恢复文件结果。音频及完整归档资产由同一 assets 文件字节摘要覆盖，各分卷报告保留相同依赖。先核对索引与工具版本，再检查总报告的 `ok`、`index_unchanged`、`index_dependencies_unchanged` 及各项结果；审计期间索引或 schema 依赖改变时，完整性检查失败，历史报告继续按原内容保留。

每卷完成后另写不可覆盖的 `.parts/` 检查点。中断时这些记录只证明已完成部分，不能替代最终报告。全量范围仅包含索引中有恢复定位的音频，不包含缺失或未提供恢复来源的音频；临时媒体不计为长期副本。一次回读通过也不证明未来可访问、内容准确、时间对齐或权利状态。

[Media restore audit 工作流](../.github/workflows/media-restore-audit.yml)使用同一临时入口，手动执行或在修改审计实现的 PR 中验收，每卷核对后释放临时媒体并保存逐项及中断报告：

```sh
gh workflow run media-restore-audit.yml --ref main
gh run list --workflow media-restore-audit.yml --limit 5
gh run download RUN_ID --dir .cache/media-audit-RUN_ID
```

`RUN_ID` 使用实际运行标识。索引新增或修订后建立新的版本化报告。

### 历史恢复证据与范围

- [合成演练记录](../preservation/checks/restore-drill-2026-11-05.json)：临时 ZIP 测试核对恢复路径、成员集合、大小与哈希，检查错误输入不生成恢复目标、错误哈希不覆盖已有文件。它只验证本地逻辑，不证明远端 ZIP 可读或真实语料已恢复。
- [2026-11-05 真实单卷抽样](../preservation/checks/restore-release-sample-2026-11-05.json)：读取当时索引中最小分卷 `missing-local-asr-2026-11-03/missing-local-audio-2026-11-03.zip`。ZIP 为 134,967,542 字节，6 个音频共 134,966,536 字节，归档、成员与恢复文件的大小及 SHA-256 均匹配。它只覆盖当时 13 个分卷中的 1 个、680 个音频中的 6 个，不等于全库通过，也不构成独立副本。
- [2026-11-05 真实全量报告](../preservation/checks/restore-full-2026-11-05.json)：临时环境逐卷读取当时有恢复定位的 13 个分卷、680 个音频，共 12,189,678,232 字节；归档、成员与恢复文件大小及 SHA-256 全匹配，每卷后释放临时媒体。
- [远端验收记录](../preservation/checks/remote-validation-2026-11-05-v2.json)固定执行提交、CI、周期审计和已回读 artifact ZIP 的摘要；[本地中断记录](../preservation/checks/restore-local-interrupted-2026-11-05.json)保留另一次未完成尝试，不据此判断来源不可用。

复现单卷检查可将上例 `--archive` 参数换为该抽样标识，分别恢复和 `--verify-only`；新检查保留新时间、输入索引摘要及逐文件结果。临时夹具测试使用：

```sh
uv run python -m unittest tests.test_restore_audio -v
uv run python -m unittest discover -s tests -p test_ingest.py -v
```

第一项不下载真实归档。第二项核对增量包协议、路径与字节、冲突处理、候选安装和接收凭证，使用临时目录及合成批次，不向远端投递或修改主语料。

## 周期审计

周期审计在维护机本地运行。用固定维护检出核对当前基线和事件链，保留启动时间、触发方式、检出版本、基线摘要、退出状态和结果。既有 GitHub Actions 记录按原样保留，首版以本地审计证据验收。

### 本地只读检查与留痕

调查或交接时可用只读入口核对基线及事件链。准备好锁定环境后，在仓库根目录运行：

```sh
uv run --offline --no-sync python tools/preservation_manifest.py check-current --read-only
uv run --offline --no-sync python tools/preservation_manifest.py verify-log
```

例行周检使用[基线与事件链](#基线与事件链)的留痕入口，在事件日志追加完整性检查结果，并回读事件链。Windows 可直接执行[周检脚本](../tools/preservation_check.ps1)：

```powershell
uv run --offline --no-sync powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File tools/preservation_check.ps1
```

使用 Windows 任务计划程序时，程序设为 `uv` 的实际可执行路径，参数沿用上例中 `uv` 之后的内容，起始位置设为稳定维护检出的仓库根目录。沿用每周一上午 9 点（香港时间）的计划。将任务历史中的实际触发时间和退出状态与同次运行产生的完整性事件对应保存，并回读事件链校验结果。手动运行单独登记。

[Windows 脚本测试](../tests/test_preservation_check.py)在临时仓库验证成功、缺失基线、缺失选择器、文件变化、日志损坏与缺少 Python，并验证从其他目录调用及路径包含空格的情况。

## 失败处置与恢复

| 现象 | 处理 |
| --- | --- |
| 文件新增、缺失或变化 | 保留报告，对照获准提交调查；查看事件日志末行 |
| 选择器或清单不可读 | 核对版本历史与摘要，保留损坏字节 |
| 日志链失败或末行不完整 | 停止追加，保留原日志，调查第一条失配记录，不追加覆盖 |
| 本地周检未触发或启动失败 | 检查任务历史、运行账户、维护检出和 uv 路径 |
| 本地周检结果缺失 | 保留任务历史，补作只读检查并登记 |
| 恢复哈希失败 | 保留失败输入与结果，不覆盖已有文件 |
| 媒体审计中断 | 保存已产生的检查点及日志，明确已完成范围，以新报告路径重试 |

文件差异只有在确认对应改动获准后才能成为新基线。先完成[维护后检查](MAINTENANCE.md#维护后检查)，再另建版本化清单、选择新基线、追加检查事件，最后将获准变更及记录纳入版本历史。旧清单与失败事件保持原样；不通过排序时间戳、截断记录、替换来源、删除失败事件或改写旧基线消除错误。

仓库内容从获准 Git 提交重新检出，使用该提交自己的当前基线核验。SQLite、导航及其他导出由维护数据重建，不把缓存或导出反向当作维护数据。媒体按记录的发布定位恢复，先核对归档摘要，再核对成员集合、大小、哈希和恢复路径；恢复到新位置后再次核对文件字节和事件链。恢复定位本身不等于字节已核验。

## 责任交接与保留退出

### 责任与访问

| 事项 | 交接内容 | 当前状态 |
| --- | --- | --- |
| 维护负责人及替补 | 处理失败、批准修订、执行回读 | [首版负责人已登记](evidence/first-release-2026-11-18.md)，替补待指定 |
| 仓库访问 | 管理权限持有人、恢复入口、替补接管 | 待确认交接记录 |
| 本地周检处置 | 检查任务结果、保存记录、处理异常 | 由首版负责人负责 |
| 媒体访问 | 发布定位、哈希、访问异常处理 | 已有工具与历史回读证据，见音频恢复章节 |
| 第二副本 | 独立位置、权限、容量及费用边界 | 按当前决定暂缓 |

仓库只记录权限角色和恢复入口，不保存密码、令牌、会话或恢复码。负责人更换时，接收者在自己的访问环境完成一次只读检查和一次媒体回读，记录提交、输入、结果及差异，完成后再撤销离任者权限。现有权限可用不表示交接已完成。

建立外部副本前，先确认保存范围、目标位置、责任人、访问控制、保留期及费用上限；最初存储目标应与主仓库处于独立故障域。写入后必须回读，对比本清单或独立媒体清单，没有回读证据的复制不记为通过。

### 保留与退出

版本化清单、校验事件和恢复证据随 Git 历史保留，本轮不清理旧版本。缓存只有在报告已保存、恢复定位仍可回查后才可清理，且不承担第二副本职责。内容权利或删除请求按[内容权利说明](../CONTENT-RIGHTS.md)处理，记录请求范围、处理依据及受影响版本，不静默删除历史证据。

停止维护前交接维护数据、解释上下文、基线、事件与媒体恢复定位，列明未完成项及访问限制；接收者回读核验后记录接收范围。负责人、保留责任及退出接收方未明确前，[验收矩阵](ARCHIVE-ACCEPTANCE.md#持续运行门槛)中的维护交接继续待验收。
