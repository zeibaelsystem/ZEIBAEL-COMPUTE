"""Contract for isolated, reviewed Rust expansion probes."""
import json
import unittest
from pathlib import Path
from scripts.job_plan import read_manifest
ROOT = Path(__file__).resolve().parents[1]
CASES = {"rayon","tokio","ndarray","polars","criterion","pyo3","tooling","simd","wasm","backtest"}
PLATFORMS = {"ubuntu-24.04-arm","windows-2022","windows-11-arm","macos-15","macos-15-intel"}

class RustExpansionContract(unittest.TestCase):
    def test_individual_routes_match_batch(self):
        batch = read_manifest(ROOT, "rust_expansion")["jobs"]
        self.assertEqual(len(batch), len(CASES) + len(PLATFORMS))
        for job in batch:
            route = read_manifest(ROOT, job["id"].replace("-", "_"))["jobs"]
            self.assertEqual(route, [job])
            self.assertEqual(job["runtime"], "rust")
            self.assertIn(job["timeout_profile"], {"short","standard","long"})
            self.assertFalse(job["runner"] == "ubuntu-slim")

    def test_case_catalog_exact_pins_and_no_paid_service(self):
        from scripts.rust_expansion import CASES as catalog
        self.assertEqual(set(catalog), CASES)
        for name, case in catalog.items():
            for version in case.get("dependencies", {}).values():
                self.assertRegex(version, r"^=\d+\.\d+\.\d+$")
            self.assertTrue(case["source"].strip())

    def test_backtest_source_has_distinct_entry_exit_and_cost_controls(self):
        from scripts.rust_expansion import CASES as catalog
        source = catalog["backtest"]["source"]
        self.assertIn("no_lookahead", source)
        self.assertIn("both_barriers_stop_first", source)
        self.assertIn("transaction_cost", source)

if __name__ == "__main__":
    unittest.main()
