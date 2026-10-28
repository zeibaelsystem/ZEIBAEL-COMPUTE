"""Validate an opt-in public HTTPS browser request before runner allocation."""
import ipaddress
import json
import re
from urllib.parse import urlsplit

HOST=re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
SELECTOR=re.compile(r"^(?:[#.][A-Za-z][A-Za-z0-9_-]*|[A-Za-z][A-Za-z0-9_-]*)$")
VALUE=re.compile(r"^[A-Za-z0-9 _.,-]{1,80}$")
DENY=(".local",".internal",".localhost",".test",".invalid",".home",".corp",".lan",".onion")
def parse_public_browser_request(url, steps_json):
    if not isinstance(url,str) or not 1<=len(url)<=400 or any(c in url for c in "\\\r\n\t ") or "%" in url or "@" in url:
        raise ValueError("Browser requires a simple public HTTPS URL")
    try:
        p=urlsplit(url)
        host=(p.hostname or "").lower()
        port=p.port
    except ValueError as exc:
        raise ValueError("Malformed public URL") from exc
    if (p.scheme!="https" or not host or p.username is not None or p.password is not None
        or p.query or p.fragment or (port is not None and port!=443)
        or "." not in host or host=="localhost" or host.endswith(DENY)
        or all(c.isdigit() for c in host.replace(".",""))
        or not all(HOST.fullmatch(part) for part in host.split("."))):
        raise ValueError("Only public DNS HTTPS (no tokens, query, fragment or custom port)")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("IP literal prohibited")
    try: steps=json.loads(steps_json or "[]")
    except (TypeError,ValueError) as exc: raise ValueError("browser_steps must be JSON") from exc
    if not isinstance(steps,list) or len(steps)>8: raise ValueError("At most eight steps")
    for step in steps:
        if not isinstance(step,dict) or step.get("action") not in ("click","fill","text","screenshot"):
            raise ValueError("Unsupported browser action")
        action=step["action"]
        permitted=({"action","selector","value"} if action=="fill" else
                   {"action","selector"} if action=="click" else {"action"})
        if set(step)!=permitted: raise ValueError("Unexpected browser action fields")
        if action in ("fill","click") and (not isinstance(step["selector"],str) or not SELECTOR.fullmatch(step["selector"])):
            raise ValueError("Only simple public selectors")
        if action=="fill" and (not isinstance(step["value"],str) or not VALUE.fullmatch(step["value"])):
            raise ValueError("Only short plain public input")
    return url,steps
