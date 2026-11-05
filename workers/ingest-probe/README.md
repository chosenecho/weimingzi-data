# Cloudflare 增量采集探测

通过用户指定的 `bilibili-api-zoku==17.4.4` 验证 Python Worker 的读取能力。当前部署为 `probe-zoku-v9`，尚未接入增量入库。

实测结论见 [部署验证记录](../../docs/CLOUDFLARE-PROBE.md)。逐项证据见 [zoku 验证清单](../../docs/cloudflare-probe/2026-11-04-zoku.json)。

## 库与运行时

入口为 `src/entry.py`，业务调用在 `src/probe.py`。视频、分 P、动态、专栏、opus、字幕元数据通过库的公开方法读取，`Credential`、WBI、BUVID 和 ticket 处理沿用库实现。`CloudflareFetchClient` 通过库的 `register_client` 接口接入 Workers `fetch`，只适配网络传输。它不提供 `curl_cffi` 的 TLS 指纹模拟。

版本与来源固定在 `pyproject.toml`、`pylock.toml` 和 `src/settings.py`。本次比较安装包与上游提交 `a0a1566c7c462ab57a3891c3a5f12976cbd11e9e`：99 个 Python 文件、52 个 JSON 文件全部相同，详见验证清单。

Pyodide 使用 `pycryptodome` 的 `Crypto` 命名空间，库使用 `Cryptodome`。`src/crypto_compat.py` 仅在该运行时建立别名，并用标准 `LazyLoader` 延后加载未使用的登录加密模块，避免将其 FFI 句柄放进启动快照。没有替换加密函数或修改 SDK。测试验证了延迟模块仍执行真实 SHA-256 实现。二维码依赖的本地 wheel 来源与哈希见 [vendor-wheels 说明](vendor-wheels/README.md)。

## 接口

- `GET /health`：公开健康检查，返回代码修订、已加载的库版本和固定目标。库导入或版本断言失败时无法返回正常健康结果。
- `POST /probe?target=video&profile=library&authentication=sessdata`：需要 `Authorization: Bearer <PROBE_TOKEN>`。

固定目标为 `nav`、`videos`、`video`、`parts`、`dynamic_feed`、`dynamic`、`articles`、`article`、`article_content`、`opus`、`subtitles`。样本标识来自仓库已有条目，定义在 `src/settings.py`。

`profile=library` 保留库的请求头，`browser` 是其兼容别名。`plain` 移除 Referer 并改用应用 User-Agent，仅用于对照。默认 `authentication=sessdata` 使用远端 `BILIBILI_SESSDATA` Secret；`anonymous` 构造无 SESSDATA 的 `Credential`。

单次上游请求超时为 18 秒，一次探测最多 8 个上游请求，库调用总超时为 55 秒。响应读取上限为 2 MiB；超限后取消读取并报错。探测串行执行，并在每次调用前重置库的设备、ticket 和 WBI 缓存，避免不同认证模式共用这些缓存。

仅允许 HTTPS 的 `api.bilibili.com`、`www.bilibili.com`、`space.bilibili.com` 及 `*.hdslb.com`。Cookie 只可附加到前三个明确域名，不自动跟随重定向。除 GET 外，仅允许库的设备激活和 ticket 两个前置 POST；不开放任意 URL、账号修改、上传、下载或 WebSocket。

探测没有 Cron、D1、R2 或 GitHub 写入配置。`PROBE_TOKEN` 和 `BILIBILI_SESSDATA` 使用 Cloudflare Secret。SESSDATA 不写入代码、日志或证据。库的公共设备前置请求可能不携带 SESSDATA；以每条请求的 `credential_attached` 为准。

## 部署

本次使用 Wrangler 4.156.0、workers-py 1.17.9，以及单独提供的 uv 0.13.4。先登录 Wrangler，按目标账户调整 `wrangler.jsonc`，然后从本目录执行：

```powershell
uvx --with uv==0.13.4 --from workers-py==1.17.9 pywrangler sync
uvx --with uv==0.13.4 --from workers-py==1.17.9 pywrangler deploy
wrangler secret put PROBE_TOKEN --config wrangler.jsonc
wrangler secret put BILIBILI_SESSDATA --config wrangler.jsonc
```

两个 Secret 均通过交互式标准输入提供，不放入命令参数。后续部署保留远端 Secret。本次账户为 Free，配置中没有自定义 CPU 限额，也没有调整套餐。

若依赖下载需要本机代理，仅在同步进程设置 `HTTPS_PROXY`、`HTTP_PROXY`。部署配置不会因此给 Worker 的上游请求添加代理。

## 复跑与测试

客户端读取 Git 忽略的 `.cache/cloudflare-probe/secrets.json`，文件只需包含与远端一致的 `PROBE_TOKEN`。从仓库根目录执行，输出目录每次取新名称：

```powershell
python -X utf8 tools/probe_cloudflare.py --url https://weimingzi-ingest-probe-20261104.jiqimao123456.workers.dev --secrets .cache/cloudflare-probe/secrets.json --output .cache/cloudflare-probe/new-run --expected-revision probe-zoku-v9
```

需要本机代理时追加 `--proxy http://127.0.0.1:10808`；它只影响客户端到 Worker。匿名对照追加 `--authentication anonymous --targets video dynamic_feed subtitles`。

客户端先保存健康检查并核对修订，再发出探测。已有证据不会覆盖。每项结果保留 Worker 响应 JSON 封装、原响应 SHA-256，以及上游请求路径、Cookie 附加状态、响应状态和正文哈希。成功正文仅保留结构摘要；失败正文仅保留经脱敏的前 2000 字符。正文哈希针对实际读取字节，不能用截短的摘录重新计算。

HTTP 200 表示探测返回了证据。采集是否完成还需检查 `ok`、`stage`、`business_request_sent` 和每条上游请求。`dependency_blocked` 表示业务请求未发出，不能记为没有新增数据。`nav` 失败时会话有效性未知；字幕前置失败不证明没有字幕或音频静音。

本目录的传输与库调用测试：

```powershell
.\.venv-workers\Scripts\python.exe -X utf8 -m unittest -v test_probe
```

仓库根目录的既有回归测试：

```powershell
python -X utf8 -m unittest discover -s tests -v
```
