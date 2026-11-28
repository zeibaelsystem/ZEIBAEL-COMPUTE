"""Synthetic-only acceptance tests for the durable acquisition frontier."""
import importlib.util
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from scripts.acquisition_core import Response


class TestFrontier(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("scripts.acquisition_frontier"),
                             "durable frontier is not implemented")
        from scripts.acquisition_frontier import Frontier
        self.Frontier = Frontier
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "queue.sqlite3"

    def open(self, seeds=(), **kwargs):
        return self.Frontier(self.path, {"example.org", "example.net"}, seeds,
                             max_depth=2, **kwargs)

    def test_resume_preserves_depth_dedup_and_results(self):
        requested = []
        def fetch(url, limit):
            requested.append(url)
            if url.endswith("/robots.txt"):
                return Response(404, "text/plain", b"")
            return Response(200, "text/html",
                b'<a href="/next">next</a><a href="/next#x">duplicate</a><a href="/">loop</a>'
                if url.endswith("/") else b'<a href="/third">next</a>')
        with self.open(["https://example.org/"]) as f:
            f.run_batch(fetch, batch_size=1, workers=1, sleep=lambda _: None)
            self.assertEqual(f.summary()["done"], 1)
            self.assertEqual(f.summary()["pending"], 1)
        with self.open() as f:
            f.run_batch(fetch, batch_size=1, workers=1, sleep=lambda _: None)
            f.run_batch(fetch, batch_size=1, workers=1, sleep=lambda _: None)
            self.assertEqual(f.summary()["done"], 3)
            self.assertEqual(f.summary()["pending"], 0)
            self.assertEqual([x["depth"] for x in f.records()], [0, 1, 2])
            self.assertEqual(len(f.records()[0]["sha256"]), 64)
        self.assertEqual(requested.count("https://example.org/"), 1)

    def test_stops_persist_across_batches_and_reopen(self):
        requested = []
        def fetch(url, limit):
            requested.append(url)
            if url.endswith("/robots.txt"):
                return Response(404, "text/plain", b"")
            return Response(429, "text/plain", b"", "120")
        with self.open(["https://example.org/a", "https://example.org/b"]) as f:
            f.run_batch(fetch, batch_size=1, workers=1, sleep=lambda _: None)
            self.assertEqual(f.summary()["blocked"], 1)
        with self.open() as f:
            f.run_batch(fetch, batch_size=1, workers=1, sleep=lambda _: None)
            self.assertEqual(f.summary()["pending"], 0)
            self.assertEqual(f.summary()["stopped_hosts"], 1)
        self.assertNotIn("https://example.org/b", requested)

    def test_parallelism_only_across_origins(self):
        barrier = threading.Barrier(2)
        active = set()
        lock = threading.Lock()
        def fetch(url, limit):
            if url.endswith("/robots.txt"):
                return Response(404, "text/plain", b"")
            host = urlsplit(url).hostname
            with lock:
                if host in active:
                    raise AssertionError("concurrent request to same origin")
                active.add(host)
            barrier.wait(timeout=5)
            with lock:
                active.remove(host)
            return Response(200, "text/plain", b"ok")
        with self.open(["https://example.org/a", "https://example.net/a"]) as f:
            f.run_batch(fetch, batch_size=2, workers=2, sleep=lambda _: None)
            self.assertEqual(f.summary()["done"], 2)

    def test_crash_rolls_back_batch_for_at_least_once_recovery(self):
        def fail(url, limit):
            if url.endswith("/robots.txt"):
                return Response(404, "text/plain", b"")
            raise RuntimeError("simulated interruption")
        with self.open(["https://example.org/a"]) as f:
            with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
                f.run_batch(fail, workers=1, sleep=lambda _: None)
            self.assertEqual(f.summary()["pending"], 1)
        with self.open() as f:
            f.run_batch(lambda url, limit: Response(404 if url.endswith("/robots.txt") else 200,
                         "text/plain", b"ok"), workers=1, sleep=lambda _: None)
            self.assertEqual(f.summary()["done"], 1)

    def test_scope_and_frontier_capacity(self):
        with self.open(["https://example.org/"], max_urls=2) as f:
            def fetch(url, limit):
                if url.endswith("/robots.txt"):
                    return Response(404, "text/plain", b"")
                return Response(200, "text/html", b'<a href="/a">a</a><a href="/b">b</a>')
            f.run_batch(fetch, workers=1, sleep=lambda _: None)
            self.assertEqual(f.summary()["discovered"], 2)
            self.assertTrue(f.summary()["capacity_reached"])
        with self.assertRaises(ValueError):
            self.Frontier(self.path, {"other.example"}, [], max_depth=2, max_urls=2)

    def test_explicit_transport_and_empty_frontier(self):
        with self.open() as f:
            self.assertEqual(f.summary()["pending"], 0)
            with self.assertRaises(TypeError):
                f.run_batch()
            self.assertEqual(f.run_batch(lambda *_: self.fail("unexpected request"))["processed"], 0)


if __name__ == "__main__":
    unittest.main()
