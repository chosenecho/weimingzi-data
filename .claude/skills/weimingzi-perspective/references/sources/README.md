# 原始材料回查说明

本目录不复制视频、音频、文章或动态正文。原始维护记录保留在仓库 `data/` 中；研究摘要、记录 ID、字段位置和质量限制位于同级 `../research/`。

- 长文：`data/articles/<article_id>.json`，按报告给出的 `text` 段落号回查。
- 动态：`data/posts/<post_id>.json`，核对当前动态正文、转发对象及作者字段，不把嵌入转发内容算作当前账号的原话。
- 转录：`data/transcripts/<transcript_id>.json`，核对 `item_id`、`method`、`model`、`quality`、`segments` 和说话人标签；没有标签时不自行归属。
- 条目日期与关系：`data/items.jsonl`，核对 `kind`、父子关系、`published_at`、`published_at_unix_seconds` 与 `observed_at`。

仓库搜索只用于定位线索。参照 `docs/AGENT-GUIDE.md`、`docs/SCHEMA.md`、`docs/DATA-CARD.md` 和仓库根目录 `CONTENT-RIGHTS.md` 使用和解释归档材料。
