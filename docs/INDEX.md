# 数据目录

[名词与概念](GLOSSARY.md) · [数据结构](SCHEMA.md)

由 `python tools/corpus.py generate` 生成。计数见 [counts.json](counts.json)。

- [视频与分段](catalog/videos.md)
- [独立录音](catalog/audio_recordings.md)
- [专题索引](catalog/topics.md)
- [动态](catalog/posts.md)
- [专栏](catalog/articles.md)
- [文集、合集与系列](catalog/collections.md)
- [人物资料](catalog/people.md)
- [校对标注与复核状态](catalog/reviews.md)

同一条目可有多份基础转录及整理稿；目录按识别方式和模型标注，并列出整理稿关联的输入。见[基础转录与整理稿](GLOSSARY.md#基础转录与整理稿)。

基础转录 3766 条；整理结果 2021 条；动态 2756 条；专栏 71 篇。

正文保存在对应 JSON 记录中；可用 `export` 命令生成 Markdown、文本和字幕。
