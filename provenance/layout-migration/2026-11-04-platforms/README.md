# 2026-11-04 平台目录重构

迁移依据见 [manifest.json](manifest.json)，其中记录起始 Git 提交、目录映射、检查范围、非导航文件数量和清单摘要。

- B 站材料：`data/videos/` → `data/bilibili/`。
- 原来嵌套在 BV 下的 YouTube 材料：`data/videos/<BV>/YouTube/<ID>/` → `data/youtube/<ID>/`。
- 用户补充音频：`data/supplemental-audio/` → `data/audio/`，当前音频索引命名为 `metadata/audio.csv`。
- 统一索引与跨平台目录由当前视频、音频 CSV 生成。历史路径解释登记在 [path-map.json](../../../metadata/path-map.json)。

迁移前后逐文件比对非导航材料的大小与 SHA-256，包括正文、字幕、原始响应、来源 JSON、数据库和 AI 文稿。只更新导航、当前索引和工具中的路径；原始内容及质量字段不作校正。导航的相对链接按目标目录重新计算。

媒体清单的 `path` 改为当前恢复目标，`archive_path` 保留已发布 ZIP 内的原路径。冻结批次和历史清单继续保留当时字段。未创建旧目录别名。

生成与检查命令见[贡献说明](../../../CONTRIBUTING.md)。
