# qrcode-terminal wheel

`qrcode_terminal-0.8-py3-none-any.whl` 是 `bilibili-api-zoku` 的传递依赖，保留原包内容与 METADATA。METADATA 声明许可证为 MIT，项目地址为 <https://github.com/alishtory/qrcode-terminal>。

本地用 `python -m pip wheel qrcode-terminal==0.8 --no-deps --wheel-dir workers/ingest-probe/vendor-wheels` 取得纯 Python wheel。保留此文件是因为 Python Worker 的跨平台解析默认不构建 sdist；不是用它替代 B 站 SDK。Worker 不调用二维码登录功能。

文件 SHA-256：`34cabc6da4b061087b80ce877a9a5d81ddfb3040347dbacb6b8e16b16c28fa72`。版本、相对路径与哈希同时记录在 `pylock.toml` 中。
