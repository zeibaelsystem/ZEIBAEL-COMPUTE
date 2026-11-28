"""Bounded acquisition primitives for explicitly authorized public data.

The live transport is opt-in and is not exposed through the public runner
dispatcher. Offline tests inject a deterministic transport.
"""
from __future__ import annotations

import csv
import hashlib
import http.client
import io
import ipaddress
import json
import re
import socket
import ssl
import time
import xml.etree.ElementTree as ET
from collections import deque
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import parse_qsl, unquote, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

USER_AGENT = "ZEIBAEL-Acquisition/0.1"
AGENT_TOKEN = "ZEIBAEL-Acquisition"
SECRET_KEY = re.compile(r"token|password|passwd|secret|session|signature|credential|auth|api.?key", re.I)
DNS_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
MAX_LINKS = 1000
MAX_ROWS = 10000


@dataclass(frozen=True)
class Response:
    status: int
    content_type: str
    body: bytes
    retry_after: str | None = None


def canonical_url(raw, allowed_hosts, allowed_query_keys=()):
    if not isinstance(raw, str) or not raw.isascii() or not 1 <= len(raw) <= 2048:
        raise ValueError("Expected bounded ASCII HTTPS URL")
    if any(ord(c) <= 32 or ord(c) == 127 for c in raw) or "\\" in raw:
        raise ValueError("Whitespace, control characters and backslashes are not allowed")
    try:
        p = urlsplit(raw)
        host = (p.hostname or "").lower()
        port = p.port
    except ValueError as exc:
        raise ValueError("Invalid URL") from exc
    if (p.scheme != "https" or p.username is not None or p.password is not None
            or port not in (None, 443) or host not in allowed_hosts
            or "." not in host or len(host) > 253
            or not all(DNS_LABEL.fullmatch(s) for s in host.split("."))):
        raise ValueError("URL is outside the approved HTTPS DNS host scope")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("IP literal is not allowed")
    path = p.path or "/"
    decoded = unquote(path)
    if "\\" in decoded or any(ord(c) < 32 or ord(c) == 127 for c in decoded):
        raise ValueError("Invalid encoded path")
    if p.query:
        try:
            pairs = parse_qsl(p.query, keep_blank_values=True, strict_parsing=True,
                              max_num_fields=20, errors="strict")
        except (ValueError, UnicodeError) as exc:
            raise ValueError("Invalid query") from exc
        if any(key not in allowed_query_keys or SECRET_KEY.search(key) for key, _ in pairs):
            raise ValueError("Query key is not approved for public extraction")
    return urlunsplit(("https", host, path, p.query, ""))


