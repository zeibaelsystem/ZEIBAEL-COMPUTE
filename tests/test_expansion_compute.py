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
            self.assertIn(x["status"], {"candidate", "blocked", "verified"})
            if x["status"] == "blocked":
                self.assertTrue(x["reason"])
            else:
                job = read_manifest(ROOT, "engine_" + x["id"])["jobs"]
                self.assertEqual(len(job), 1)
                self.assertEqual(job[0]["id"], x["id"])
                self.assertEqual(job[0]["runner"], "ubuntu-24.04")
                self.assertTrue(job[0]["output_files"])
                self.assertEqual(job[0]["commands"][-1], ["python", "scripts/expansion_compute.py", x["id"]])

    def test_unknown_engine_rejected(self):
        from scripts.expansion_compute import run
        with self.assertRaises(ValueError):
            run("unapproved", ROOT)
