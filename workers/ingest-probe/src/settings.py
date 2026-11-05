"""Probe metadata kept separate from lazily loaded native dependencies."""

REVISION = "probe-zoku-v9"
LIBRARY = {"name": "bilibili-api-zoku", "version": "17.4.4", "upstream_commit": "a0a1566c7c462ab57a3891c3a5f12976cbd11e9e", "transport": "CloudflareFetchClient"}
SAMPLE = {"uid": 23191782, "bvid": "BV1S8hA6MEvy", "cid": 41314223900, "dynamic_id": 1266215019584946198, "cvid": 18927433, "opus_id": 713245238842359833}
TARGETS = {
    "nav": ("Credential.check_valid", "credential", "valid"),
    "videos": ("User.get_videos", "user", "video"),
    "video": ("Video.get_info", "video", "info"),
    "parts": ("Video.get_pages", "video", "pages"),
    "dynamic_feed": ("User.get_dynamics_new", "user", "dynamic_new"),
    "dynamic": ("Dynamic.get_info", "dynamic", "detail"),
    "articles": ("User.get_articles", "user", "article"),
    "article": ("Article.get_info", "article", "view"),
    "article_content": ("Article.fetch_content", "article", "detail"),
    "opus": ("Opus.get_info / Opus.markdown", "opus", "detail"),
    "subtitles": ("Video.get_subtitle", "video", "get_player_info"),
}
