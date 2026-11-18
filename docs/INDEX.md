# 数据目录

[结构与术语](SCHEMA.md) · [查询与导出](QUERY.md)

由 `uv run python tools/corpus.py generate` 生成。文档按 kind 分别列出；排序不代表审核质量。

- [视频与分段](catalog/videos.md)
- [独立录音](catalog/audio_recordings.md)
- [专题索引](catalog/topics.md)
- [动态](catalog/posts.md)
- [专栏](catalog/articles.md)
- [文集、合集与系列](catalog/collections.md)
- [人物资料](catalog/people.md)
- [校对标注与复核状态](catalog/reviews.md)

items 6608 条；documents 8614 条；assets 2107 条；annotations 11 条。完整计数见 [counts.json](counts.json)。

正文来自 documents 的 text/content/blocks；音频与独立工件来自 assets，人工依据来自 annotations。
