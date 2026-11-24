import json
import unittest
from pathlib import Path

from scripts.job_plan import read_manifest

ROOT = Path(__file__).resolve().parents[1]
ENGINES = {
    "openfoam", "coolprop", "dwsim", "sympy", "opencv", "tesseract",
    "duckdb", "polars", "quantlib", "vectorbt", "pytorch", "onnxruntime",
    "openmodelica", "gmsh", "lammps",
}

class ExtendedComputeContract(unittest.TestCase):
    def test_all_engines_have_bounded_reviewed_jobs(self):
        jobs = read_manifest(ROOT, "extended_compute_smoke")["jobs"]
        self.assertEqual({j["id"] for j in jobs}, ENGINES)
        self.assertEqual(len(jobs), len(ENGINES))
        for job in jobs:
            self.assertEqual(job["runner"], "ubuntu-24.04")
            self.assertTrue(job["output_files"])
            self.assertIn(job["timeout_profile"], {"standard", "long"})
            self.assertEqual(job["commands"][-1], ["python", "scripts/extended_compute.py", job["id"]])

    def test_individual_routes_equal_batch_jobs(self):
        batch = json.loads((ROOT / "ci/jobs/extended_compute_smoke.json").read_text())
        for job in batch["jobs"]:
            item = json.loads((ROOT / ("ci/jobs/engine_" + job["id"] + ".json")).read_text())
            self.assertEqual(item, {"schema": 1, "jobs": [job]})

    def test_smoke_dispatch_rejects_unknown_engine(self):
        from scripts.extended_compute import run_engine
        with self.assertRaises(ValueError):
            run_engine("not-approved", ROOT)

if __name__ == "__main__":
    unittest.main()
