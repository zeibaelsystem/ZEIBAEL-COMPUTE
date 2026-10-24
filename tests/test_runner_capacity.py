"""Regression coverage for ZEIBAEL-COMPUTE standard GitHub Free runner capacity."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.job_plan import build_plan, read_manifest, RUNNERS, MAX_JOBS

ROOT = Path(__file__).resolve().parents[1]


def job(identifier, runner="ubuntu-24.04", profile="short", runtime="python"):
    return {"id": identifier, "runtime": runtime, "runner": runner,
            "timeout_profile": profile, "commands": [["python", "--version"]]}


class CapacityTests(unittest.TestCase):
    def write_manifest(self, folder, jobs):
        work = Path(folder) / "ci" / "jobs"
        work.mkdir(parents=True, exist_ok=True)
        (work / "capacity.json").write_text(json.dumps({"schema": 1, "jobs": jobs}), encoding="utf-8")

    def test_twenty_reviewed_jobs_are_supported(self):
        self.assertEqual(MAX_JOBS, 20)
        with tempfile.TemporaryDirectory() as tmp:
            self.write_manifest(tmp, [job("job" + str(i)) for i in range(20)])
            self.assertEqual(len(build_plan(Path(tmp), "script", "capacity")["include"]), 20)

    def test_twenty_one_jobs_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write_manifest(tmp, [job("job" + str(i)) for i in range(21)])
            with self.assertRaisesRegex(ValueError, "20"):
                read_manifest(Path(tmp), "capacity")

    def test_all_seven_public_standard_runner_families(self):
        runners = {"ubuntu-24.04", "ubuntu-24.04-arm", "windows-2022",
                   "windows-11-arm", "macos-15-intel", "macos-15", "ubuntu-slim"}
        self.assertTrue(runners.issubset(RUNNERS))
        with tempfile.TemporaryDirectory() as tmp:
            self.write_manifest(tmp, [job("r" + str(i), runner=runner) for i, runner in enumerate(sorted(runners))])
            self.assertEqual(len(read_manifest(Path(tmp), "capacity")["jobs"]), 7)

    def test_ubuntu_slim_only_short_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write_manifest(tmp, [job("slim", runner="ubuntu-slim", profile="standard")])
            with self.assertRaisesRegex(ValueError, "slim|15|min"):
                read_manifest(Path(tmp), "capacity")

    def test_slim_cannot_run_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write_manifest(tmp, [job("dock", runner="ubuntu-slim", runtime="docker")])
            with self.assertRaises(ValueError):
                read_manifest(Path(tmp), "capacity")

    def test_no_workflow_wide_concurrency_lock(self):
        src = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertNotIn("\nconcurrency:\n", src)
        self.assertIn("max-parallel: 20", src)

    def test_20_run_sample_validates(self):
        manifest = read_manifest(ROOT, "capacity_20_probe")
        self.assertEqual(len(manifest["jobs"]), 20)
        runners = {job["runner"] for job in manifest["jobs"]}
        self.assertEqual(len(runners), 7)


if __name__ == "__main__":
    unittest.main()
