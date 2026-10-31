"""Validate public, unauthenticated Instagram media jobs before allocating a runner."""
import re
from urllib.parse import urlsplit

POST = re.compile(r"/(?:reel|p)/([A-Za-z0-9_-]{6,20})/?\Z")

def validate_public_media_url(url, steps_json="[]"):
    if not isinstance(url, str) or len(url) > 160 or url != url.strip():
        raise ValueError("Expected short public permalink")
    if steps_json not in ("", "[]"):
        raise ValueError("Media jobs do not accept browser action steps")
    try:
        u = urlsplit(url)
        port = u.port
    except ValueError as exc:
        raise ValueError("Malformed public permalink") from exc
    if (u.scheme != "https" or (u.hostname or "").lower() not in
            ("www.instagram.com", "instagram.com") or
            u.username or u.password or u.query or u.fragment or
            port not in (None, 443) or not POST.fullmatch(u.path) or
            u.path.startswith("//") or "\\" in url or "%" in url):
        raise ValueError("Only canonical public Instagram Reel/post links are allowed")
    return "https://www.instagram.com" + u.path.rstrip("/") + "/"

def validated_public_media_environment(script_id, source):
    if script_id != "public_media":
        return {}
    url = validate_public_media_url(source.get("ZEIBAEL_BROWSER_URL", ""),
                                    source.get("ZEIBAEL_BROWSER_STEPS", "[]"))
    return {"ZEIBAEL_MEDIA_URL": url}
