"""Offline scale benchmark, no network, no external dependency."""
import json
import tempfile
import time
import unittest
from pathlib import Path

from scripts.acquisition_core import Response
from scripts.acquisition_frontier import Frontier


class TestFrontierScale(unittest.TestCase):
    def test_ten_thousand_synthetic_urls_with_restarts(self):
        count = 10000
        hosts = {"host%d.example.org" % i for i in range(20)}
        hosts_sorted = sorted(hosts)
        urls = ["https://" + hosts_sorted[i % len(hosts)] + "/record/" + str(i)
                for i in range(count)]
        calls = 0
        # Each record is independent; no external I/O or actual rate delay.
        def fixture_transport(url, limit):
            if url.endswith("/robots.txt"):
                return Response(404, "text/plain", b"")
            return Response(200, "text/plain", url.encode("ascii"))
        started = time.perf_counter()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frontier.sqlite3"
            with Frontier(path, hosts, urls, max_depth=0, max_urls=count) as f:
                result = f.run_batch(fixture_transport, batch_size=1000, workers=8,
                                     sleep=lambda _: None)
                calls += result["processed"]
                self.assertEqual(result["pending"], 9000)
            for _ in range(9):
                with Frontier(path, hosts, max_depth=0, max_urls=count) as f:
                    result = f.run_batch(fixture_transport, batch_size=1000, workers=8,
                                         sleep=lambda _: None)
                    calls += result["processed"]
            with Frontier(path, hosts, max_depth=0, max_urls=count) as f:
                summary = f.summary()
                records = list(f.iter_records())
                self.assertEqual(summary["done"], count)
                self.assertEqual(summary["pending"], 0)
                self.assertEqual(summary["failed"], 0)
                self.assertTrue(summary["complete"])
                self.assertEqual(calls, count)
                self.assertEqual({r["url"] for r in records}, set(urls))
                self.assertEqual(len({r["sha256"] for r in records}), count)
            elapsed = time.perf_counter() - started
            print("ZEIBAEL_ACQUISITION_BENCHMARK=" + json.dumps({
                "fixture_only": True, "records": count, "origins": len(hosts),
                "workers": 8, "batches": 10, "seconds": round(elapsed, 3),
                "records_per_second": round(count / elapsed, 2),
                "sqlite_bytes": path.stat().st_size, "failures": 0
            }, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
