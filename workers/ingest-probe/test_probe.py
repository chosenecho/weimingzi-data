"""Exercise the real pinned zoku library with a mocked Fetch boundary."""

import json
from pathlib import Path
import sys
import subprocess
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).parent / "src"))

import cf_client
from cf_client import CURRENT_PROBE, CloudflareFetchClient, ProbeContext, prepare_request
from probe import TARGETS, primary_path, run_probe


class PolicyTests(unittest.TestCase):
    def test_lazy_crypto_remains_real_implementation(self):
        code = """
import sys, importlib.util, hashlib
sys.path.insert(0, 'src')
import crypto_compat
crypto_compat.defer_crypto()
import bilibili_api
assert bilibili_api.BILIBILI_API_VERSION == '17.4.4'
assert type(sys.modules['Cryptodome.PublicKey.ECC']) is importlib.util._LazyModule
from Cryptodome.Hash import SHA256
assert SHA256.new(b'test').hexdigest() == hashlib.sha256(b'test').hexdigest()
"""
        subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).parent, check=True, capture_output=True)

    def test_primary_paths_come_from_library(self):
        for target in TARGETS:
            self.assertTrue(primary_path(target).startswith("/"))
        self.assertEqual(primary_path("subtitles"), "/x/player/wbi/v2")

    def test_encoded_sessdata_preserved(self):
        _, _, headers, _, attached = prepare_request("GET", "https://api.bilibili.com/test", {}, {}, {"SESSDATA": "test%2Cvalue"}, {})
        self.assertTrue(attached)
        self.assertEqual(headers["Cookie"], "SESSDATA=test%2Cvalue")

    def test_cdn_cannot_receive_cookies(self):
        _, _, headers, _, attached = prepare_request("GET", "https://aisubtitle.hdslb.com/test", {}, {"Cookie": "opaque"}, {"SESSDATA": "private"}, {})
        self.assertFalse(attached)
        self.assertNotIn("Cookie", headers)

    def test_untrusted_urls_rejected(self):
        for url in ["http://api.bilibili.com/x", "https://api.bilibili.com.evil.test/x", "https://api.bilibili.com@evil.test/x", "https://api.bilibili.com:444/x", "https://example.com/x"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                prepare_request("GET", url, {}, {}, {}, {})

    def test_account_mutations_rejected(self):
        with self.assertRaises(ValueError):
            prepare_request("POST", "https://api.bilibili.com/x/web-interface/archive/like", {}, {}, {}, {})


class LibraryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.sent = []

    async def good_fetch(self, url, **options):
        self.sent.append((url, options))
        self.assertEqual(options["redirect"], "manual")
        path = urlsplit(url).path
        if path.endswith("/spi"):
            data = {"b_3": "device3", "b_4": "device4"}
        elif path.endswith("ExClimbWuzhi"):
            data = {}
        elif path.endswith("GenWebTicket"):
            data = {"ticket": "ticket"}
        elif path.endswith("/nav"):
            data = {"isLogin": True, "wbi_img": {"img_url": "https://i.test/" + "a" * 32 + ".png", "sub_url": "https://i.test/" + "b" * 32 + ".png"}}
        elif path.endswith("/v2"):
            data = {"subtitle": {"subtitles": [{"subtitle_url": "https://aisubtitle.hdslb.com/body.json"}]}}
        elif path.endswith("body.json"):
            return 200, {}, json.dumps({"body": [{"from": 0, "to": 1, "content": "test"}]}).encode(), False
        else:
            data = {"bvid": "BV1S8hA6MEvy", "title": "sample"}
        return 200, {}, json.dumps({"code": 0, "msg": "ok", "data": data}).encode(), False

    async def test_real_video_method_and_device_bootstrap(self):
        with patch("cf_client.fetch_bounded", self.good_fetch):
            result = await run_probe("video", "test%2Cvalue")
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["business_request_sent"])
        self.assertTrue(any("/spi" in url for url, _ in self.sent))
        video_requests = [options for url, options in self.sent if urlsplit(url).path == primary_path("video")]
        self.assertIn("SESSDATA=test%2Cvalue", video_requests[0]["headers"]["Cookie"])
        self.assertIn("buvid3=device3", video_requests[0]["headers"]["Cookie"])

    async def test_real_library_wbi_and_subtitle_body(self):
        with patch("cf_client.fetch_bounded", self.good_fetch):
            result = await run_probe("subtitles", "test%2Cvalue")
        self.assertTrue(result["ok"], result)
        player_url = next(url for url, _ in self.sent if urlsplit(url).path == primary_path("subtitles"))
        query = parse_qs(urlsplit(player_url).query)
        self.assertIn("w_rid", query)
        self.assertIn("wts", query)
        cdn_options = next(options for url, options in self.sent if url.endswith("body.json"))
        self.assertNotIn("Cookie", cdn_options["headers"])
        self.assertEqual(result["summary"]["body_status"], "usable")

    async def test_412_is_dependency_failure_and_login_unknown(self):
        async def blocked(url, **options):
            return 412, {}, b'{"code":-412,"message":"request was banned","ttl":1}', False
        with patch("cf_client.fetch_bounded", blocked):
            result = await run_probe("nav", "test%2Cvalue")
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "dependency_blocked")
        self.assertFalse(result["business_request_sent"])
        self.assertIsNone(result["summary"]["logged_in"])
        self.assertEqual(result["requests"][0]["api_code"], -412)

    async def test_anonymous_mode_has_no_sessdata(self):
        with patch("cf_client.fetch_bounded", self.good_fetch):
            result = await run_probe("video", "", authentication="anonymous")
        self.assertTrue(result["ok"], result)
        for _, options in self.sent:
            self.assertNotIn("SESSDATA=test", options["headers"].get("Cookie", ""))
        self.assertFalse(any(item["credential_attached"] for item in result["requests"]))

    async def test_error_evidence_redacts_cookie(self):
        async def echo(url, **options):
            return 412, {}, b'{"message":"test%2Cvalue test,value"}', False
        with patch("cf_client.fetch_bounded", echo):
            result = await run_probe("video", "test%2Cvalue")
        serialized = json.dumps(result)
        self.assertNotIn("test%2Cvalue", serialized)
        self.assertNotIn("test,value", serialized)

    async def test_truncated_responses_not_used(self):
        context = ProbeContext()
        token = CURRENT_PROBE.set(context)
        async def truncated(url, **options):
            return 200, {}, b"{}", True
        try:
            with patch("cf_client.fetch_bounded", truncated), self.assertRaises(ValueError):
                await CloudflareFetchClient().request("GET", "https://api.bilibili.com/test")
            self.assertTrue(context.requests[0]["truncated"])
        finally:
            CURRENT_PROBE.reset(token)


if __name__ == "__main__":
    unittest.main()
