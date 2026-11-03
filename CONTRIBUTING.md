# 纠错与贡献

## 报告内容问题

使用仓库的“文稿／来源纠错”Issue 模板，提供 BV 或音频标识、当前文件路径、具体段落或时间区间、原文、建议修订及可核对来源。请区分原始识别错误、AI 改写和来源归属问题。

局部确认只适用于对应字句，不能据此将全文状态改成人工审核通过。涉及权利或归属的请求，按[内容权利说明](CONTENT-RIGHTS.md)提供具体路径及依据。

## 提交数据变更

保留原始文稿、调用响应、失败尝试和时间戳异常。新版本、补充识别或人工校正单独保存，登记来源、模型、时间、哈希和审核状态。历史批次清单与原始响应按快照保存；当前索引和导航同步更新。

原始音频通过 Release 和媒体清单分发，不直接加入 Git。账号凭据、API Key、cookies 和浏览器配置不应进入提交。

## 更新目录

增加或调整数据后，在仓库根目录执行：

```bash
python -X utf8 tools/check_repository.py --update-index
python -X utf8 tools/check_repository.py --verify-hashes
python -m unittest discover -s tests -v
```

`--update-index` 更新分页视频目录、机器统计和首页统计表。更新媒体清单时，分别登记 ZIP 条目的 `archive_path` 和当前目标 `path`，不要只修改其中一个字段。

## 提交说明

说明修改对象、依据、影响的来源版本、复核状态和检查结果。改动训练入口时列明选稿变化；只调整目录或导航时，应核验正文与音频哈希。目录与历史路径解释见[批次与校验](docs/PROVENANCE.md)。
