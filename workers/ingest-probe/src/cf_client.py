"""Only transport: zoku retains endpoint selection, WBI and device cookies."""

import asyncio
from contextvars import ContextVar
from dataclasses import dataclass, field
import hashlib
from http.cookies import SimpleCookie
import json
from urllib.parse import unquote, urlencode, urlsplit, urlunsplit

from bilibili_api import BiliAPIClient, BiliAPIResponse

MAX_BODY = 2 * 1024 * 1024
MAX_REQUESTS = 8
COOKIE_HOSTS = {"api.bilibili.com", "www.bilibili.com", "space.bilibili.com"}
BOOTSTRAP_POSTS = {
    ("api.bilibili.com", "/x/internal/gaia-gateway/ExClimbWuzhi"),
    ("api.bilibili.com", "/bapis/bilibili.api.ticket.v1.Ticket/GenWebTicket"),
}


@dataclass
class ProbeContext:
    sessdata: str = ""
    profile: str = "library"
    requests: list = field(default_factory=list)

    def redact(self, text):
        for secret in (self.sessdata, unquote(self.sessdata)):
            if secret:
                text = text.replace(secret, "[redacted]")
        return text


CURRENT_PROBE = ContextVar("zoku_probe", default=None)


def trusted_url(url):
    parsed = urlsplit(str(url))
    host = (parsed.hostname or "").lower()
    allowed = host in COOKIE_HOSTS or host.endswith(".hdslb.com")
    if parsed.scheme != "https" or not allowed or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Upstream URL is outside the probe allowlist")
    return parsed


def prepare_request(method, url, params, headers, cookies, data):
    parsed = trusted_url(url)
    method = method.upper()
    if method not in ("GET", "POST") or (method == "POST" and (parsed.hostname, parsed.path) not in BOOTSTRAP_POSTS):
        raise ValueError("Only reads and zoku's device/ticket bootstrap are allowed")
    query = urlencode(params or {}, doseq=True)
    url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "&".join(x for x in (parsed.query, query) if x), ""))
    # Never accept an opaque Cookie header or carry cookies to a subtitle CDN.
    outbound = {k: str(v) for k, v in (headers or {}).items() if k.lower() not in ("cookie", "host", "content-length")}
    allowed_cookies = cookies if parsed.hostname in COOKIE_HOSTS else {}
    for name, value in (allowed_cookies or {}).items():
        if any(c in str(name) + str(value) for c in "\r\n;"):
            raise ValueError("Unsafe cookie value")
    if allowed_cookies:
        outbound["Cookie"] = "; ".join(f"{k}={v}" for k, v in allowed_cookies.items() if v is not None)
    body = None
    if method == "POST":
        if isinstance(data, dict):
            body = urlencode(data, doseq=True)
            outbound.setdefault("Content-Type", "application/x-www-form-urlencoded")
        else:
            body = data
    return method, url, outbound, body, bool((allowed_cookies or {}).get("SESSDATA"))


async def fetch_bounded(url, **options):
    from workers import fetch

    response = await fetch(url, **options)
    headers = dict(response.headers.items())
    reader = response.body.getReader() if response.body is not None else None
    raw = bytearray()
    truncated = False
    if reader is not None:
        try:
            while True:
                chunk = await reader.read()
                if chunk.done:
                    break
                value = bytes(chunk.value.to_py())
                room = MAX_BODY - len(raw)
                raw.extend(value[:room])
                if len(value) > room:
                    truncated = True
                    await reader.cancel()
                    break
        finally:
            reader.releaseLock()
    return int(response.status), headers, bytes(raw), truncated


class CloudflareFetchClient(BiliAPIClient):
    def __init__(self, proxy="", timeout=18.0, verify_ssl=True, trust_env=True, session=None):
        self.set_proxy(proxy)
        self.set_verify_ssl(verify_ssl)
        self.set_timeout(timeout)

    def get_wrapped_session(self):
        return None

    def set_proxy(self, proxy=""):
        if proxy:
            raise ValueError("Cloudflare fetch does not use a socket proxy")

    def set_timeout(self, timeout=18.0):
        self.timeout = min(float(timeout or 18), 18.0)

    def set_verify_ssl(self, verify_ssl=True):
        if not verify_ssl:
            raise ValueError("TLS verification cannot be disabled")

    def set_trust_env(self, trust_env=True):
        pass

    async def request(self, method="", url="", params=None, data=None, files=None, headers=None, cookies=None, allow_redirects=True):
        context = CURRENT_PROBE.get()
        if context is None:
            raise RuntimeError("No active protected probe")
        if files:
            raise ValueError("Uploads are not supported by this read probe")
        if len(context.requests) >= MAX_REQUESTS:
            raise RuntimeError("Upstream request budget exceeded")
        method, url, headers, body, attached = prepare_request(method, url, params, headers, cookies, data)
        if context.profile == "plain":
            headers = {k: v for k, v in headers.items() if k.lower() not in ("referer", "user-agent")}
            headers["User-Agent"] = "weimingzi-data-zoku-probe/1.0"
        parsed = urlsplit(url)
        record = {
            "method": method,
            "url": urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", "")),
            "credential_attached": attached,
            "query_keys": sorted({part.split("=", 1)[0] for part in parsed.query.split("&") if part}),
        }
        context.requests.append(record)
        try:
            async with asyncio.timeout(self.timeout):
                status, response_headers, raw, truncated = await fetch_bounded(url, method=method, headers=headers, body=body, redirect="manual")
            record.update(http_status=status, body_bytes=len(raw), truncated=truncated, body_sha256=hashlib.sha256(raw).hexdigest())
            try:
                document = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                document = None
            if isinstance(document, dict):
                record["api_code"] = document.get("code")
                record["api_message"] = context.redact(str(document.get("message", document.get("msg", ""))))[:500]
            # Successful responses can include private nav data; return only hashes.
            if status != 200 or (isinstance(document, dict) and document.get("code") not in (None, 0)):
                record["error_body_excerpt"] = context.redact(raw.decode("utf-8", errors="replace"))[:2000]
            if truncated:
                raise ValueError("Upstream response exceeds 2 MiB")
            response_cookies = SimpleCookie()
            response_cookies.load(response_headers.get("set-cookie", ""))
            return BiliAPIResponse(code=status, headers=response_headers, cookies={k: v.value for k, v in response_cookies.items()}, raw=raw, url=url)
        except Exception as error:
            record["fetch_error"] = context.redact(str(error))[:500] or type(error).__name__
            raise

    async def close(self):
        pass

    async def _unsupported(self, *args, **kwargs):
        raise NotImplementedError("Downloads and WebSockets are outside this probe")

    download_create = download_chunk = download_close = _unsupported
    ws_create = ws_send = ws_recv = ws_close = _unsupported

    def download_content_length(self, cnt):
        raise NotImplementedError("Downloads are outside this probe")
