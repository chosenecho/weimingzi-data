# 消费配置交接

训练选稿、发布 head、确认应用和段落收录策略由 `chosenecho/weimingzi-thought-model` 维护。本仓保存原始资料、多版本关系、局部确认和片段归属；基础校验、入库与 SQLite 导出只依赖归档数据。

## 交接位置

制作工程中的文件：

- `configs/corpus/training.json`：训练选稿引用。
- `configs/corpus/release.json`：发布 head、确认引用及段落排除指针。
- `configs/corpus/consumption-handoff.json`：原始提交、配置哈希及兼容投影核对结果。
- `docs/CORPUS_CONSUMPTION.md`：消费配置字段、校验和导出说明。

原始配置来自本仓完整提交 `2cdba19147d7df4b05ebcc53b89f83afe4297be5`，按 Git 对象原字节交接。旧发布算法与字段说明保留在该提交的[历史发布文档](https://github.com/chosenecho/weimingzi-data/blob/2cdba19147d7df4b05ebcc53b89f83afe4297be5/docs/RELEASE.md)；它描述当时的消费策略，不作为当前维护规则。

## 下游命令

在制作工程根目录执行，`CORPUS_ROOT` 指向已锁定完整 Git 提交的资料仓库：

```sh
uv run wm-train corpus check --corpus-root CORPUS_ROOT
uv run wm-train corpus export --view training --corpus-root CORPUS_ROOT --out .cache/exports/training.jsonl
uv run wm-train corpus export --view release --corpus-root CORPUS_ROOT --out .cache/exports/release.jsonl
uv run wm-train corpus export --view release --corpus-root CORPUS_ROOT --policy clean --out .cache/exports/release-clean.jsonl
```

发布导出默认使用 `full`。`clean` 显式保留旧算法用于重现：段内一处局部确认可以使整段进入投影，导出中的确认列表也沿用旧范围。它不证明整段标注均已解决。`full` 保留未被配置显式排除的 head 段落，同样不表示全文审核通过。

## 资料更新后的流程

本仓先修订资料、保留原记录和校订依据，并完成基础校验、目录生成及全仓检查。下游随后锁定新的完整 Git 提交，更新选稿或发布指针并执行消费校验。消费规则失效由下游处理，不阻断有效归档资料的入库。

局部确认仍只适用于记录中的字句或术语；片段归属仍以原文哈希和时间锚点为准。两类证据分别引用，选稿不改变 `quality.is_fully_human_reviewed`，也不授予第三方内容使用权。来源修订后由下游重新制作和审核；冻结训练包、既有版本及历史审批保留原字节。
