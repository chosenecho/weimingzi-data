"""Authenticated FC event probe using zoku and its native CurlCFFIClient."""

import asyncio
from contextvars import ContextVar
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
import platform
from urllib.parse import unquote, urlsplit

from bilibili_api import (
    BILIBILI_API_VERSION, Credential, article, dynamic, get_client, opus,
    recalculate_wbi, refresh_bili_ticket, refresh_buvid, register_client,
    request_log, request_settings, user, video,
)
from bilibili_api.clients.CurlCFFIClient import CurlCFFIClient
from bilibili_api.utils.utils import get_api

REVISION = 'probe-fc-zoku-v2'
assert BILIBILI_API_VERSION == '17.4.4'
LIBRARY = {'name': 'bilibili-api-zoku', 'version': BILIBILI_API_VERSION,
           'upstream_commit': 'a0a1566c7c462ab57a3891c3a5f12976cbd11e9e',
           'transport': 'EvidenceClient(CurlCFFIClient)',
           'curl_cffi_version': importlib.metadata.version('curl-cffi')}
SAMPLE = {'uid': 23191782, 'bvid': 'BV1S8hA6MEvy', 'cid': 41314223900,
          'dynamic_id': 1266215019584946198, 'cvid': 18927433,
          'opus_id': 713245238842359833}
TARGETS = {
    'nav': ('Credential.check_valid', 'credential', 'valid'),
    'videos': ('User.get_videos', 'user', 'video'),
    'video': ('Video.get_info', 'video', 'info'),
    'parts': ('Video.get_pages', 'video', 'pages'),
    'dynamic_feed': ('User.get_dynamics_new', 'user', 'dynamic_new'),
    'dynamic': ('Dynamic.get_info', 'dynamic', 'detail'),
    'articles': ('User.get_articles', 'user', 'article'),
    'article': ('Article.get_info', 'article', 'view'),
    'article_content': ('Article.fetch_content', 'article', 'detail'),
    'opus': ('Opus.get_info / Opus.markdown', 'opus', 'detail'),
    'subtitles': ('Video.get_subtitle', 'video', 'get_player_info'),
    'dynamic_feed_legacy': ('User.get_dynamics', 'user', 'dynamic'),
}
COOKIE_HOSTS = {'api.bilibili.com', 'api.vc.bilibili.com', 'www.bilibili.com', 'space.bilibili.com'}
BOOTSTRAP_POSTS = {
    ('api.bilibili.com', '/x/internal/gaia-gateway/ExClimbWuzhi'),
    ('api.bilibili.com', '/bapis/bilibili.api.ticket.v1.Ticket/GenWebTicket'),
}
CURRENT = ContextVar('fc_probe', default=None)


def redact(value):
    value = str(value)
    secret = os.environ.get('BILIBILI_SESSDATA', '')
    for item in (secret, unquote(secret)):
        if item:
            value = value.replace(item, '[redacted]')
    return value


def validate_url(method, url):
    parsed = urlsplit(url)
    host = (parsed.hostname or '').lower()
    if (parsed.scheme != 'https' or parsed.username or parsed.password
            or parsed.port not in (None, 443)
            or not (host in COOKIE_HOSTS or host.endswith('.hdslb.com'))):
        raise ValueError('Upstream URL is outside the probe allowlist')
    if method != 'GET' and not (method == 'POST' and (host, parsed.path) in BOOTSTRAP_POSTS):
        raise ValueError('Only reads and SDK device/ticket bootstrap are allowed')
    return parsed


