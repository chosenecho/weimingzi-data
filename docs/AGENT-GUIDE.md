# 代理使用指南

## 项目范围

本仓库用于归档、保存和提供资料检索。代理可以帮助查找记录、说明字段含义、整理可追溯的引用和执行仓库维护；不把这些工作扩展成项目对人物、内容或观点的真实性判断。

记录存在不表示正文完整、准确、经过人工审核或获得统一再发布许可。模型、字幕来源、校对标注、质量字段和人工确认都按记录本身及其限定范围解释；未知状态保持未知。内容权利问题按仓库中的[内容权利说明](../CONTENT-RIGHTS.md)处理。

## 开始前

先阅读任务相关的说明：

- [数据卡](DATA-CARD.md)：归档限制、质量状态和使用范围。
- [数据结构](SCHEMA.md)：记录字段、关联和时间单位。
- [维护说明](MAINTENANCE.md)：检索、导出、入库和校验命令。
- [名词与概念](GLOSSARY.md)：转录、整理稿、校对标注等项目术语。
- [内容权利说明](../CONTENT-RIGHTS.md)：使用、再发布和训练的权利范围。

需要修改仓库前，先运行 `git status --short`，保留已有工作区改动。不要直接修改生成的 `docs/INDEX.md`、`docs/catalog/` 和 `docs/counts.json`；用 `python tools/corpus.py generate` 更新它们。

## 查找和引用

首次检索或归档数据更新后，生成本地 SQLite 检索副本，再搜索正文：

```sh
python tools/corpus.py export --format sqlite --output .cache/exports/corpus.sqlite3
python tools/corpus.py search 唯物主义
```

指定数据库或结果数量时：

```sh
python tools/corpus.py search 唯物主义 --database .cache/exports/corpus.sqlite3 --limit 20
```

SQLite 是可删除重建的派生数据，不是归档来源。`search` 只索引基础转录、整理稿、动态和专栏正文，不检索全部元数据、校对标注、附注或独立校验稿。少于三个字符的查询使用字面子串匹配；检索不提供语义理解、拼写纠正或事实判断。

搜索命中只是定位线索。引用前打开对应的维护记录，核对完整段落或分段、相关字段、来源链接、模型和质量信息；需要时间定位时同时查看原记录的 `time_unit`。回答中给出记录 ID 和仓库相对路径，并说明引用的是哪个字段、段落或分段。没有搜到结果只能说明当前查询未命中，不能据此断定仓库没有相关记录。

需要检索段落校对标注时，使用专用导出：

```sh
python tools/corpus.py export --format review_issues --output .cache/exports/review_issues.jsonl
```

需要限定整理稿 ID 或训练选稿时，参照[维护说明中的标注导出命令](MAINTENANCE.md#查看校对标注)。查询附注、输入参照或独立校验稿时，检查对应维护 JSON；不要把正文全文索引当成这些内容的索引。

## 保存和修改

维护数据在 `data/` 下的 JSON、JSONL 文件以及 `selections/` 中。SQLite、CSV、字幕、TXT、Markdown 导出和生成目录都可重新生成；除非任务明确要求更新维护数据，不要只为检索或查看结果提交这些派生文件。

新增批次按[维护说明](MAINTENANCE.md)执行校验、规划和应用。新增或修订记录时保留来源、原文、模型信息、时间顺序、质量状态和不确定性；同一内容的不同转录或整理稿并列保存。不得为了让导出通过而排序、截断、取整或修补原始时间值，也不得从无文字、不可用字幕或缺失音频推断确认静音。

校验并更新生成目录：

```sh
python tools/corpus.py validate
python tools/corpus.py generate
python tools/check_repository.py
python -m unittest discover -s tests -v
```

只改文档时，检查新增链接和示例命令是否与现有入口一致；涉及代码或数据时，运行适用的测试和校验，并在交付说明中指出未覆盖的部分。
