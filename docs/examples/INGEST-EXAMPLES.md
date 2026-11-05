# 增量协议合成示例

[详细设计](../INCREMENTAL-INGEST-SPEC.md) 定义协议。

- [批次 Schema](../contracts/ingest-batch-v1.schema.json)
- [补充操作 Schema](../contracts/ingest-enrichment-v1.schema.json)
- [媒体 Schema](../contracts/ingest-media-asset-v1.schema.json)
- [策略草案](ingest-policy.toml)，默认关闭。
- [合成批次清单](ingest-batch/manifest.json)和[记录文件](ingest-batch/records/)。
- [补充载荷](ingest-enrichment.json)和[设计附件校验脚本](validate_ingest_example.py)。

`ingest-batch/manifest.json` 和 `records/` 是一个包含视频、分 P、音频、ASR、AI 整理稿、动态及文章引用的合成批次。记录身份与哈希按仓库现有规范计算，可用于结构、完整性及隔离候选库检查。

所有正文、平台身份、代码提交、运行、媒体及核验声明均为测试构造，不是平台真实内容或真实 ASR。音频明确没有分发定位，视频和图片定位是合成字段；没有上传任何云端媒体。示例不能用于生产投递或真实来源、媒体可用性验证。

封包示例使用每条记录一个 JSON；目标 JSONL 表仍按记录合并，不能直接复制文件覆盖。`manifest.json` 中各类哈希含义见详细设计的“哈希边界”。批次本身不携带人工确认和训练选稿。

实际配置还需要解析存储别名、固定 App 触发主体、设置生产端版本和目标仓库基线。初始容量及重试预算是拟定参数，可在实测后调整，未宣称为 FC 或 GitHub 的产品限制。

`ingest-enrichment.json` 演示补充标题观测、时间和来源运行，不替换原展示标题。它是独立载荷示例，不属于 `ingest-batch/`，也不带自动获准的目标记录。

运行设计示例检查：

```sh
uv run --no-project --with jsonschema==4.26.0 python -X utf8 docs/examples/validate_ingest_example.py
```

该脚本只验证设计附件：Schema、批次哈希、文件清单、跨表引用、媒体字段、策略和反例。它在临时目录调用现有语料校验器，不修改正式数据，不访问平台和云端，不验证尚未实现的命令或 PR 流程。`jsonschema` 仅为示例检查使用，未加入语料工具的运行依赖。