class EvidenceClient(CurlCFFIClient):
    async def request(self, method='', url='', params=None, data=None,
                      files=None, headers=None, cookies=None, allow_redirects=True):
        context = CURRENT.get()
        if context is None:
            raise RuntimeError('No active protected probe')
        parsed = validate_url(method.upper(), url)
        if files or len(context) >= 8:
            raise ValueError('Upload or request budget exceeded')
        headers = {k: v for k, v in (headers or {}).items() if k.lower() != 'cookie'}
        cookies = dict(cookies or {}) if parsed.hostname in COOKIE_HOSTS else {}
        record = {'method': method.upper(), 'url': parsed._replace(query='', fragment='').geturl(),
                  'query_keys': sorted((params or {}).keys()),
                  'credential_attached': bool(cookies.get('SESSDATA'))}
        context.append(record)
        try:
            response = await super().request(
                method=method, url=url, params=params or {}, data=data or {},
                files={}, headers=headers, cookies=cookies, allow_redirects=False)
            raw = response.raw
            record.update(http_status=response.code, body_bytes=len(raw),
                          body_sha256=hashlib.sha256(raw).hexdigest())
            try:
                document = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                document = None
            if isinstance(document, dict):
                record['api_code'] = document.get('code')
                record['api_message'] = redact(document.get('message', document.get('msg', '')))[:500]
            if response.code != 200 or (isinstance(document, dict) and document.get('code') not in (None, 0)):
                record['error_body_excerpt'] = redact(raw.decode('utf-8', errors='replace'))[:2000]
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError('Buffered upstream response exceeds 2 MiB')
            return response
        except Exception as error:
            record['fetch_error'] = redact(error)[:500] or type(error).__name__
            raise


register_client('fc-evidence-curl', EvidenceClient, {'impersonate': '', 'http2': False})
request_log.set_on(False)
request_settings.set_timeout(18)
request_settings.set_trust_env(False)
LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(LOOP)


def primary_path(target):
    _, module, key = TARGETS[target]
    return urlsplit(get_api(module)['info'][key]['url']).path


async def library_call(target, credential, page=1):
    uploader = user.User(SAMPLE['uid'], credential=credential)
    v = video.Video(bvid=SAMPLE['bvid'], credential=credential)
    if target == 'nav':
        return {'logged_in': await credential.check_valid()}
    if target == 'videos':
        return await uploader.get_videos(pn=page, ps=5)
    if target == 'video':
        return await v.get_info()
    if target == 'parts':
        return await v.get_pages()
    if target == 'dynamic_feed':
        return await uploader.get_dynamics_new()
    if target == 'dynamic_feed_legacy':
        return await uploader.get_dynamics()
    if target == 'dynamic':
        return await dynamic.Dynamic(SAMPLE['dynamic_id'], credential=credential).get_info()
    if target == 'articles':
        return await uploader.get_articles(pn=page, ps=5)
    if target == 'article':
        return await article.Article(SAMPLE['cvid'], credential=credential).get_info()
    if target == 'article_content':
        a = article.Article(SAMPLE['cvid'], credential=credential)
        await a.fetch_content()
        return {'markdown': a.markdown()}
    if target == 'opus':
        o = opus.Opus(SAMPLE['opus_id'], credential=credential)
        return {'info': await o.get_info(), 'markdown': await o.markdown()}
    if target == 'subtitles':
        metadata = await v.get_subtitle(cid=SAMPLE['cid'])
        tracks = (metadata or {}).get('subtitles', [])
        if not tracks:
            return {'track_count': 0, 'body_status': 'no_tracks_in_response'}
        url = tracks[0].get('subtitle_url', '')
        if url.startswith('//'):
            url = 'https:' + url
        response = await get_client().request(method='GET', url=url)
        if response.code != 200:
            raise RuntimeError('Subtitle body HTTP failure')
        body = response.json().get('body')
        if not isinstance(body, list) or not body or not any(str(cue.get('content', '')).strip() for cue in body):
            return {'track_count': len(tracks), 'body_status': 'unusable_source_body'}
        return {'track_count': len(tracks), 'cue_count': len(body), 'body_status': 'usable'}
    raise ValueError('Unknown target')


