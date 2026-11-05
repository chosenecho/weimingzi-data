"""Exercise FC entrypoint and actual zoku calls at the native client boundary."""

import ast
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

import index
from bilibili_api import BiliAPIResponse


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {'BILIBILI_SESSDATA': 'test%2Cvalue'})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.sent = []

    def run_target(self, target, authentication='sessdata', profile='library'):
        return json.loads(index.handler(json.dumps(dict(target=target, authentication=authentication, profile=profile)), None))

    async def good_request(client, method='', url='', params=None, **options):
        path = urlsplit(url).path
        if path.endswith('/spi'):
            data = {'b_3': 'device3', 'b_4': 'device4'}
        elif path.endswith('ExClimbWuzhi'):
            data = {}
        elif path.endswith('GenWebTicket'):
            data = {'ticket': 'ticket'}
        elif path.endswith('/nav'):
            data = {'isLogin': True, 'wbi_img': {'img_url': 'https://i.test/'+'a'*32+'.png', 'sub_url': 'https://i.test/'+'b'*32+'.png'}}
        elif path.endswith('/v2'):
            data = {'subtitle': {'subtitles': [{'subtitle_url': 'https://aisubtitle.hdslb.com/body.json'}]}}
        elif path.endswith('body.json'):
            return BiliAPIResponse(code=200, headers={}, cookies={}, raw=b'{"body":[{"content":"test"}]}', url=url)
        else:
            data = {'bvid': 'BV1S8hA6MEvy', 'title': 'sample'}
        return BiliAPIResponse(code=200, headers={}, cookies={}, raw=json.dumps({'code': 0, 'data': data}).encode(), url=url)

    def test_health_loads_pinned_sdk(self):
        result = json.loads(index.handler(b'{"action":"health"}', None))
        self.assertTrue(result['ok'])
        self.assertEqual(result['library']['version'], '17.4.4')
        self.assertEqual(len(result['targets']), 12)
        self.assertNotIn('test%2Cvalue', json.dumps(result))

    def test_invalid_events_rejected(self):
        for target in ['constructor', [], None]:
            self.assertEqual(self.run_target(target)['error'], 'invalid_probe_parameters')

    def test_same_sample_and_methods_as_cf(self):
        path = Path(__file__).resolve().parents[2]/'workers/ingest-probe/src/settings.py'
        tree = ast.parse(path.read_text())
        for name in ['SAMPLE', 'TARGETS']:
            node = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in n.targets))
            actual = getattr(index, name)
            if name == 'TARGETS':
                actual = {k: v for k, v in actual.items() if k != 'dynamic_feed_legacy'}
            self.assertEqual(ast.literal_eval(node.value), actual)

    def test_url_and_mutation_policy(self):
        for method, url in [('GET', 'http://api.bilibili.com/x'), ('GET', 'https://api.bilibili.com.evil.test/x'), ('GET', 'https://api.bilibili.com:444/x'), ('POST', 'https://api.bilibili.com/x/web-interface/archive/like')]:
            with self.assertRaises(ValueError):
                index.validate_url(method, url)

    def test_real_library_video(self):
        with patch.object(index.CurlCFFIClient, 'request', self.good_request):
            result = self.run_target('video')
        self.assertTrue(result['ok'], result)
        self.assertTrue(result['business_request_sent'])
        self.assertTrue(any(r['url'].endswith('/spi') for r in result['requests']))
        business = next(r for r in result['requests'] if urlsplit(r['url']).path == index.primary_path('video'))
        self.assertTrue(business['credential_attached'])

    def test_real_wbi_and_subtitle_body(self):
        with patch.object(index.CurlCFFIClient, 'request', self.good_request):
            result = self.run_target('subtitles')
        self.assertTrue(result['ok'], result)
        player = next(r for r in result['requests'] if urlsplit(r['url']).path == index.primary_path('subtitles'))
        self.assertIn('w_rid', player['query_keys'])
        self.assertIn('wts', player['query_keys'])
        self.assertEqual(result['summary']['body_status'], 'usable')
        self.assertFalse(result['requests'][-1]['credential_attached'])

    def test_anonymous_does_not_attach_sessdata(self):
        with patch.object(index.CurlCFFIClient, 'request', self.good_request):
            result = self.run_target('video', authentication='anonymous')
        self.assertTrue(result['ok'], result)
        self.assertFalse(any(r['credential_attached'] for r in result['requests']))

    def test_bootstrap_failure_keeps_login_unknown_and_redacts(self):
        async def blocked(client, **options):
            return BiliAPIResponse(code=412, headers={}, cookies={}, raw=b'<html>test%2Cvalue test,value</html>', url=options['url'])
        with patch.object(index.CurlCFFIClient, 'request', blocked):
            result = self.run_target('nav')
        self.assertFalse(result['ok'])
        self.assertEqual(result['stage'], 'dependency_blocked')
        self.assertIsNone(result['summary']['logged_in'])
        self.assertNotIn('test%2Cvalue', json.dumps(result))
        self.assertNotIn('test,value', json.dumps(result))

    def test_chrome_profile_uses_upstream_transport_settings(self):
        with patch.object(index.CurlCFFIClient, 'request', self.good_request):
            result = self.run_target('video', profile='chrome')
        self.assertTrue(result['ok'], result)
        self.assertEqual(index.get_client().get_wrapped_session().impersonate, 'chrome')

    def test_video_risk_response_is_not_usable(self):
        summary = index.summarize('videos', {'is_risk': True, 'gaia_res_type': 1, 'list': {'vlist': []}})
        self.assertEqual(summary['source_status'], 'risk_challenge')
        self.assertEqual(summary['item_count'], 0)

    def test_video_list_counts_real_rows(self):
        summary = index.summarize('videos', {'is_risk': False, 'gaia_res_type': 0, 'list': {'vlist': [{'bvid': 'BVtest'}]}, 'page': {'pn': 1}})
        self.assertEqual(summary['source_status'], 'usable')
        self.assertEqual(summary['item_count'], 1)

    def test_bounded_page_validation(self):
        result = json.loads(index.handler('{"target":"videos","page":3}', None))
        self.assertEqual(result['error'], 'invalid_probe_parameters')


if __name__ == '__main__':
    unittest.main()
