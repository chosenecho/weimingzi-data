"""Fixed sample reads through the user-specified bilibili-api-zoku library."""

import asyncio
from datetime import datetime, timezone
from urllib.parse import urlsplit

from bilibili_api import (
    BILIBILI_API_VERSION, Credential, article, dynamic, get_client, opus,
    recalculate_wbi, refresh_bili_ticket, refresh_buvid, register_client,
    request_log, request_settings, user, video,
)
from bilibili_api.utils.utils import get_api

from cf_client import CURRENT_PROBE, CloudflareFetchClient, ProbeContext
from settings import LIBRARY, REVISION, SAMPLE, TARGETS

if BILIBILI_API_VERSION != LIBRARY["version"]:
    raise RuntimeError("Unexpected bilibili-api-zoku version")

register_client("cloudflare-fetch", CloudflareFetchClient)
request_log.set_on(False)
request_settings.set_timeout(18.0)
LOCK = asyncio.Lock()


def primary_path(target):
    _, module, key = TARGETS[target]
    return urlsplit(get_api(module)["info"][key]["url"]).path


async def library_call(target, credential):
    uploader = user.User(SAMPLE["uid"], credential=credential)
    v = video.Video(bvid=SAMPLE["bvid"], credential=credential)
    if target == "nav":
        return {"logged_in": await credential.check_valid()}
    if target == "videos":
        return await uploader.get_videos(pn=1, ps=5)
    if target == "video":
        return await v.get_info()
    if target == "parts":
        return await v.get_pages()
    if target == "dynamic_feed":
        return await uploader.get_dynamics_new()
    if target == "dynamic":
        return await dynamic.Dynamic(SAMPLE["dynamic_id"], credential=credential).get_info()
    if target == "articles":
        return await uploader.get_articles(pn=1, ps=5)
    if target == "article":
        return await article.Article(SAMPLE["cvid"], credential=credential).get_info()
    if target == "article_content":
        a = article.Article(SAMPLE["cvid"], credential=credential)
        await a.fetch_content()
        return {"markdown": a.markdown()}
    if target == "opus":
        o = opus.Opus(SAMPLE["opus_id"], credential=credential)
        return {"info": await o.get_info(), "markdown": await o.markdown()}
    if target == "subtitles":
        metadata = await v.get_subtitle(cid=SAMPLE["cid"])
        tracks = (metadata or {}).get("subtitles", [])
        if not tracks:
            return {"track_count": 0, "body_status": "no_tracks_in_response"}
        url = tracks[0].get("subtitle_url", "")
        if url.startswith("//"):
            url = "https:" + url
        # Use the registered library client, with no account cookies on the CDN.
        response = await get_client().request(method="GET", url=url)
        if response.code != 200:
            raise RuntimeError("Subtitle body HTTP failure")
        body = response.json().get("body")
        if not isinstance(body, list) or not body or not any(str(cue.get("content", "")).strip() for cue in body):
            return {"track_count": len(tracks), "body_status": "unusable_source_body"}
        return {"track_count": len(tracks), "cue_count": len(body), "body_status": "usable"}
    raise ValueError("Unknown target")


def summarize(target, result):
    if target == "nav":
        return {"logged_in": result["logged_in"], "login_status_verified": isinstance(result["logged_in"], bool)}
    if isinstance(result, list):
        return {"item_count": len(result)}
    if isinstance(result, dict):
        if target == "subtitles":
            return result
        summary = {"result_keys": sorted(result.keys())}
        if isinstance(result.get("markdown"), str):
            summary["markdown_characters"] = len(result["markdown"])
        return summary
    return {"result_type": type(result).__name__}


async def run_probe(target, sessdata="", profile="library", authentication="sessdata"):
    context = ProbeContext(sessdata=sessdata, profile=profile)
    output = {"revision": REVISION, "library": LIBRARY, "target": target, "library_call": TARGETS[target][0], "profile": profile, "authentication": authentication, "sample": SAMPLE, "started_at": datetime.now(timezone.utc).isoformat(), "requests": context.requests}
    async with LOCK:
        # zoku caches these globally: reset between credential modes under a lock.
        refresh_buvid()
        refresh_bili_ticket()
        recalculate_wbi()
        token = CURRENT_PROBE.set(context)
        try:
            async with asyncio.timeout(55):
                value = await library_call(target, Credential(sessdata=sessdata or None))
            output.update(ok=True, summary=summarize(target, value))
        except Exception as error:
            output.update(ok=False, library_error={"type": type(error).__name__, "message": context.redact(str(error))[:1000]})
            if target == "nav":
                output["summary"] = {"logged_in": None, "login_status_verified": False}
        finally:
            CURRENT_PROBE.reset(token)
    path = primary_path(target)
    output["business_request_sent"] = any(urlsplit(item["url"]).path == path for item in context.requests)
    output["stage"] = "completed" if output["ok"] else ("business_request_failed" if output["business_request_sent"] else "dependency_blocked")
    output["finished_at"] = datetime.now(timezone.utc).isoformat()
    return output
