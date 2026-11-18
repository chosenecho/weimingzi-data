# 原生四实体增量示例

当前唯一接收协议为 `contract_version: 2`、`record_schema_version: 3`、`kind: weimingzi_native_increment`。批次结构见[机器契约](../contracts/ingest-batch-v2.schema.json)，完整行为见[增量协议](../INCREMENTAL-INGEST-SPEC.md)。[合成清单](ingest-batch/manifest.json)封装六条完整原生记录：两个 item、两个 document 和两个 asset；没有人工 annotation。每个载荷独立存于 `records/{entity}/{id}.json`，目标库由原生写入器合并，不直接复制文件覆盖 JSONL。

所有文字、身份、提交、模型、媒体和核验声明均为合成测试构造。音频、归档及 OSS 对象没有在此示例上传或验证；其中两条 `metadata.media_assets` 观察用于检查[当前媒体观察契约](../contracts/ingest-media-asset-v2.schema.json)，`asset_version` 为 `2`。生产端声明的 `readback_sha256` 表示来源证据字段，接收器的结构检查本身不访问远端或证明对象字节。

[策略示例](ingest-policy.toml)是关闭状态的部署参考，不授予权限，也不是运行时配置入口。实际许可由仓库中的 `ingest/policy.py` 固定。自动来源只可在受限来源范围内增加机器结果和观察；人工确认、采用事实、全文审核与确认静音需由维护者以真实证据维护完整原生图。

操作仅有 `insert` 和 `replace`。每条都声明 `entity`、完整载荷、载荷规范 JSON 哈希、来源引用及 `expected_record_sha256`：`insert` 必须显式为 `null`，`replace` 必须是旧完整原生记录的 SHA-256。后置状态完全相同先于 CAS 判断；替换仍受来源、不可改事实和追加许可约束。新结果使用新记录，原时间、质量、模型和输入快照保持原事实。

[校验脚本](validate_ingest_example.py)以真实接收器检查严格 JSON、文件清单、两种哈希、来源关联和权限，再在临时目录通过唯一原生写入器验证完整候选图；它只读示例并创建临时目录，不改维护数据，不需要 Git 仓库或网络。基础检查只用项目依赖：

```sh
uv run python docs/examples/validate_ingest_example.py
```

如需额外校验 JSON Schema 本身及示例是否符合它，可临时安装检查依赖：

```sh
uv run --no-project --with jsonschema==4.26.0 python -X utf8 docs/examples/validate_ingest_example.py
```

版本 1 的旧批次、旧表名和补充载荷已退出当前接收协议。既有收据保持历史字节，按文件 SHA-256 和对应历史 checkout 复查，不通过当前接收器转换或重放。已接收的当前收据重投递会单独报告 `accepted_state_present` 或 `accepted_state_changed`，不会用历史结果冒充当前状态断言。
