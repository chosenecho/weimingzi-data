# 批次与校验

## 当前入口

| 用途 | 入口 |
| --- | --- |
| 跨平台文稿检索 | [source-index.csv](../metadata/source-index.csv) · [阅读目录](SOURCE-INDEX.md) |
| 当前源目录 | [catalog.csv](../metadata/catalog.csv) · [audio.csv](../metadata/audio.csv) |
| 训练选稿与哈希 | [training-source.json](../metadata/training-source.json) |
| 音频恢复与哈希 | [media/](../metadata/media/) |
| 当前目录统计 | [dataset-summary.json](../metadata/dataset-summary.json) |
| 历史路径解释 | [path-map.json](../metadata/path-map.json) |
| 目录迁移校验 | [迁移记录](../provenance/layout-migration/2026-11-04/README.md) |
| 平台目录重构 | [迁移记录](../provenance/layout-migration/2026-11-04-platforms/README.md) |

## 历史批次

| 批次 | 记录 |
| --- | --- |
| 首次视频快照 | [整理报告](../provenance/initial-snapshot/整理报告.json) · [文件清单](../provenance/initial-snapshot/文件清单.json) |
| 训练源及局部字句确认 | [原训练索引](../provenance/training/2026-11-03/training-source.v1.json) · [校正记录](../provenance/corrections/2026-11-03-r1/) |
| 补充音频与 YouTube AI 校对 | [处理批次](../provenance/ai-proofreading/2026-11-03-opencode-go/README.md) |
| 无本地产物 ASR 补跑 | [处理批次](../provenance/asr/2026-11-03-missing-local/README.md) |
| 用户动态、专栏与合集 | [入库回执](../data/user-content/入库回执.json) · [独立清单](../data/user-content/publication-manifest.json) |
| 无效条目及假封面清理 | [清理记录](../provenance/cleanup/2026-11-03-invalid-entries/README.md) |

各批次数量、失败记录和待审状态描述当时的处理结果；它们不自动更新为当前状态。既有 Git 历史、音频 Release 和原始响应不回写。

## 新目录中的历史清单

历史清单和 SQLite 字段可能仍记录 `视频/`、`补充音频/` 等旧路径，或记录数据源自己的内部路径。迁移后的当前入口位于 `metadata/`；历史文稿路径可按 `path-map.json` 的最长前缀替换规则定位。保留的原训练索引和原媒体清单在 `historical_manifest_overrides` 中列明。

同一子树内的相对路径继续按该子树解释，例如用户内容清单相对于 `data/user-content/`。不能把所有历史路径都当作仓库根目录路径。

导航页和当前机器索引为新结构更新；旧清单中的导航页哈希因此可能与当前页不同。迁移记录登记这些修改。原始正文、字幕、音频内容及训练稿件哈希以各来源记录和当前训练／媒体索引核对。

## 检查仓库

```bash
python -X utf8 tools/check_repository.py
python -X utf8 tools/check_repository.py --verify-hashes
python -m unittest discover -s tests -v
```

默认检查跨平台索引、分页目录、来源标签、导航链接、路径、数量和媒体清单结构。`--verify-hashes` 另核验训练索引中的选稿及原稿哈希。检查过程不下载音频，也不重新调用模型。