def summarize(target, value):
    if target == 'nav':
        return {'logged_in': value['logged_in'], 'login_status_verified': isinstance(value['logged_in'], bool)}
    if target == 'subtitles':
        return value
    if target == 'videos':
        rows = (value.get('list') or {}).get('vlist')
        challenged = value.get('is_risk') is True or value.get('gaia_res_type') not in (None, 0)
        status = 'risk_challenge' if challenged else ('usable' if isinstance(rows, list) and rows else 'empty_or_unusable_page')
        return {'item_count': len(rows) if isinstance(rows, list) else None,
                'sample_bvids': [r.get('bvid') for r in (rows or [])],
                'page': value.get('page'), 'is_risk': value.get('is_risk'),
                'gaia_res_type': value.get('gaia_res_type'), 'source_status': status}
    if target == 'articles':
        rows = value.get('articles')
        return {'item_count': len(rows) if isinstance(rows, list) else None,
                'sample_cvids': [r.get('id') for r in (rows or [])],
                'count': value.get('count'), 'page': value.get('pn')}
    if target in ('dynamic_feed', 'dynamic_feed_legacy'):
        rows = value.get('items' if target == 'dynamic_feed' else 'cards')
        return {'item_count': len(rows) if isinstance(rows, list) else None,
                'has_more': value.get('has_more'), 'offset': value.get('offset', value.get('next_offset'))}
    if target == 'video':
        return {'bvid': value.get('bvid'), 'page_count': len(value.get('pages') or []), 'duration': value.get('duration')}
    if isinstance(value, list):
        return {'item_count': len(value)}
    if isinstance(value, dict):
        out = {'result_keys': sorted(value)}
        if isinstance(value.get('markdown'), str):
            out['markdown_characters'] = len(value['markdown'])
        return out
    return {'result_type': type(value).__name__}


async def run_probe(target, authentication, profile, page=1):
    secret = os.environ.get('BILIBILI_SESSDATA', '') if authentication == 'sessdata' else ''
    if authentication == 'sessdata' and (not secret or any(c in secret for c in '\r\n; ')):
        return {'ok': False, 'error': 'sessdata_secret_missing_or_invalid'}
    refresh_buvid()
    refresh_bili_ticket()
    recalculate_wbi()
    request_settings.set('impersonate', 'chrome' if profile == 'chrome' else '')
    request_settings.set('http2', profile == 'chrome')
    client = get_client()
    client.get_wrapped_session().cookies.clear()
    requests = []
    token = CURRENT.set(requests)
    out = {'revision': REVISION, 'library': LIBRARY, 'target': target,
           'library_call': TARGETS[target][0], 'profile': profile,
           'authentication': authentication, 'page': page, 'sample': SAMPLE,
           'started_at': datetime.now(timezone.utc).isoformat(), 'requests': requests}
    try:
        async with asyncio.timeout(55):
            value = await library_call(target, Credential(sessdata=secret or None), page)
        summary = summarize(target, value)
        out.update(ok=summary.get('source_status') not in ('risk_challenge', 'empty_or_unusable_page'), summary=summary)
    except Exception as error:
        out.update(ok=False, library_error={'type': type(error).__name__, 'message': redact(error)[:1000]})
        if target == 'nav':
            out['summary'] = {'logged_in': None, 'login_status_verified': False}
    finally:
        CURRENT.reset(token)
    out['business_request_sent'] = any(urlsplit(r['url']).path == primary_path(target) for r in requests)
    out['stage'] = 'completed' if out['ok'] else ('business_response_unusable' if 'summary' in out and target == 'videos' else ('business_request_failed' if out['business_request_sent'] else 'dependency_blocked'))
    out['finished_at'] = datetime.now(timezone.utc).isoformat()
    return out


def handler(event, context):
    if isinstance(event, (bytes, str)):
        event = json.loads(event)
    if not isinstance(event, dict):
        return json.dumps({'ok': False, 'error': 'invalid_event'})
    if event.get('action') == 'health':
        return json.dumps({'ok': True, 'revision': REVISION, 'library': LIBRARY,
                           'python': platform.python_version(), 'platform': platform.platform(),
                           'scheduled': False, 'targets': list(TARGETS)})
    target = event.get('target')
    authentication = event.get('authentication', 'sessdata')
    profile = event.get('profile', 'library')
    page = event.get('page', 1)
    if not isinstance(target, str) or target not in TARGETS or authentication not in ('sessdata', 'anonymous') or profile not in ('library', 'chrome') or type(page) is not int or page not in (1, 2):
        return json.dumps({'ok': False, 'error': 'invalid_probe_parameters'})
    return json.dumps(LOOP.run_until_complete(run_probe(target, authentication, profile, page)), ensure_ascii=False)
