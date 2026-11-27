"""Rust HPC integration contract; public synthetic workloads only."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.job_plan import read_manifest

ROOT = Path(__file__).resolve().parents[1]
CRATE = ROOT / "ci/fixtures/rust_hpc/Cargo.toml"


class RustHpcContract(unittest.TestCase):
    def test_reviewed_route_is_offline_and_bounded(self):
        job, = read_manifest(ROOT, "rust_hpc")["jobs"]
        self.assertEqual(job["runtime"], "rust")
        self.assertEqual(job["runner"], "ubuntu-24.04")
        self.assertEqual(job["timeout_profile"], "short")
        self.assertFalse(job.get("output_files", False))
        for command in job["commands"]:
            self.assertEqual(command[0], "cargo")
            self.assertIn("--offline", command)
            self.assertIn("--locked", command)
        self.assertEqual([c[1] for c in job["commands"]], ["test", "build", "run"])

    def test_release_binary_matches_serial_and_parallel(self):
        with tempfile.TemporaryDirectory() as target:
            command = ["cargo", "run", "--offline", "--locked", "--release",
                       "--manifest-path", str(CRATE), "--target-dir", target,
                       "--", "1000000", "4"]
            out = subprocess.run(command, cwd=ROOT, check=True, text=True,
                                 capture_output=True, timeout=120)
            result = json.loads(out.stdout)
            self.assertEqual(result["samples"], 1000000)
            self.assertEqual(result["workers"], 4)
            self.assertEqual(result["serial_hits"], result["parallel_hits"])
            self.assertLess(abs(result["pi"] - 3.141592653589793), 0.015)
            self.assertGreaterEqual(result["serial_ns"], 0)
            self.assertGreaterEqual(result["parallel_ns"], 0)
            bad = subprocess.run(command[:-2] + ["0", "4"], cwd=ROOT,
                                 capture_output=True, timeout=30)
            self.assertNotEqual(bad.returncode, 0)


if __name__ == "__main__":
    unittest.main()
