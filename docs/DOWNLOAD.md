# 音频下载

音频只维护 [data/audio.jsonl](../data/audio.jsonl) 这一份索引。可恢复与不可获取的数量、音频总字节数见 [counts.json](counts.json)。

```sh
python tools/restore_audio.py --list
python tools/restore_audio.py
python tools/restore_audio.py --verify-only
```

`--list` 列出可恢复文件的总数、总字节数及分卷标识。按需选择其中一个标识：

```sh
python tools/restore_audio.py --archive RELEASE_TAG/ARCHIVE.zip
```

将示例替换为 `--list` 的实际值；`--archive` 可重复使用。下载文件缓存到 `.cache/media/`，音频按哈希恢复到 `media/audio/`。这两个目录不入库。

下载工具依次检查 ZIP 的字节数及 SHA-256、成员集合、成员大小、音频文件 SHA-256；已有正确文件直接复用。恢复路径可以调整，`downloads[].member_path` 必须继续使用远端 ZIP 内的原成员名。

`availability=unavailable` 的记录没有可用下载地址，工具会跳过。外部存储键只保留已知标识，不表示该文件现可下载。文本结果与音频可用状态独立：存在转录不代表仓库可恢复对应音频。
