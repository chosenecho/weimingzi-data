# 仓库代理说明

开始工作前阅读 [代理使用指南](docs/AGENT-GUIDE.md) 和与当前任务相关的说明文件。该指南说明本项目的职责边界、检索方式、证据回查和数据修改流程。

本仓库用于归档和保存资料。不要把归档记录、模型结果、校对标注或检索命中改写为项目对内容真实性、完整性或权利状态的判断。维护数据以 `data/` 下的 JSON、JSONL 及 `selections/` 中记录为准；SQLite 和生成目录均为派生结果。

修改数据前先检查 `git status --short` 并保留已有改动。不要直接编辑 `docs/INDEX.md`、`docs/catalog/` 或 `docs/counts.json`；使用 `python tools/corpus.py generate` 生成。完成数据或工具修改后，按代理指南运行适用的校验。

涉及训练时先按 [README 的仓库分工](README.md#与训练工程协作)确定修改位置：本仓库修原始资料，`chosenecho/weimingzi-thought-model` 维护制作与训练，私有 `chosenecho/weimingzi-datasets` 保存正式版本。下游读取本仓库的完整 Git 提交；`selections/training.json` 是选稿记录，不代替 SFT 内容与证据审批。来源修订保留原记录及校订范围，由下游重新制作、审核和发布，不能直接修补已冻结训练包。
