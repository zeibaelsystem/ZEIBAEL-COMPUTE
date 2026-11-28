"""Bounded local fixtures for upstream Spider CLI and MCP stdio.

Run inside loopback-only namespace, with an empty HOME and no credentials.
Never expose the MCP server or crawler as an arbitrary URL endpoint.
"""
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = "http://127.0.0.1:18766"
PAGES = {"/": b'<html><body><a href="/a">A</a><a href="/blocked">blocked</a><a href="/a#duplicate">duplicate</a></body></html>',
         "/a": b'<html><body><h1>ZEIBAEL-COMPANION</h1></body></html>'}
requests = []


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        requests.append(self.path)
        if self.path == "/robots.txt":
            body, kind, status = b"User-agent: *\nDisallow: /blocked\n", "text/plain", 200
        elif self.path in PAGES:
            body, kind, status = PAGES[self.path], "text/html", 200
        else:
            body, kind, status = b"denied", "text/plain", 403
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


@contextmanager
def local_site():
    requests.clear()
    with ThreadingHTTPServer(("127.0.0.1", 18766), Handler) as server:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            yield
        finally:
            server.shutdown()
            worker.join()


def check_requests():
    assert "/robots.txt" in requests, requests
    assert "/blocked" not in requests, requests
    assert requests.count("/") == 1 and requests.count("/a") == 1, requests


def cli(binary, env):
    with local_site():
        p = subprocess.run([binary, "--url", BASE + "/", "--http", "--respect-robots-txt",
                            "--limit", "8", "--depth", "3", "--delay", "100",
                            "crawl", "--output-links"], capture_output=True, text=True,
                           check=True, timeout=45, env=env)
        assert BASE + "/a" in p.stdout, (p.stdout, p.stderr)
        check_requests()
        print("ZEIBAEL_SPIDER_CLI=" + json.dumps({"status": "PASS", "requests": len(requests),
              "robots_checked": True, "blocked_not_requested": True, "dedup": True}), flush=True)


def mcp(binary, env):
    with local_site(), subprocess.Popen([binary], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        text=True, bufsize=1, env=env) as p:
        lines = queue.Queue()
        def reader():
            for line in p.stdout:
                lines.put(line)
            lines.put(None)
        threading.Thread(target=reader, daemon=True).start()
        def send(message):
            p.stdin.write(json.dumps({"jsonrpc": "2.0", **message}) + "\n")
            p.stdin.flush()
        def rpc(identifier, method, params):
            send({"id": identifier, "method": method, "params": params})
            while True:
                line = lines.get(timeout=40)
                assert line is not None, "MCP closed unexpectedly"
                response = json.loads(line)
                if response.get("id") != identifier:
                    continue
                assert "error" not in response, response
                return response["result"]
        def call(identifier, name, args):
            result = rpc(identifier, "tools/call", {"name": name, "arguments": args})
            assert not result.get("isError"), result
            text = "\n".join(x["text"] for x in result["content"] if x.get("type") == "text")
            return text
        try:
            initial = rpc(1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                            "clientInfo": {"name": "zeibael-local-fixture", "version": "1.0"}})
            assert initial.get("protocolVersion")
            send({"method": "notifications/initialized"})
            names = {t["name"] for t in rpc(2, "tools/list", {})["tools"]}
            assert {"spider_transform", "spider_crawl", "spider_scrape", "spider_links"} <= names, names
            output = call(3, "spider_transform", {"html": "<h1>ZEIBAEL-MCP</h1>",
                                                "return_format": "markdown"})
            assert "ZEIBAEL-MCP" in output, output
            output = call(4, "spider_crawl", {"url": BASE + "/", "limit": 8, "depth": 3,
                        "respect_robots_txt": True, "subdomains": False,
                        "headless": False, "delay_ms": 100, "return_format": "text"})
            assert "ZEIBAEL-COMPANION" in output and BASE + "/a" in output, output
            check_requests()
            print("ZEIBAEL_SPIDER_MCP=" + json.dumps({"status": "PASS", "tools": sorted(names),
                "invoked": ["spider_transform", "spider_crawl"], "requests": len(requests),
                "robots_checked": True, "blocked_not_requested": True}), flush=True)
        finally:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()


if __name__ == "__main__":
    mode, binary = sys.argv[1:]
    with tempfile.TemporaryDirectory() as home:
        env = {"PATH": "/usr/bin:/bin", "HOME": home, "NO_PROXY": "*"}
        {"cli": cli, "mcp": mcp}[mode](os.path.abspath(binary), env)
