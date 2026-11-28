"""API ingestion and exact object dedup acceptance contracts."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from scripts.acquisition_core import Response
from scripts.job_plan import read_manifest

class IngestTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("scripts.acquisition_ingest"),
                             "missing acquisition ingestion module")
        from scripts import acquisition_ingest
        self.a = acquisition_ingest
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "ingest.db"
        self.seed = "https://example.org/data?page=1"

    def response(self, items, next_url=None):
        return Response(200, "application/json", json.dumps({"items":items,"next":next_url}).encode())

    def test_pagination_resume_exact_objects_and_provenance(self):
        def fetch(url, limit):
            if url.endswith("robots.txt"):
                return Response(404,"text/plain",b"")
            if url == self.seed:
                return self.response([{"id":1},{"id":2}], "/data?page=2")
            if url.endswith("page=2"):
                return self.response([{"id":2},{"id":3}])
            self.fail(url)
        with self.a.Ingest(self.db, self.seed, max_pages=10, max_objects=10) as job:
            r = job.run(fetch, batch=1, sleep=lambda _:None)
            self.assertEqual(r["status"],"pending")
            self.assertEqual(r["objects"],2)
        with self.a.Ingest(self.db, self.seed, max_pages=10, max_objects=10) as job:
            r = job.run(fetch, batch=1, sleep=lambda _:None)
            self.assertEqual(r["status"],"complete")
            self.assertEqual(r["objects"],3)
            self.assertEqual(r["observations"],4)
            self.assertEqual(r["pages"],2)
            self.assertEqual(len(list(job.records())),4)

    def test_cross_origin_next_denied(self):
        seen=[]
        def fetch(url, limit):
            seen.append(url)
            if url.endswith("robots.txt"):
                return Response(404,"text/plain",b"")
            return self.response([{"id":1}],"https://other.example/data?page=2")
        with self.a.Ingest(self.db,self.seed) as job:
            self.assertEqual(job.run(fetch,sleep=lambda _:None)["status"],"invalid_next")
            self.assertEqual(job.run(fetch,sleep=lambda _:None)["status"],"invalid_next")
        self.assertEqual(seen,["https://example.org/robots.txt",self.seed])

    def test_rate_limit_persisted_and_no_fallback(self):
        seen=[]
        def fetch(url,limit):
            seen.append(url)
            if url.endswith("robots.txt"): return Response(404,"text/plain",b"")
            return Response(429,"text/plain",b"","120")
        with self.a.Ingest(self.db,self.seed) as job:
            self.assertEqual(job.run(fetch,sleep=lambda _:None)["status"],"rate_limited")
        with self.a.Ingest(self.db,self.seed) as job:
            self.assertEqual(job.run(fetch,sleep=lambda _:None)["status"],"rate_limited")
        self.assertEqual(len(seen),2)

    def test_capacity_atomic(self):
        def fetch(url,limit):
            if url.endswith("robots.txt"): return Response(404,"text/plain",b"")
            return self.response([{"id":1},{"id":2}])
        with self.a.Ingest(self.db,self.seed,max_objects=1) as job:
            r=job.run(fetch,sleep=lambda _:None)
            self.assertEqual(r["status"],"capacity")
            self.assertEqual(r["objects"],0)
            self.assertEqual(r["pages"],0)

    def test_cycle_stops(self):
        def fetch(url,limit):
            if url.endswith("robots.txt"): return Response(404,"text/plain",b"")
            return self.response([{"id":1}],self.seed)
        with self.a.Ingest(self.db,self.seed) as job:
            self.assertEqual(job.run(fetch,sleep=lambda _:None)["status"],"invalid_next")

    def test_scope_immutable(self):
        with self.a.Ingest(self.db,self.seed): pass
        with self.assertRaises(ValueError):
            self.a.Ingest(self.db,"https://other.example/data?page=1")

    def test_reviewed_job_manifest(self):
        manifest=read_manifest(Path.cwd(),"acquisition_owned_public")
        self.assertIsNotNone(manifest)
        self.assertEqual(manifest["jobs"][0]["commands"],[["python","-m","ci.fixtures.acquisition_live_smoke"]])

if __name__=="__main__":
    unittest.main()
