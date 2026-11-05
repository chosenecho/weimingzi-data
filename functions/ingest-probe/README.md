# 阿里云 FC 读取探测

通过用户指定的 `bilibili-api-zoku==17.4.4` 验证原生 Linux 网络客户端。

结果见 [FC 验证记录](../../docs/ALIBABA-FC-PROBE.md)。逐项证据见 [验证清单](../../docs/alibaba-fc-probe/2026-11-04.json)。

## 实现

`index.py` 使用 SDK 的 `CurlCFFIClient`，子类仅记录请求路径、状态、哈希和脱敏错误，附加固定域名及只读策略。API、WBI、BUVID、ticket 与 `Credential` 均由 SDK 实现，无 CF 专用的 Crypto 命名空间兼容处理。

原始 11 个方法与样本和 CF 探测一致，测试逐项核对。额外的 `dynamic_feed_legacy` 调用 SDK 的 `User.get_dynamics()`，用作失败对照。它返回 404，不能作为当前有效的增量入口。

`profile=library` 使用原生库配置，`chrome` 设置库客户端的 `impersonate=chrome`、`http2=true`。每次探测清除客户端 Cookie 并刷新 SDK 缓存，区分 `sessdata` 与 `anonymous`。库日志关闭，成功正文仅返回结构摘要与哈希。失败正文脱敏后最多返回 2000 字符。

单个请求超时 18 秒，一次探测最多 8 个请求，库调用总超时 55 秒。原生客户端完整缓冲响应后拒绝使用超过 2 MiB 的正文，不作流式截断。只允许固定 HTTPS 域名的 GET，以及库的设备激活和 ticket 两个前置 POST，不跟随重定向。字幕 CDN 不接收账号 Cookie。

## 构建与创建

从仓库根目录执行。依赖版本固定在 `requirements.lock.txt`，构建目标为 Linux x86_64、Python 3.12。二维码 wheel 与 CF 构建共享，来源见 [wheel 说明](../../workers/ingest-probe/vendor-wheels/README.md)。

```powershell
python -X utf8 tools/build_alibaba_fc_probe.py --output .cache/alibaba-probe/new-build
```

控制工具使用官方 `alibabacloud-fc20230330==4.8.4` SDK。默认读取本机 Workbench 当前授权，可通过 `--credentials` 指定同结构配置文件。账户 ID 使用实际查询结果替换 `<ACCOUNT_ID>`。

```powershell
uv run --no-project --with alibabacloud-fc20230330==4.8.4 python -X utf8 tools/probe_alibaba_fc.py deploy --account <ACCOUNT_ID> --function <NEW_FUNCTION_NAME> --output .cache/alibaba-probe/new-deploy --zip .cache/alibaba-probe/new-build/function.zip
```

创建时通过隐藏输入读取 SESSDATA，写入函数环境变量。不要把凭据加入命令参数。工具拒绝覆盖同名函数及已有输出目录。新函数使用 512 MiB、0.5 vCPU、90 秒超时、300 秒空闲超时；不创建 HTTP 或定时触发器、预留实例、RAM 角色或其他云资源。

## 已有函数调用

本次函数名称为 `weimingzi-ingest-probe-20261104`，地域为 `cn-hangzhou`，代码修订为 `probe-fc-zoku-v2`。先进行健康检查与修订核对，再保存逐项证据：

```powershell
uv run --no-project --with alibabacloud-fc20230330==4.8.4 python -X utf8 tools/probe_alibaba_fc.py probe --account <ACCOUNT_ID> --profile chrome --output .cache/alibaba-probe/new-run
```

`--targets` 限定读取目标，`--authentication anonymous` 做匿名对照。`--page 2 --targets videos articles` 验证第二页；仅允许页码 1、2，避免意外全量抓取。各批调用应串行执行。

控制工具使用 RAM 签名调用 FC，没有额外的公开 URL 或 PROBE_TOKEN。`--output` 每次必须取新目录。`describe` 只保存环境变量名，不输出值。`update` 仅更新代码，必须提供 `--zip` 与匹配远端现状的 `--expected-checksum`，保留已有环境变量与配置。

FC HTTP 200 表示调用返回证据。还需检查 `ok`、`stage`、`business_request_sent` 与结构摘要。视频列表的风险占位或空页不计为成功发现，列表首页成功也不代表后续分页成功。当前视频第 2 页和动态列表仍受阻，详见验证记录。

## 本地测试

从本目录执行：

```powershell
uv run --no-project --with bilibili-api-zoku==17.4.4 --with curl-cffi==0.17.0 python -X utf8 -m unittest -v test_probe
```

测试在原生客户端边界模拟 HTTP 响应，执行实际 SDK 的视频、WBI 和字幕方法，不访问生产上游。仓库原有测试仍从根目录运行 `python -X utf8 -m unittest discover -s tests -v`。
