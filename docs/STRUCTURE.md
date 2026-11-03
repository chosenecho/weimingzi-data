# 目录结构

```text
weimingzi-data/
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── CONTENT-RIGHTS.md
├── data/
│   ├── videos/<BV>/
│   ├── user-content/
│   └── supplemental-audio/
├── metadata/
│   ├── catalog.csv
│   ├── supplemental-audio.csv
│   ├── training-source.json
│   ├── dataset-summary.json
│   ├── media/
│   ├── sources/
│   └── path-map.json
├── provenance/
│   ├── initial-snapshot/
│   ├── training/
│   ├── corrections/
│   ├── ai-proofreading/
│   ├── asr/
│   ├── cleanup/
│   └── layout-migration/
├── docs/
│   ├── VIDEO-INDEX.md
│   └── videos/
├── tools/
└── tests/
```

## 数据与当前索引

`data/` 保存阅读材料、来源版本和 SQLite 快照。视频内部仍按 BV、分 P、YouTube 标识及版本组织，保留原始文件名。

`metadata/` 保存当前可用的机器入口：统一文稿目录、训练源、音频恢复清单、复核事项和缺失引用。`sources/` 中的来源快照保留原字段，不代表当前平台状态。

## 历史证据

`provenance/` 保存首次快照、后续处理批次、局部校正和清理记录。原始错误响应、旧统计和旧路径按历史证据保留。目录迁移记录及历史路径对照见[批次与校验](PROVENANCE.md)。

## 工具与文档

`tools/` 包含音频恢复和仓库检查工具；`tests/` 验证音频恢复的路径与校验行为。文档、分页视频目录及其生成规则见[文档导航](README.md)与[贡献说明](../CONTRIBUTING.md)。

此次结构调整不提供旧根目录或旧脚本位置的兼容入口。
