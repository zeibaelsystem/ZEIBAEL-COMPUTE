"""Validate exact, public per-video permalinks before allocating a runner."""
import re
from urllib.parse import urlsplit

POST = re.compile(r"/(?:reel|p)/([A-Za-z0-9_-]{6,20})/?\Z")
YOUTUBE_ID = r"[A-Za-z0-9_-]{11}"
TIKTOK = re.compile(r"/@([A-Za-z0-9_.]{1,30})/video/([0-9]{10,22})/?\Z")
THREADS = re.compile(r"/@([A-Za-z0-9_.]{1,30})/post/([A-Za-z0-9_-]{6,20})/?\Z")


def identify_public_media(url):
    """Return (platform, video/post ID, canonical URL); no outbound network."""
    if (not isinstance(url, str) or len(url) > 160 or
            not re.fullmatch(r"[!-~]+", url) or any(x in url for x in ("\\", "%", "#"))):
        raise ValueError("Expected a clean public permalink")
    try:
        u = urlsplit(url)
        port = u.port
    except ValueError as exc:
        raise ValueError("Malformed public permalink") from exc
    if (u.scheme != "https" or u.username is not None or u.password is not None
            or u.fragment or port not in (None, 443)):
        raise ValueError("Only direct public HTTPS links are allowed")
    host = u.hostname or ""
    if host in ("www.instagram.com", "instagram.com") and not u.query and "?" not in url:
        m = POST.fullmatch(u.path)
        if m:
            return "instagram", m[1], "https://www.instagram.com" + u.path.rstrip("/") + "/"
    elif host in ("www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"):
        if host == "youtu.be":
            m = re.fullmatch(r"/(" + YOUTUBE_ID + r")/?", u.path) if "?" not in url else None
        elif u.path == "/watch":
            m = re.fullmatch(r"v=(" + YOUTUBE_ID + r")", u.query)
        else:
            m = re.fullmatch(r"/shorts/(" + YOUTUBE_ID + r")/?", u.path) if "?" not in url else None
        if m:
            return "youtube", m[1], "https://youtu.be/" + m[1]
    elif host in ("www.tiktok.com", "tiktok.com") and "?" not in url:
        m = TIKTOK.fullmatch(u.path)
        if m:
            return "tiktok", m[2], f"https://www.tiktok.com/@{m[1]}/video/{m[2]}"
    elif host in ("www.threads.com", "threads.com", "www.threads.net", "threads.net") and "?" not in url:
        m = THREADS.fullmatch(u.path)
        if m:
            return "threads", m[2], f"https://www.threads.com/@{m[1]}/post/{m[2]}"
    raise ValueError("Unsupported public permalink or unresolved share link")


def validate_public_media_url(url, steps_json="[]"):
    if steps_json not in ("", "[]"):
        raise ValueError("Media jobs do not accept browser action steps")
    return identify_public_media(url)[2]


def parse_media_window(value):
    """Optional public media window in whole seconds, independent of browser actions."""
    if value == "":
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,4}:[0-9]{1,4}", value):
        raise ValueError("Expected media window start:end in seconds")
    start, end = map(int, value.split(":"))
    if not (0 <= start < end <= 3600 and end - start <= 300):
        raise ValueError("Media window must be within 0..3600 seconds and at most 300 seconds")
    return start, end


def validated_public_media_environment(script_id, source):
    if script_id != "public_media":
        return {}
    url = validate_public_media_url(source.get("ZEIBAEL_BROWSER_URL", ""),
                                    source.get("ZEIBAEL_BROWSER_STEPS", "[]"))
    safe = {"ZEIBAEL_MEDIA_URL": url}
    window = parse_media_window(source.get("ZEIBAEL_MEDIA_WINDOW", ""))
    if window:
        safe["ZEIBAEL_MEDIA_WINDOW"] = f"{window[0]}:{window[1]}"
    return safe
