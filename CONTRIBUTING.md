# 参与维护

请按 [数据结构](docs/SCHEMA.md) 和 [维护流程](docs/MAINTENANCE.md) 提交。内容按类型入库，同一条目下保存有实际差异的结果；重复导出格式不再各存一份。

文字纠错请提供记录 ID、问题段落、对应音频区间或可回查依据。人工确认须说明范围，不把局部确认扩大为全文审核。音频下载问题请提供 `--list` 中的分卷标识、命令和报错。

提交前运行：

```sh
python tools/corpus.py generate
python tools/check_repository.py
python -m unittest discover -s tests -v
```

不要提交音频、SQLite 检索库、临时导出、锁文件或运行日志。内容权利与归属问题见 [CONTENT-RIGHTS.md](CONTENT-RIGHTS.md)。