def is_public_address(address):
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not (ip.is_multicast or ip.is_reserved or ip.is_unspecified)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, hostname, address):
        super().__init__(hostname, port=443, timeout=15, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        sock = socket.create_connection((self.address, self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


def fetch_https(url, max_bytes):
    """Single direct request: public DNS only, pinned address, no redirects/cookies."""
    p = urlsplit(url)
    keys = {key for key, _ in parse_qsl(p.query, keep_blank_values=True)}
    url = canonical_url(url, {p.hostname}, keys)
    p = urlsplit(url)
    if not isinstance(max_bytes, int) or not 1 <= max_bytes <= 16_000_000:
        raise ValueError("Invalid response bound")
    addresses = sorted({r[4][0] for r in socket.getaddrinfo(
        p.hostname, 443, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)})
    if not addresses or not all(is_public_address(a) for a in addresses):
        raise ValueError("DNS returned a non-public address")
    conn = _PinnedHTTPSConnection(p.hostname, addresses[0])
    try:
        target = p.path + ("?" + p.query if p.query else "")
        conn.request("GET", target, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity",
                                              "Accept": "*/*", "Connection": "close"})
        response = conn.getresponse()
        status = response.status
        kind = response.getheader("Content-Type", "")
        retry = response.getheader("Retry-After")
        if not 200 <= status < 300:
            return Response(status, kind, b"", retry)
        if response.getheader("Content-Encoding", "identity").lower() != "identity":
            raise ValueError("Unsupported compressed response")
        return Response(status, kind, response.read(max_bytes + 1), retry)
    finally:
        conn.close()


def _clean(parts):
    return " ".join(" ".join(parts).split())


class _HTML(HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base = base
        self.parts, self.title, self.links = [], [], []
        self.hidden = []
        self.in_title = False
        self.truncated = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "template", "noscript"}:
            self.hidden.append(tag)
        if self.hidden:
            return
        if tag == "title":
            self.in_title = True
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                if len(self.links) < MAX_LINKS:
                    self.links.append(urljoin(self.base, href))
                else:
                    self.truncated = True

    def handle_endtag(self, tag):
        if self.hidden:
            if tag == self.hidden[-1]:
                self.hidden.pop()
            return
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if not self.hidden:
            if self.in_title:
                self.title.append(data)
            else:
                self.parts.append(data)


def _reject_constant(value):
    raise ValueError("Invalid JSON constant: " + value)


def parse_document(body, content_type, url):
    """Parse only supported textual data. No execution or external entity access."""
    kind = content_type.split(";", 1)[0].strip().lower()
    if not (kind.startswith("text/") or kind in {"application/json", "application/xml",
             "application/xhtml+xml", "application/rss+xml", "application/atom+xml"}
             or kind.endswith(("+json", "+xml"))):
        raise ValueError("Unsupported media type")
    try:
        s = body.decode("utf-8-sig", errors="strict")
        if kind in {"text/html", "application/xhtml+xml"}:
            parser = _HTML(url)
            parser.feed(s)
            parser.close()
            return {"kind": "html", "title": _clean(parser.title), "text": _clean(parser.parts),
                    "links": list(dict.fromkeys(parser.links)), "truncated": parser.truncated}
        if kind == "application/json" or kind.endswith("+json"):
            return {"kind": "json", "data": json.loads(s, parse_constant=_reject_constant), "links": []}
        if kind == "text/csv":
            reader = csv.reader(io.StringIO(s, newline=""), strict=True)
            rows = []
            truncated = False
            for row in reader:
                if len(rows) >= MAX_ROWS:
                    truncated = True
                    break
                rows.append(row)
            return {"kind": "csv", "rows": rows, "links": [], "truncated": truncated}
        if kind in {"application/xml", "text/xml"} or kind.endswith("+xml"):
            if re.search(r"<!\s*(DOCTYPE|ENTITY)\b", s, re.I):
                raise ValueError("DTD and entities are prohibited")
            root = ET.fromstring(s)
            links = []
            truncated = False
            for elem in root.iter():
                name = elem.tag.rsplit("}", 1)[-1]
                if name in {"loc", "link"}:
                    value = elem.get("href") or elem.text
                    if value and value.strip():
                        if len(links) < MAX_LINKS:
                            links.append(urljoin(url, value.strip()))
                        else:
                            truncated = True
            return {"kind": "xml", "text": _clean(root.itertext()), "links": list(dict.fromkeys(links)),
                    "truncated": truncated}
        if kind.startswith("text/"):
            return {"kind": "text", "text": s, "links": []}
    except (UnicodeError, RecursionError, ET.ParseError, csv.Error) as exc:
        raise ValueError("Unable to parse document safely") from exc
    raise ValueError("Unsupported media type")


def crawl(seeds, allowed_hosts, fetch=fetch_https, *, max_pages=100, max_depth=2,
          max_bytes=2_000_000, max_total_bytes=64_000_000, max_queue=20_000,
          allowed_query_keys=(), sleep=time.sleep):
    """Bounded breadth-first extraction with an injected transport for offline tests.

    Each approved origin is queried for robots policy before its pages. Stop on
    access denial/rate limiting, never follow redirects, and return queued URLs
    when a budget is exhausted. No persistent state or concurrency in this version.
    """
    bounds = ((max_pages, 1, 10000), (max_depth, 0, 20), (max_bytes, 1, 16_000_000),
              (max_total_bytes, 1, 512_000_000), (max_queue, 1, 100000))
    if any(type(v) is not int or not low <= v <= high for v, low, high in bounds):
        raise ValueError("Invalid crawl bounds")
    hosts = {h.lower() for h in allowed_hosts}
    if not 1 <= len(hosts) <= 20:
        raise ValueError("Approve one to twenty exact hosts per batch")
    todo, seen, records = deque(), set(), []
    robots, stopped, delays, requested = {}, set(), {}, set()
    queue_limit_reached = False
    total = 0

    def enqueue(raw, depth, seed=False):
        nonlocal queue_limit_reached
        try:
            url = canonical_url(raw, hosts, allowed_query_keys)
        except ValueError:
            if seed:
                raise
            return
        if url in seen:
            return
        if len(seen) >= max_queue:
            queue_limit_reached = True
            return
        seen.add(url)
        todo.append((url, depth))

    for seed in seeds:
        enqueue(seed, 0, True)
    if not todo:
        raise ValueError("At least one approved seed is required")

    def get(url, host, limit):
        nonlocal total
        if host in requested:
            sleep(delays.get(host, 1.0))
        requested.add(host)
        response = fetch(url, limit)
        if not isinstance(response, Response):
            raise ValueError("Transport returned invalid response")
        total += len(response.body)
        return response

    def robots_for(host):
        url = "https://" + host + "/robots.txt"
        limit = min(512000, max_total_bytes - total)
        if limit <= 0:
            return "budget_exhausted", None
        try:
            response = get(url, host, limit)
            if len(response.body) > limit:
                return "robots_unavailable", None
            if response.status in (404, 410):
                return "ok", None
            if response.status != 200:
                return "robots_unavailable", None
            rp = RobotFileParser(url)
            rp.parse(response.body.decode("utf-8-sig", errors="strict").splitlines())
            delay = max(1.0, rp.crawl_delay(AGENT_TOKEN) or 0)
            rate = rp.request_rate(AGENT_TOKEN)
            if rate and rate.requests > 0:
                delay = max(delay, rate.seconds / rate.requests)
            if delay > 60:
                return "robots_unavailable", None
            delays[host] = delay
            return "ok", rp
        except (OSError, ValueError, http.client.HTTPException):
            return "robots_unavailable", None

    while todo and len(records) < max_pages and total < max_total_bytes:
        url, depth = todo.popleft()
        host = urlsplit(url).hostname
        record = {"url": url, "depth": depth}
        if host in stopped:
            record["status"] = "origin_stopped"
        else:
            if host not in robots:
                robots[host] = robots_for(host)
            policy_status, rp = robots[host]
            if policy_status != "ok":
                record["status"] = policy_status
                stopped.add(host)
            elif rp is not None and not rp.can_fetch(AGENT_TOKEN, url):
                record["status"] = "denied"
            elif total >= max_total_bytes:
                todo.appendleft((url, depth))
                break
            else:
                limit = min(max_bytes, max_total_bytes - total)
                try:
                    response = get(url, host, limit)
                    record["http_status"] = response.status
                    if response.status == 429:
                        record.update(status="rate_limited", retry_after=response.retry_after)
                        stopped.add(host)
                    elif response.status in (401, 403):
                        record["status"] = "access_denied"
                        stopped.add(host)
                    elif response.status == 503 and response.retry_after:
                        record.update(status="rate_limited", retry_after=response.retry_after)
                        stopped.add(host)
                    elif 300 <= response.status < 400:
                        record["status"] = "redirect_not_followed"
                    elif not 200 <= response.status < 300:
                        record["status"] = "http_error"
                    elif len(response.body) > limit:
                        record["status"] = "too_large"
                    else:
                        record["sha256"] = hashlib.sha256(response.body).hexdigest()
                        record["content_type"] = response.content_type
                        try:
                            parsed = parse_document(response.body, response.content_type, url)
                            record.update(status="ok", extraction=parsed)
                            if depth < max_depth:
                                for link in parsed["links"]:
                                    enqueue(link, depth + 1)
                        except ValueError:
                            record["status"] = "unsupported_or_invalid_document"
                except (OSError, ValueError, http.client.HTTPException):
                    record["status"] = "fetch_error"
        records.append(record)
    return {"records": records, "pending": [{"url": u, "depth": d} for u, d in todo],
            "discovered": len(seen), "bytes_received": total, "queue_limit_reached": queue_limit_reached,
            "complete": not todo and not queue_limit_reached}
