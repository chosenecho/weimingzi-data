"""Protected Python Worker entrypoint using bilibili-api-zoku."""

import hmac
from urllib.parse import parse_qs, urlsplit

from workers import Response, WorkerEntrypoint
from settings import LIBRARY, REVISION, TARGETS

import crypto_compat
crypto_compat.install()
from probe import run_probe


def reply(data, status=200):
    return Response.from_json(data, status=status, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        parsed = urlsplit(request.url)
        method = str(request.method.value)
        if parsed.path == "/health" and method == "GET":
            return reply({"ok": True, "revision": REVISION, "library": LIBRARY, "scheduled": False, "targets": list(TARGETS)})
        if parsed.path != "/probe":
            return reply({"error": "not_found"}, 404)
        if method != "POST":
            return reply({"error": "method_not_allowed"}, 405)
        expected = str(getattr(self.env, "PROBE_TOKEN", ""))
        if not expected or not hmac.compare_digest(request.headers.get("Authorization", ""), "Bearer " + expected):
            return reply({"error": "unauthorized"}, 401)
        query = parse_qs(parsed.query)
        target = query.get("target", [""])[0]
        profile = query.get("profile", ["library"])[0]
        # Older caller's 'browser' means use zoku's own HEADERS unchanged.
        if profile == "browser":
            profile = "library"
        authentication = query.get("authentication", ["sessdata"])[0]
        if target not in TARGETS or profile not in ("library", "plain") or authentication not in ("sessdata", "anonymous"):
            return reply({"error": "invalid_probe_parameters"}, 400)
        sessdata = ""
        if authentication == "sessdata":
            sessdata = str(getattr(self.env, "BILIBILI_SESSDATA", ""))
            if not sessdata or any(c in sessdata for c in "\r\n; "):
                return reply({"error": "sessdata_secret_missing_or_invalid"}, 503)
        result = await run_probe(target, sessdata, profile, authentication)
        return reply(result)
