import json
import unittest
from pathlib import Path
from scripts.job_plan import read_manifest
ROOT = Path(__file__).resolve().parents[1]

class ExpansionContract(unittest.TestCase):
    def test_catalog_covers_ninety_distinct_candidates(self):
        data = json.loads((ROOT / "ci/expansion_candidates.json").read_text())
        items = data["candidates"]
        self.assertEqual(len(items), 90)
        self.assertEqual(len({x["id"] for x in items}), 90)
        self.assertEqual(len({x["group"] for x in items}), 9)
        for x in items:
            self.assertIn(x["status"], {"blocked", "verified"})
            if x["status"] == "blocked":
                self.assertTrue(x["reason"])
                self.assertIsNone(read_manifest(ROOT, "engine_" + x["id"]))
            else:
                self.assertEqual(x["evidence"]["manifest_step"], "success")
                self.assertEqual(x["evidence"]["artifact_step"], "success")
                job = read_manifest(ROOT, "engine_" + x["id"])["jobs"]
                self.assertEqual(len(job), 1)
                self.assertEqual(job[0]["id"], x["id"])
                self.assertEqual(job[0]["runner"], "ubuntu-24.04")
                self.assertTrue(job[0]["output_files"])
                self.assertEqual(job[0]["commands"][-1], ["python", "scripts/expansion_compute.py", x["id"]])

    def test_batch_exact_verified_coverage(self):
        data = json.loads((ROOT / "ci/expansion_candidates.json").read_text())
        verified = {x["id"] for x in data["candidates"] if x["status"] == "verified"}
        jobs = [j for path in sorted((ROOT / "ci/jobs").glob("expansion_batch_*.json"))
                for j in read_manifest(ROOT, path.stem)["jobs"]]
        self.assertEqual(len(jobs), len(verified))
        self.assertEqual({j["id"] for j in jobs}, verified)
        self.assertEqual(data["verified_count"], len(verified))
        self.assertEqual(data["blocked_count"], 90-len(verified))

    def test_unknown_engine_rejected(self):
        from scripts.expansion_compute import run
        with self.assertRaises(ValueError):
            run("unapproved", ROOT)
