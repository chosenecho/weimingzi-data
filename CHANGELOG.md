# 更新记录

## 2026-11-04

- 转录材料按来源拆为 `data/bilibili/`、`data/youtube/`、`data/audio/`；YouTube 脱离 BV 目录独立保存。
- 新增跨平台阅读目录与 `source-index.csv`，稳定身份与现有来源标签一致，保留各来源的质量字段。
- 整理首页、平台入口与离线语料文档，来源标签和导航纳入仓库检查。迁移前后校验非导航材料，见[平台迁移记录](provenance/layout-migration/2026-11-04-platforms/README.md)。
- 按 data、metadata、provenance、docs、tools 重组仓库，取消旧路径入口。
- 首页改为阅读、下载、训练和来源核验入口；完整视频目录改为分页索引。
- 新增数据说明、下载指南、目录说明、贡献指南与问题模板。
- 训练索引与媒体清单迁移至新路径；既有音频 ZIP 使用 archive_path 映射恢复。
- 新增仓库检查、音频恢复测试和 GitHub Actions。数据迁移依据见[迁移记录](provenance/layout-migration/2026-11-04/README.md)。

## 2026-11-03

历史批次及来源见[批次与校验](docs/PROVENANCE.md)。

- 发布首次视频文稿快照及音频分卷。
- 保留 R01—R06 的局部字句确认，登记独立训练入口。
- 补充音频和有正文的 YouTube 转录新增 AI 阅读稿。
- 无本地产物批次完成可获取音频的云识别，保留时间戳异常与原失败响应。
- 新增用户动态、专栏、文集和合集快照。
- 清除不可访问的索引条目与误存为 WebP 的 HTML 封面。
