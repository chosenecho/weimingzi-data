# 训练源数据

本仓库为 `chosenecho/weimingzi-thought-model` 提供视频文稿来源。当前机器入口是 [training-source.json](../metadata/training-source.json)，包含 **1,966** 个选定分 P；数量由索引的 `total` 与 `entries` 登记，亦见 [dataset-summary.json](../metadata/dataset-summary.json)。

## 选稿规则

每个 B 站分 P 选择一组完整的 AI 阅读稿和校对记录，有局部确认校正版时优先使用校正版。原始 ASR、字幕、YouTube、用户补充音频、动态与专栏不自动作为额外独立训练样本加入该入口。

选稿数据见[训练选稿数据集](../data/datasets/训练选稿/README.md)。使用者应记录所采用的 Git 提交，并核验选稿哈希及质量状态。

## 选稿索引

| 字段 | 含义 |
| --- | --- |
| bvid、page | 视频及分 P 标识 |
| paths | 当前阅读稿与校对记录路径 |
| sha256 | 所选文件的 SHA-256 |
| original_paths、original_sha256 | 应用局部校正前的文件及哈希 |
| quality_status | 该版本的复核状态 |
| confirmed_issues | 已确认的具体字句记录 |

路径均相对于仓库根目录。选稿记录及文件哈希由检查工具核验。

## 已有局部确认

[校正记录](../data/datasets/%E6%96%87%E6%9C%AC%E4%BF%AE%E8%AE%A2) 保存 R01—R06 的前后文本与具体结论，原始材料另行保留：

- R01：恢复原句重复和句式。
- R02：恢复并列的“定律、必然性”。
- R03：确认“实践论”现稿，无需改字。
- R04：记录 L／L主义所指，不把缩写擅自展开写入原文。
- R05：两处改为“工益是最大的公益”。
- R06：补回“那坐你这班车的人”的“那”字。

以上仅为具体字句与术语确认，不表示全文、音频、说话人或训练样本已完整审核。派生问答与训练标注不冒充视频原始发言回写。

## 获取与核验

克隆仓库，检出采用的固定 Git 提交，读取索引中的选定路径并检查 SHA-256。只准备文字训练源无需下载音频。

```bash
git checkout <选定提交>
python -X utf8 tools/check_repository.py --verify-hashes
```

检查工具核验当前索引中的选稿与原稿哈希，不调用模型或下载音频。后续扩充、重新校对或训练包生成，应登记为独立变更；不要随 main 自动替换已冻结的训练源。

内容使用条件见[内容权利说明](../CONTENT-RIGHTS.md)，原始质量限制见[数据说明](DATA-CARD.md)。
