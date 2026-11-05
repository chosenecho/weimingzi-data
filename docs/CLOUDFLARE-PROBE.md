# Cloudflare Worker 采集验证

验证日期：2026-11-04，时区 Asia/Hong_Kong。当前结果以 [zoku 验证清单](cloudflare-probe/2026-11-04-zoku.json) 为准。

已将探测迁移为用户指定的 `bilibili-api-zoku==17.4.4` 并部署到 Cloudflare Python Worker。最终版本能够加载库并返回全部固定目标的探测证据；上游采集仍被 HTTP 412 阻断，尚未验证增量入库。

## 当前部署与实现

- Worker：`weimingzi-ingest-probe-20261104`
- 健康检查：<https://weimingzi-ingest-probe-20261104.jiqimao123456.workers.dev/health>
- 代码修订：`probe-zoku-v9`
- Cloudflare 版本：`98e388a1-7d79-4c22-8270-68e303c73ac3`
- SDK 对应上游提交：`a0a1566c7c462ab57a3891c3a5f12976cbd11e9e`
- 配置、接口和复跑命令：[探测 Worker](../workers/ingest-probe/README.md)

业务调用、凭据、WBI 和设备前置处理由库执行。自定义 `CloudflareFetchClient` 只把库的传输接口接到 Workers `fetch`，不具备 `curl_cffi` 的 TLS 指纹模拟能力。安装包的 99 个 Python 文件、52 个 JSON 文件与上述上游提交逐一比较，未发现差异；锁文件保存依赖版本与归档哈希。

当前实现为 Pyodide 的 Crypto 命名空间提供兼容别名，并延迟加载 SDK 导入链中未使用的登录加密模块。该处理使用真实模块与标准 `LazyLoader`，没有修改 SDK 或替换加密实现。此前的启动快照失败和请求内导入 CPU 超限，未在最终这批探测中再次出现。

## 最终实测

携带 SESSDATA 的 11 个目标均返回 Worker HTTP 200，但 `ok=false`、`stage=dependency_blocked`、`business_request_sent=false`。每项只执行了一个库的前置请求，均收到 B 站 HTTP 412 HTML 错误页。库随后抛出 `JSONDecodeError`；本次响应没有 JSON `api_code`。

| 库的前置请求 | 受阻目标 | SESSDATA 附加状态 |
| --- | --- | --- |
| spi | 会话、视频、分 P、opus | false，库的公共设备请求 |
| nav | 动态、专栏、字幕 | true |

spi 路径为 `/x/frontend/finger/spi`，nav 路径为 `/x/web-interface/nav`。两组分别包含 5 个和 6 个目标，详见清单中的逐项请求。不能把它们表述为 11 个业务接口均已发出并失败。

匿名对照执行了 `video`、`dynamic_feed`、`subtitles`。前两项分别在 spi、nav 收到同样的 HTTP 412，均未附加 SESSDATA。字幕项由库直接抛出 `CredentialNoSessdataException`，没有发出上游请求。最终两批合计 14 项库调用，13 个实际上游请求均为 HTTP 412。

`nav` 没有成功取得 `isLogin`，会话有效性仍未知，证据记录 `logged_in=null`、`login_status_verified=false`。播放器及字幕正文尚未读取，无法据此判断字幕是否存在、正文是否可用或音频是否静音。也不能把前置阻塞记为没有新增数据。

9 项部署访问检查全部符合预期：健康检查 200、未知路径 404、错误方法 405、缺失和错误令牌 401，以及未知目标、原型属性目标、错误 profile、错误认证模式 400。传输及真实 SDK 调用测试 12 项通过，既有仓库回归测试 41 项通过，记录见验证清单。

固定样本为上传者 `23191782`、视频 `BV1S8hA6MEvy`、CID `41314223900`、动态 `1266215019584946198`、专栏 `18927433` 和 opus `713245238842359833`，均取自仓库已有条目。

## 部署失败记录

早期 Python 版本曾在处理请求前返回 Cloudflare 1105。将整个 SDK 改为请求内导入后，健康检查通过，但探测触发 1102；tail 记录 `CpuLimitExceeded`，该次 CPU 时间为 2017 ms。此失败发生在库导入阶段，不能算作 B 站拒绝证据。

曾尝试配置更高 CPU 限额，Cloudflare 以错误码 100328 拒绝 Free 套餐的设置。该配置未部署，随后移除，没有升级套餐。中间修订的启动失败、CPU 超限及混合结果保留在清单的 `historical_attempts` 中；最终结论只统计 `probe-zoku-v9` 的两批探测。

## 历史手写请求与客户端连接

早先的手写 JavaScript 探测记录为 [匿名 fetch 清单](cloudflare-probe/2026-11-04.json)。携带凭据的记录见 [SESSDATA fetch 清单](cloudflare-probe/2026-11-04-sessdata.json)。其 HTTP 412 正文为 `{"code":-412,"message":"request was banned","ttl":1}`，不代表本次 SDK 调用收到相同正文。两份历史清单保持原样。

本机直连 workers.dev 曾连接超时，Python 默认 User-Agent 也曾得到 Cloudflare 1010。最终客户端使用显式应用 User-Agent 和本机 `127.0.0.1:10808` 代理到达 Worker。该代理只作用于客户端到 Worker；没有为 Worker 到 B 站的请求配置代理，也没有确定 B 站拒绝响应背后的具体规则。

## 证据与后续约束

验证清单保存最终两批的健康检查、逐项响应封装、响应哈希、上游路径与状态，以及 9 项访问检查。上游失败正文仅保存脱敏后前 2000 字符，SHA-256 针对实际读取的完整字节；摘录本身不足以复算该哈希。客户端接收的原始封装继续保存在 Git 忽略的 `.cache/cloudflare-probe/`，没有覆盖先前失败记录。

SESSDATA 仅通过标准输入配置为远端 `BILIBILI_SESSDATA` Secret；本地访问令牌使用忽略文件，验证清单不保存凭据值。探测未配置 Cron、D1、R2 或 GitHub 写入，未改动仓库语料。

当前证据支持“SDK 能在 Worker 运行”，尚不支持“Worker 能稳定直连采集”。接入增量调度、身份映射、合并和发布前，仍需先取得业务接口成功响应并验证分页与正文质量。若调整网络传输路径，应继续保留此 SDK，并独立验证新路径；不能仅凭本次 412 认定更换路径一定有效。

2026-11-04 后续完成了 [阿里云 FC 对照](ALIBABA-FC-PROBE.md)。该环境取得登录有效和多类业务读取成功的响应，视频分页及动态列表仍受阻；本页保留原 CF 结果。
