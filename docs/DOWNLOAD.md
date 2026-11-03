# 音频下载与校验

文字、字幕、索引和 SQLite 快照保存在 Git 中；音频 ZIP 保存在本仓库 GitHub Releases。当前文件数及字节数来自 [媒体清单](../metadata/media/) 和 [dataset-summary.json](../metadata/dataset-summary.json)。

## 准备

克隆仓库，安装 Python 3.12 或更高版本，在仓库根目录执行以下命令。下载工具仅依赖 Python 标准库。

```bash
python -X utf8 tools/fetch_media.py --list
```

输出包含音频数量、解压字节数、ZIP 总字节数和分卷名称。磁盘空间需要同时容纳 ZIP 缓存、解压音频及仓库已有文件。

## 按范围下载

| 范围 | 清单 |
| --- | --- |
| 首次快照 | [base.json](../metadata/media/base.json) |
| 无本地产物 ASR 补跑 | [asr-2026-11-03.json](../metadata/media/asr-2026-11-03.json) |

```bash
# 默认恢复所有已发布批次
python -X utf8 tools/fetch_media.py

# 只恢复首次快照
python -X utf8 tools/fetch_media.py --collection base

# 只恢复 ASR 补跑音频
python -X utf8 tools/fetch_media.py --collection asr-2026-11-03

# 只恢复指定分卷
python -X utf8 tools/fetch_media.py --collection base --asset audio-001.zip
```

下载后的音频位于 `data/bilibili/` 或 `data/audio/`。每个音频目录中的 `.download.md` 记录恢复路径、字节数、SHA-256 和 Release 链接。

## 校验与重试

```bash
# 离线检查全部音频；有缺失或哈希不符时返回非零退出码
python -X utf8 tools/fetch_media.py --verify-only

# 只检查某个批次
python -X utf8 tools/fetch_media.py --collection asr-2026-11-03 --verify-only
```

缓存位于 `.cache/media/<release_tag>/`。下载与提取先写入 `.part`，校验通过后再替换目标文件；重复执行会复用完整且哈希正确的缓存和音频。未完成的分卷会重新下载。

## 新目录与旧 ZIP

Release 中的既有 ZIP 不重打包。媒体清单 v2 用 `archive_path` 标识 ZIP 内的历史条目，用 `path` 标识当前恢复位置。应通过工具恢复，直接把旧 ZIP 解压到仓库根目录会产生旧目录。

## 遇到问题

保留报错、命令、批次、分卷名称和实际 SHA-256，在 [Issues](https://github.com/chosenecho/weimingzi-data/issues) 提交下载问题。请勿附带账号凭据或 cookies。当前检查范围及来源说明见[数据说明](DATA-CARD.md)。
