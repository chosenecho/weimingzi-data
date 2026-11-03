# 目录结构

## 以来源为存储边界

~~~text
weimingzi-data/
├── data/
│   ├── bilibili/<BV>/P001/
│   ├── youtube/<YouTube ID>/
│   ├── audio/<音频条目>/
│   └── user-content/
├── metadata/
│   ├── source-index.csv
│   ├── catalog.csv
│   ├── audio.csv
│   ├── source-labels.json
│   ├── training-source.json
│   ├── dataset-summary.json
│   ├── media/
│   ├── sources/
│   └── path-map.json
├── provenance/
├── docs/
├── src/weimingzi_corpus/
├── profiles/
├── tools/
├── tests/
└── projects/
~~~

`data/bilibili/` 按 BV、分 P 保存 B 站材料。`data/youtube/` 按 YouTube ID 独立保存音轨转录；与 BV 的关系登记在索引中，不以嵌套目录表达。`data/audio/` 保存用户补充音频的转录和来源记录，以音频 SHA-256 确定身份。现有章节目录名保留为阅读名称，改名不产生新身份。

每条来源内部保留原有版本：`原始转录/`、`AI校对/`、`已发布转录/`、来源响应及 README。并非每条都有全部产物，YouTube 与音频条目按已有材料保存。章节与主题可以在索引、标签或导出视图中组织，不复制正文建立多套主题目录。

`data/user-content/` 单独保存动态、文章、文集和合集快照，按自身清单解释路径。音频二进制通过 Release 与媒体清单恢复；Git 中的下载占位说明是导航。

## 统一来源标识

| 来源 | record_id | 存放位置 |
| --- | --- | --- |
| B 站分 P | `bilibili:<BV>:p<整数>` | `data/bilibili/<BV>/P<三位数>/` |
| YouTube 音轨 | `youtube:<YouTube ID>` | `data/youtube/<YouTube ID>/` |
| 用户补充音频 | `audio:<完整 SHA-256>` | `data/audio/<音频条目>/` |

身份不含标题、章节名或校对版本。不同平台记录即使同题也有各自身份；BV 关联不证明逐 P 对齐或音轨相同。阅读推荐版本由索引指定，不能通过扫描目录取排序最后的文件来替代选稿规则。

## 当前索引与冻结证据

| 入口 | 维护方式与含义 |
| --- | --- |
| [catalog.csv](../metadata/catalog.csv) | B 站与 YouTube 的来源目录、推荐文稿及原有质量字段 |
| [audio.csv](../metadata/audio.csv) | 用户补充音频身份、正文入口和独立复核字段 |
| [source-index.csv](../metadata/source-index.csv) | 从以上两张表生成的统一检索视图，共用稳定来源标识 |
| [source-labels.json](../metadata/source-labels.json) | 有明确批次依据的补充来源标签，仅覆盖列出的批次 |
| [training-source.json](../metadata/training-source.json) | 选定训练稿件与对应哈希，不随统一索引自动扩充 |
| [media/](../metadata/media/) | 当前恢复路径 `path` 与 ZIP 内路径 `archive_path` 分别登记 |
| [sources/](../metadata/sources/) 与 [provenance/](../provenance/) | 冻结来源、原响应、处理记录、失败尝试和迁移依据 |

统一索引的 `platform` 表示上述三种存储来源，`source_id` 为平台 ID 或音频 SHA-256。`bvid` 在 YouTube 行中只表示已记录的参考关系，可以为空；音频行取已有 `related_bvid`。`catalog` 指向负责该条记录的当前 CSV。

`quality_status` 原样取视频目录的推荐状态；补充音频没有同名状态，留空。`recognized_text_empty`、`requires_review`、`human_reviewed`、`timed_exports_available` 只传递来源中明确存在的字段，空值表示未在该索引提供，不能解释为 False 或审核通过。完整复核依据仍在原表和条目记录中。

历史 JSON、SQLite、字幕、文稿和响应保留原字节及旧路径。当前入口与导航使用新路径；[path-map.json](../metadata/path-map.json) 仅解释历史路径，不提供兼容目录。具体映射见[批次与校验](PROVENANCE.md)。

## 代码、快照与用途

`src/weimingzi_corpus/` 实现离线交付包接收、编辑、冻结及投影，`profiles/` 保存 CPT 与知识库等用途规则，详见[语料工具](CORPUS.md)。该工具的 Silver/Gold 记录契约与归档 CSV 的检索视图分别维护，统一来源索引不会自动把历史材料转换成已通过生产验收的交付包。

`tools/` 负责媒体恢复、当前索引和导航生成；`tests/` 验证离线工具与归档约束；`projects/` 保存专项设计。生成目录的命令与检查流程见[贡献说明](../CONTRIBUTING.md)。
