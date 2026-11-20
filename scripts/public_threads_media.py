"""Read one verified Threads video explicitly linked by public Open Graph metadata."""
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, ProxyHandler, Request

try:
    from scripts.public_media_input import identify_public_media
except ModuleNotFoundError:
    from public_media_input import identify_public_media

MAX_PAGE_BYTES = 2_000_000
MAX_VIDEO_BYTES = 28_000_000
VIDEO_TAGS = {"og:video", "og:video:url", "og:video:secure_url"}


class MediaMetadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.identities = set()
        self.videos = set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "link" and a.get("rel") == "canonical" and a.get("href"):
            self.identities.add(a["href"])
        if tag == "meta" and a.get("content"):
            if a.get("property") == "og:url":
                self.identities.add(a["content"])
            if a.get("property") in VIDEO_TAGS:
                self.videos.add(a["content"])


def threads_video_url(html, canonical):
    platform, post_id, _ = identify_public_media(canonical)
    if platform != "threads":
        return None
    meta = MediaMetadata()
    meta.feed(html)
    known = set()
    for value in meta.identities:
        try:
            identity = identify_public_media(value.split("?", 1)[0])
        except ValueError:
            continue
        known.add(identity[:2])
    if known != {("threads", post_id)} or len(meta.videos) != 1:
        return None
    candidate = next(iter(meta.videos))
    try:
        u = urlsplit(candidate)
        valid_port = u.port in (None, 443)
    except ValueError:
        return None
    if (len(candidate) > 4096 or not candidate.isascii() or
            any(ord(c) <= 32 for c in candidate) or "\\" in candidate or
            u.scheme != "https" or u.username is not None or u.password is not None
            or u.fragment or not valid_port or not u.path.lower().endswith(".mp4")
            or not (u.hostname or "").endswith((".cdninstagram.com", ".fbcdn.net"))):
        return None
    return candidate


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def public_bytes(url, expected_type, limit):
    opener = build_opener(ProxyHandler({}), NoRedirect())
    req = Request(url, headers={"Accept": expected_type})
    with opener.open(req, timeout=12) as response:
        if response.status != 200 or response.headers.get_content_type() != expected_type:
            return None
        size = response.headers.get("Content-Length")
        if size is not None and (not size.isdecimal() or int(size) > limit):
            return None
        data = response.read(limit + 1)
        return data if len(data) <= limit else None


def fetch_threads_media(canonical, folder):
    """No auth, scripts, rendition guesses, redirects, or public URL logs."""
    if identify_public_media(canonical)[0] != "threads":
        return False
    try:
        page = public_bytes(canonical, "text/html", MAX_PAGE_BYTES)
        if not page:
            return False
        video = threads_video_url(page.decode("utf-8", errors="replace"), canonical)
        if not video:
            return False
        data = public_bytes(video, "video/mp4", MAX_VIDEO_BYTES)
        if not data or len(data) < 100 or data[4:8] != b"ftyp":
            return False
    except (OSError, ValueError):
        return False
    (folder / "threads.mp4").write_bytes(data)
    return True
