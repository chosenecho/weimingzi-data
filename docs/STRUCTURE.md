# 目录与主目录字段

## 按内容和材料分类

~~~text
data/
  transcripts/
    主义主义/
    哲学与经典/
    社会与现实/
    实践与项目/
    问答与交流/
    生活与学习/
    文艺与游戏/
    杂谈与其他/
  datasets/
    校对数据/
    转录数据/
    文本修订/
    训练选稿/
    资料清单/
  user-content/
metadata/
  catalog.csv
  training-source.json
  review-issues.json
  dataset-summary.json
  media/
~~~

主题按既有标题和栏目整理，分类直接登记在主目录中，可以人工调整。每个内容条目只放在一个主题下；条目内保留分段、各份转录及其校对稿，`补充版本/` 用来放同一条目的其他材料。

内容目录采用现有 BV、材料标识或章节名定位。平台和文件来路仅作为可用的记录字段，不决定存放层级。条目中的参考关联不证明音轨相同或分段已经对齐。

数据库、报告与清单按材料类型集中到 `data/datasets/`。动态、文章等保持其适用的数据格式，并作为数据集登记在主目录。

## 一份主目录

[catalog.csv](../metadata/catalog.csv) 同时登记转录和数据集。转录按可独立取用的一份材料登记；同一条目的多个分段或补充版本共用 `collection`。数据集按一组文件登记，文件清单见对应 README。

| 字段 | 含义 |
| --- | --- |
| record_id | 唯一材料标识，改标题或目录时保留 |
| kind | `transcript` 或 `dataset` |
| category | 主题或材料类别 |
| collection | 内容条目或数据集的根目录 |
| folder | 这份材料所在目录，位于 collection 内 |
| title、part_title | 内容标题和分段标题 |
| recommended_text | 阅读入口；无正文时留空 |
| recommended_quality_status | 已有版本的质量状态；未提供时留空 |
| requires_review、human_reviewed 等 | 实际登记的复核字段；空值表示未知 |
| platform、bvid、youtube_id、audio_sha256、source_details 等 | 已有标识或补充信息；可以为空 |

读取当前仓库文件时使用主目录的路径。资料文件自身的路径、时间和模型字段按记录内容理解。新增一种材料无需增加来源目录或来源专用索引。

## 派生入口和工具

[分类目录](INDEX.md)、条目 README、数据集 README 和 [统计](../metadata/dataset-summary.json) 从主目录生成。[training-source.json](../metadata/training-source.json) 是用途选稿，不因主目录新增材料而自动扩充。[媒体清单](../metadata/media/) 负责音频恢复。

`src/weimingzi_corpus/` 与 `profiles/` 提供交付包接收、语料编辑和用途导出，见[离线语料工具](CORPUS.md)。维护命令见[贡献说明](../CONTRIBUTING.md)。
