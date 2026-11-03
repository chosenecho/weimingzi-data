# 离线分层语料与字段投影

本仓库拥有交付后的正文、用户资料、用户数据和用途标注。新入口不读生产 SQLite，不维护 asr-archive 的 publication 状态，不解析历史目录或旧稿件格式。

## 安装与一条完整路径

Python 3.12 标准库实现，安装仅注册命令，无模型和数据库依赖：

~~~sh
python -m pip install -e .
wm-corpus ingest --delivery /path/to/batch-001 --out ./snapshots/silver-001
wm-corpus verify --directory ./snapshots/silver-001
wm-corpus checkout --source ./snapshots/silver-001 --out ./working/editorial
~~~

编辑 working/editorial/records.jsonl，可修改正文、增加或删除非核心字段、追加训练标注和检索元数据。原件在 .base 中，工作副本使用普通复制，不用硬链接；不要编辑 .base 或已冻结目录。

checkout 还把 draft/review 与用户附件复制到可编辑 assets 目录。用户可以自由修改这些文件或新增资料，freeze 会一起保存，且不回写 Bronze。assets 只接受文件完整性检查，不沿用生产内容质检；正文投影以 records.jsonl 为准，不会擅自解析编辑过的 Markdown 来覆盖正文。需要同步正文时显式更新记录。

~~~sh
wm-corpus freeze --source ./working/editorial --out ./snapshots/silver-002
wm-corpus project --source ./snapshots/silver-002 --profile profiles/cpt.json --out ./gold/cpt-001
wm-corpus project --source ./snapshots/silver-002 --profile profiles/knowledge.json --out ./gold/kb-001
wm-corpus verify --directory ./gold/cpt-001
~~~

freeze 重算与父记录的差异，并由原件重建保管链，忽略用户手改的 _lineage。修改后的记录标记 downstream-edited，不能沿用生产回执作为修改后内容的质检结论。未改记录可保持原回执适用范围。原生产交付包无须变化或重审。

## 三层与字段

- Bronze：完整复制生产交付包，包括 ASR、AI 调用、draft/review、用户附件和原清单；逐文件身份保持一致。不能把没有保存的上游原始字段补成“原始数据”。
- Silver：稳定 record_id、text 与 source.platform/source_id/group_id 是通用最低要求。其余字段开放；_lineage 是本工具保管链保留字段。生产入口额外检查交付时的质量契约及时间轴，不推断语义或人工批准。
- Gold：用途 profile 定义输出字段到 Silver 点路径的映射、required 类型、defaults 与 filter。训练和知识库是并行投影；新用途只新建 profile，不强迫所有 Silver 记录迁就同一张宽表。

生产 passed 回执是生产时的保证。下游编辑后需按用途重新核查，例如 SFT 问答审核、知识库分块策略和资料公开策略。只要记录身份、来源和正文仍有效，Silver 不禁止用途字段变化，也不重新执行 ASR 的时间轴关口。

## 多批输入与独立用户内容

~~~sh
wm-corpus ingest --delivery /path/to/batch-002 --out ./snapshots/silver-batch-002
wm-corpus merge --source ./snapshots/silver-002 --source ./snapshots/silver-batch-002 --out ./snapshots/combined-001
wm-corpus import-local --records ./user-records.jsonl --out ./snapshots/user-content-001
wm-corpus merge --source ./snapshots/combined-001 --source ./snapshots/user-content-001 --out ./snapshots/all-001
~~~

同一 record_id 的完全相同记录可去重，不同版本直接报冲突，调用方需明确选择使用哪个快照。import-local 用于独立维护的动态、文章和用户内容，保留输入 JSONL 原字节；只需通用 record_id/text/source，不伪装通过生产质检。附加业务字段无需声明。新来源通过此入口进入，checkout 中不允许给未知新 record_id 借用旧回执。

## 自定义用途契约

~~~json
{
  "format": "weimingzi-projection/v1",
  "name": "arguments",
  "purpose": "research",
  "fields": {
    "id": "record_id",
    "body": "text",
    "argument": "annotations.argument"
  },
  "required": {"id": "string", "body": "string"},
  "defaults": {"argument": null},
  "filter": {"kind": ["editorial"]}
}
~~~

所有字段先映射、检查，再写新目录。缺失字段若没有 defaults 即失败；required 要求类型，字符串同时要求非空。默认值也接受同样检查。额外字段不会凭空进入 Gold，源字段保留在 Silver 与 Bronze。当前点路径只遍历对象，不执行表达式、不展开数组；复杂转换应作为用途代码单独实现并冻结结果。

Gold 包含 records.jsonl、逐行 lineage.jsonl、profile.json 与 manifest.json。lineage 记录 Silver 身份、来源分组、输出记录哈希与上游回执适用范围，不把检索字段塞进训练正文。profiles/cpt.json 输出 id/text/group_id，profiles/knowledge.json 输出 id/body/source/metadata/annotations。

## 不可变快照与迁移

每份快照是自足目录：文件大小与 SHA-256、规范 JSON 计算的 bundle_id、输入或父快照身份。新输出要求不存在，临时目录校验后安装；同名覆盖、路径穿越、符号链接、重复 JSON key 和文件篡改均拒绝。哈希检测损坏，不证明资料来源的真实性。

复制完整快照目录即可离线搬运，再 verify；移动不要求原磁盘路径。不可变是工具的拒绝覆盖约定，不是操作系统只读或对象锁。若手工修改已冻结文件，校验会失败；正确做法是 checkout 后 freeze。

快照保存全部 Bronze，会占用额外磁盘；没有硬链接或后台垃圾回收。先采用可检查的自足副本，后续数据量需要时再引入内容地址对象存储及保留策略，不用删除唯一恢复点来节约空间。

本机快照不能替代独立磁盘/远端备份。历史归档内容未被批量转换；新入口只接受声明的 v1 格式或显式本地输入，不承诺旧格式兼容。

## 验证

运行 python -m unittest discover -s tests -v。测试覆盖原件保留、开放字段、编辑后的回执范围、并行 Gold、映射预检失败、多输入、本地资料、篡改、覆盖和路径穿越。没有调用在线模型。
