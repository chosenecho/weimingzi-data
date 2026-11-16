# 音频下载

schema v3 的音频和 ZIP 归档资产统一维护在 [data/assets.jsonl](../data/assets.jsonl)，版本由 [data/schema.json](../data/schema.json) 声明。音频下载项通过 `archive_id` 引用同一索引中的归档资产；`sha256`、`size_bytes` 分别描述相应音频或 ZIP 的实际文件字节，不使用结构化 JSON 的摘要替代文件哈希。可恢复与不可获取的数量、音频总字节数见 [counts.json](counts.json)。

```sh
python tools/restore_audio.py --list
python tools/restore_audio.py
python tools/restore_audio.py --verify-only
```

工具根据 schema 声明默认读取 v3 的 `data/assets.jsonl`；读取旧 v2 数据时默认使用 `data/audio.jsonl`。显式 `--index` 继续接受仓库相对路径，例如 `--index data/assets.jsonl`，或仍按旧音频记录格式保存的自定义索引。v3 的音频投影保留原下载字段，恢复操作不依赖其他文稿实体。

`--list` 列出可恢复文件的总数、总字节数及分卷标识。按需选择其中一个标识：

```sh
python tools/restore_audio.py --archive RELEASE_TAG/ARCHIVE.zip
```

将示例替换为 `--list` 的实际值；`--archive` 可重复使用。下载文件缓存到 `.cache/media/`，音频按哈希恢复到 `media/audio/`。这两个目录不入库。

下载工具依次检查 ZIP 的字节数及 SHA-256、成员集合、成员大小、音频文件 SHA-256；已有正确文件直接复用。恢复路径可以调整，`downloads[].member_path` 必须继续使用远端 ZIP 内的原成员名，`release_tag` 保持原发布标识。

需要留存恢复证据时使用 `tools/audit_audio_restore.py`，参数及保存要求见[保存运行与交接](PRESERVATION-OPERATIONS.md)。审计记录实际读取索引的路径、字节数与 SHA-256，并记录 schema 依赖及所用投影模块；v3 的归档资产与音频资产均由同一份索引的字节摘要覆盖。索引或 schema 在审计期间改变时，完整性检查失败；已有历史审计报告继续保留原内容。

`availability=unavailable` 的记录没有可用下载地址，工具会跳过。外部存储键只保留已知标识，不表示该文件现可下载。文本结果与音频可用状态独立：存在转录不代表仓库可恢复对应音频。
