# 纠错与贡献

## 报告内容问题

使用仓库的“文稿／来源纠错”Issue 模板，提供 BV 或音频标识、当前文件路径、具体段落或时间区间、原文、建议修订及可核对来源。请区分原始识别错误、AI 改写和来源归属问题。

局部确认只适用于对应字句，不能据此将全文状态改成人工审核通过。涉及权利或归属的请求，按[内容权利说明](CONTENT-RIGHTS.md)提供具体路径及依据。

## 提交数据变更

来源按平台独立建目录：B 站使用 BV 与分 P，YouTube 使用自身 ID，用户音频登记完整 SHA-256。章节和跨平台对应记入索引，目录不按推测的内容关系合并；位置和稳定身份约定见[目录结构](docs/STRUCTURE.md)。

保留原始文稿、调用响应、失败尝试和时间戳异常。新版本、补充识别或人工校正单独保存，登记来源、模型、时间、哈希和审核状态。历史批次清单与原始响应按快照保存；当前索引和导航同步更新。

原始音频通过 Release 和媒体清单分发，不直接加入 Git。账号凭据、API Key、cookies 和浏览器配置不应进入提交。

## 更新目录

增加或调整数据后，在仓库根目录执行：

```bash
python -X utf8 tools/check_repository.py --update-index
python -X utf8 tools/check_repository.py --verify-hashes
python -m unittest discover -s tests -v
```

`--update-index` 更新跨平台目录、统一 CSV、分页视频目录、补充来源标签、机器统计和首页统计表。维护视频及 YouTube 条目时更新 `metadata/catalog.csv`，补充音频更新 `metadata/audio.csv`；生成的 `source-index.csv` 不手工编辑。新增补充批次应在来源标签工具中登记明确依据。

媒体清单的 `path` 是当前恢复目标，`archive_path` 是 ZIP 内条目名。目录改名只调整恢复目标，已发布 ZIP 的内部路径与哈希保持原值。

## 提交说明

说明修改对象、依据、影响的来源版本、复核状态和检查结果。改动训练入口时列明选稿变化；只调整目录或导航时，应核验正文与音频哈希。目录与历史路径解释见[批次与校验](docs/PROVENANCE.md)。
