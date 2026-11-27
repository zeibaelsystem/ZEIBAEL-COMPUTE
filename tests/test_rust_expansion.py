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

    def test_exact_license_file_exception_is_checksum_bound(self):
        from scripts.rust_expansion import review_package_license
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "LICENSE").write_text("Apache License\nVersion 2.0, January 2004\nEND OF TERMS AND CONDITIONS\n")
            pkg = {"name":"polars-arrow-format","version":"0.1.0","license":None,
                   "license_file":"LICENSE","manifest_path":str(root/"Cargo.toml")}
            checksum = "19b0ef2474af9396b19025b189d96e992311e6a47f90c53cd998b36c4c64b84c"
            self.assertEqual(review_package_license(pkg, checksum), "Apache-2.0")
            for changed, check in [(dict(pkg,version="0.1.1"),checksum),(pkg,"wrong"),
                                   (dict(pkg,license_file="../LICENSE"),checksum)]:
                with self.assertRaises(ValueError):
                    review_package_license(changed,check)
            (root / "LICENSE").write_text("Unknown license")
            with self.assertRaises(ValueError):
                review_package_license(pkg,checksum)

    def test_verified_lockfiles_are_byte_identical(self):
        import hashlib
        from scripts.rust_expansion import LOCK_HASHES, LOCK_ROOT
        self.assertEqual(set(LOCK_HASHES), {"rayon","tokio","ndarray","criterion","pyo3"})
        for name, expected in LOCK_HASHES.items():
            lock = (LOCK_ROOT / (name + ".lock")).read_bytes()
            self.assertEqual(hashlib.sha256(lock).hexdigest(), expected)

    def test_verified_rust_native_runner_requirements(self):
        from scripts.runtime_resources import CORE_VERIFIED, RUNNER_SPECS, choose_reviewed_runner
        from scripts.runtime_router import BUILTIN_RUNNERS, select_runner
        expected = PLATFORMS | {"ubuntu-24.04"}
        self.assertEqual(CORE_VERIFIED["rust"], expected)
        self.assertEqual(set(BUILTIN_RUNNERS["rust"]), expected)
        self.assertEqual(select_runner("rust"), "ubuntu-24.04")
        for runner in expected:
            spec = RUNNER_SPECS[runner]
            selected = choose_reviewed_runner("rust", {"os":spec["os"],"arch":spec["arch"],"toolchains":["rustc","cargo"]}, CORE_VERIFIED["rust"], "standard")
            self.assertEqual(selected, runner)
        with self.assertRaises(ValueError):
            choose_reviewed_runner("rust", {}, CORE_VERIFIED["rust"], "short", runner="ubuntu-slim")

    def test_spdx_alternatives_do_not_require_rejected_license_branch(self):
        from scripts.rust_expansion import permitted_license_expression
        for expression in ["MIT OR Apache-2.0 OR LGPL-2.1-or-later",
                           "MIT/Apache-2.0", "Apache-2.0 WITH LLVM-exception",
                           "(MIT OR GPL-3.0-only) AND BSD-3-Clause"]:
            self.assertTrue(permitted_license_expression(expression), expression)
        for expression in ["MIT AND LGPL-2.1-or-later", "GPL-3.0-only",
                           "MIT OR", "MIT nonsense", "MIT$OR Apache-2.0",
                           "MIT WITH Unknown-exception", "(MIT OR Apache-2.0", ""]:
            self.assertFalse(permitted_license_expression(expression), expression)

if __name__ == "__main__":
    unittest.main()
