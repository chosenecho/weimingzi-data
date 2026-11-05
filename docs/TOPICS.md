# 专题索引的维护与导出

[专题目录](catalog/topics.md)由 selections/topics.json 生成，配置格式为 thematic-index/v1。

专题与 data/collections.jsonl 中的平台集合分别维护。当前专题 ID 为 ismism，名称为“主义主义”。

纳入规则保留各自证据，不检索作者名、上传者名、简介或正文中的宽泛关键词：

1. collection_ids：明确指定的来源系列成员，保留集合 ID、题名、原成员位置。
2. title_prefixes：题名经 Unicode NFKC、去空白及 casefold 后，匹配配置的前缀，保留原题名和命中前缀。
3. exact_tags：仅匹配 metadata.tags 中规范化后相等的完整标签，保留原标签。
4. manual_inclusions：必须提供条目 ID、纳入角色及依据；可补充来源链接。
5. include_chapter_supplements：沿明确的章节补充关系加入独立录音，不推定音轨相同。

core 表示系列或题名规则命中；related 表示仅标签命中；introductory 表示有依据的导入材料；chapter_supplement 表示章节补充。角色不证明文稿完成或已人工审核。同一条目可保留多个纳入理由；已纳入视频的分 P 不重复作为专题条目。

BV1wk4y1L7Q2《【我是谁】无论是要批判我还是向我学习都要了解的基本情况》通过原“主义主义”标签和 issue #3 的导入材料依据纳入。其题名不含专题关键词，也没有伪造来源系列成员关系。生成索引保留它的直接转录、整理稿及复核状态。

    python tools/corpus.py topic ismism --output .cache/exports/ismism-coverage.json
    python tools/corpus.py topic 主义主义 --include-records --output .cache/exports/ismism-records.json
    python tools/corpus.py validate
    python tools/corpus.py generate
    python tools/corpus.py generate --check

topic 查询及完整导出对每个入选条目复用[分层覆盖查询](COVERAGE.md)，分别列出直接关联、跨来源引用、同音频与章节补充，保留所有变体。报告的 entries 包含纳入原因和完整 coverage；加 --include-records 才嵌入各份原始规范记录。顶层 counts 在每层跨专题条目按记录 ID 去重；不同层可能包含同一记录，不能相加当作文稿总数。

修改专题时编辑 selections/topics.json，运行校验和生成命令。校验拒绝未知集合、失效条目和缺少依据的人工纳入；不要手改生成目录，也不要为专题筛选改写原始题名、标签或集合。
