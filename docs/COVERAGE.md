# 分层文稿覆盖查询

coverage 查询视频、分 P 或独立录音，保留每份基础转录和整理稿的原始 ID。按视频查询会包含其子条目；按分 P 查询不会把同视频的其他分 P 算作直接覆盖。identifier 接受条目 ID 或精确的平台标识。

    python tools/corpus.py coverage BV1oq4y1q7rg --part 1
    python tools/corpus.py coverage i-7fee8b9e09f3f0d185f2aaa2
    python tools/corpus.py coverage BV1oq4y1q7rg --part 1 --include-records --output .cache/a.json
    python tools/corpus.py coverage BV1dA411T7xD --format jsonl --include-records --output .cache/a.jl

JSON 报告包含 scope_item_ids、四层关联、逐层计数和 summary；JSONL 每行包含查询条目、关联层及一份记录。加 --include-records 后，每个结果的 record 是未经改写的完整规范记录，包括正文、输入参照、附注、校对标注和质量快照。相同记录可能出现在不同证据层；各层按 ID 去重，summary.related 跨层按 ID 去重。此导出不选择“最佳版本”，也不更改训练选稿。

| 层 | 依据 | 范围 |
| --- | --- | --- |
| direct | 记录的 item_id | 查询条目及所查视频的分 P |
| cross_source | 显式引用或重录关系 | 展示原关系与来源 |
| same_audio | 完整音频 SHA-256 相等 | 展示哈希及原索引 |
| chapter_supplement | 显式章节补充关系 | 章节范围的补充文稿 |

cross_source 接受 references 和 references_video 关系，双向展示；视频级引用不证明分 P 对齐或音轨相同。

audible_rerecording_of 也进入 cross_source：从原条目可查有声重录版的文稿，保留确认依据。重录关系不证明音轨同一或逐段时间对齐；所有文稿保留实际录音条目及原时间值。

same_audio 保留已记录的完整哈希身份依据，不因文件暂不可恢复而抹除。chapter_supplement 使用 chapter_supplement_not_audio_identity 关系，不证明音轨相同或整条目完整覆盖。

关系只扩展一跳，不把引用、同音频、章节补充连成可传递的等价关系。返回的 items 也列出暂时只有元数据的关联条目。每份结果分别带有原条目、记录路径、关联证据和输入 transcript_ids。

完成与复核状态分别见 is_complete、is_fully_human_reviewed、requires_review 和原 quality。

text_status 只筛查存储文本：empty 表示没有文字，filler_only 表示去掉标点空白后只含“嗯呃啊哦唔额唉哎噢”中的字，其余为 text_present_unverified。它不测量音频，也不判断静音。complete_text_candidates 仅统计完成且非空、非纯填充词的整理稿；仍须结合质量标记复核。human_reviewed_complete_texts 另行统计实际标记为全文人工审核的结果。

## 回归案例

基础转录总记录数为 transcripts。text_present_transcripts 统计非空且非纯填充词的记录，filler_only_transcripts 统计纯填充词记录，empty_transcripts 统计空记录。

text_present_transcripts 只是文本筛查结果，不代表识别准确或已核过原音频。

- BV1oq4y1q7rg P1：direct 包含双视频结果包中的新稿；cross_source 保留 YouTube LhbZtt3hmSE 的独立稿及指向 Bilibili 视频的原引用。新稿不替换旧稿。
- BV1dA411T7xD 中“美的辩证法”条目 i-7fee8b9e09f3f0d185f2aaa2：same_audio 展示其他来源版本及完整哈希。
- “克尔凯廓尔三阶段论”条目 i-e33df3f1154c7f435ae90247：same_audio 展示其他来源版本及完整哈希。
- 独立录音“神创论”“自然神论”“神义论”：从明确的章节补充关系查阅；未完成整理稿仍显示 is_complete=false。
- BV1CP4y1s7BM P2：用户已确认原分 P 无声，P1 是有声重录版。direct 保留纯填充词原稿；cross_source 返回 P1 已有文稿。无声判断来自用户确认，filler_only 仍只表示文本筛查结果。

覆盖案例依据 [issue #4](https://github.com/chosenecho/weimingzi-data/issues/4) 和仓库规范记录。

填充词案例原问题见 [issue #5](https://github.com/chosenecho/weimingzi-data/issues/5)。
用户确认的原话、日期与重录关系见[质量核查记录](evidence/issue-5-filler-only.md)。

查询直接层为空时，应继续检查相关层；相关层有稿也不等于该分 P 已有直接整理稿。
