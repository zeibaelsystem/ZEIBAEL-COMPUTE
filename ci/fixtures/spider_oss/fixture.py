"""Run the actual Rust crawler on a finite local-only site.

No arbitrary target, private data, credentials, or provider endpoint.
The CI invocation uses a network namespace containing only loopback.
"""
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = b'<html><a href="/a">A</a><a href="/b">B</a><a href="/a#dup">duplicate</a><a href="/blocked">blocked</a></html>'
PAGES = {"/": ROOT, "/a": b'<html>ZEIBAEL-A<a href="/b">B</a></html>',
         "/b": b'<html>ZEIBAEL-B<a href="/">root</a></html>'}
requests = []


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        requests.append(self.path)
        if self.path == "/robots.txt":
            body = b"User-agent: *\nDisallow: /blocked\n"
            kind = "text/plain"
            status = 200
        elif self.path in PAGES:
            body, kind, status = PAGES[self.path], "text/html", 200
        else:
            body, kind, status = b"not allowed", "text/plain", 403
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


def main():
    binary = os.path.abspath(sys.argv[1])
    with ThreadingHTTPServer(("127.0.0.1", 18765), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = subprocess.run([binary], text=True, capture_output=True,
                                    timeout=45, check=True,
                                    env={"PATH": "/usr/bin:/bin", "NO_PROXY": "*"})
            pages = json.loads(result.stdout.strip().splitlines()[-1])
            by_path = {p["url"].removeprefix("http://127.0.0.1:18765"): p for p in pages}
            assert set(by_path) == {"/", "/a", "/b"}, (pages, requests)
            assert len(pages) == 3, pages
            assert "/robots.txt" in requests, requests
            assert "/blocked" not in requests, requests
            assert all(requests.count(p) == 1 for p in PAGES), requests
            assert all(p["status"] == 200 for p in pages), pages
            assert "ZEIBAEL-A" in by_path["/a"]["html"]
            assert "ZEIBAEL-B" in by_path["/b"]["html"]
            print("ZEIBAEL_SPIDER_FIXTURE=" + json.dumps({
                "pages": len(pages), "http_requests": len(requests),
                "robots_checked": True, "blocked_not_requested": True,
                "duplicate_not_requested": True, "external_network": "isolated",
                "spider_version": "2.54.2", "status": "PASS"
            }), flush=True)
        finally:
            server.shutdown()
            thread.join()


if __name__ == "__main__":
    main()
