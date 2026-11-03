# AI 与自动化使用指南

需要 Python 3.12；在仓库根目录安装后，输入和输出可以放在任意磁盘位置。优先传绝对路径，避免推断历史中文目录或原机器盘符。

~~~sh
python -m pip install -e .
wm-corpus --help
wm-corpus ingest --delivery /path/to/delivery --out /data/snapshots/silver-001
wm-corpus verify --directory /data/snapshots/silver-001
wm-corpus checkout --source /data/snapshots/silver-001 --out /data/working/edit-001
~~~

根据用户要求编辑工作副本 records.jsonl，保留 record_id、text 与 source 的稳定身份。用途字段可新增、删除或改名；不要改 .base、原交付包和已冻结目录。

draft/review 与用户附件的可编辑副本在 working 的 assets 中；修改后随 freeze 保存。它们不自动覆盖 records.jsonl，正文同步由编辑者明确处理，资产内容也不冒用生产质检标签。

~~~sh
wm-corpus freeze --source /data/working/edit-001 --out /data/snapshots/silver-002
wm-corpus project --source /data/snapshots/silver-002 --profile profiles/cpt.json --out /data/gold/cpt-001
wm-corpus project --source /data/snapshots/silver-002 --profile profiles/knowledge.json --out /data/gold/kb-001
wm-corpus verify --directory /data/gold/cpt-001
~~~

- 成功时 stdout 为单个 JSON 对象；失败说明写 stderr，操作失败退出 1，参数错误退出 2。解析 manifest 的 format、bundle_id、records_file、record_count，不靠目录名猜版本。
- 所有冻结输出必须是全新目录，不覆盖、不自动删除旧版本。发生中断先 verify 现有目标；完整目标可继续使用，不完整目标需保留证据并另选新目标。
- 原件保留在 Bronze。下游修改后的 quality=downstream-edited 不代表不可使用，而是上游质检回执不再适用于修改后的字节；不要把它改回 passed 来绕过用途审核。
- 用途字段由 profiles/*.json 映射。缺少字段或类型错误会在产出前失败；应修正 profile 或记录，不改生产契约。自定义 profile 再运行 project，可并行得到训练、知识库等不同字段形状。
- 多批快照用 merge --source 多次指定；同 ID 的不同记录会报冲突，应明确选版本。独立维护的文章、动态和用户数据用 import-local --records，不伪造生产回执。
- Gold 的 CPT 输出是候选，不是 SFT 批准；KB 不是默认训练输入。训练仓库消费完整 Gold 目录和 lineage，不能只复制正文后丢掉来源。
- 此工具不下载模型、不运行 ASR、不启动训练、不修改生产状态。完整使用与边界见 [CORPUS.md](CORPUS.md)。


返回[仓库首页](../README.md)。
