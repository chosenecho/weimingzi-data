# 数据整理与纠错

## 新增和整理材料

1. 将转录材料放到 `data/transcripts/<主题>/<内容条目>/`；同一内容的分段和补充版本放在该条目内。主题可直接采用现有分类。
2. 跨条目的数据库、JSON、CSV 等资料按材料类型放到 `data/datasets/<类别>/`。动态与文章继续使用 `data/user-content/` 的格式。
3. 在 [catalog.csv](metadata/catalog.csv) 登记材料身份、分类、目录和可用正文。转录使用 `kind=transcript`，成组数据使用 `kind=dataset`。新增数据集先提供 README 入口。
4. 如果有质量状态或来源信息，按实际字段填写；没有依据时留空。新增转录不会自动加入训练选稿。

具体字段见[目录结构](docs/STRUCTURE.md)。分类、标题和目录位置可以调整；`record_id` 保持唯一。同一内容的不同转录分别登记，共用 `collection`，避免把多个版本误算为同一份文稿。

清单和数据库均作为数据保存。日常维护主目录即可，分类页与条目 README 由工具生成。正文、字幕、调用响应和文本修订材料应保留各自内容，避免用校对稿覆盖原始转录。

## 生成与检查

~~~sh
python -X utf8 tools/check_repository.py --update-index
python -X utf8 tools/check_repository.py --verify-hashes
python -m unittest discover -s tests -v
~~~

`--update-index` 读取主目录，生成分类导航、条目与数据集 README、机器统计及首页统计表。主目录 CSV 由维护者编辑，工具不会重新推断主题或审核状态。

音频通过 Release 和媒体清单分发。清单的 `path` 是当前恢复位置，`archive_path` 是 ZIP 内条目名；改目录时只改恢复位置，ZIP 内条目名及其哈希保持原值。

## 报告和修订正文问题

使用“文稿／来源纠错”Issue 模板，提供材料标识、文件路径、具体段落或时间区间、原文、建议修订与可核对依据。局部确认只适用于对应字句，不应将全文状态改为人工审核通过。涉及权利或归属的请求见[内容权利说明](CONTENT-RIGHTS.md)。

提交时说明修改对象、依据、质量状态及检查结果。账号凭据、API Key、cookies 和浏览器配置不应进入提交。
