import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.job_plan import build_plan, read_manifest
from scripts.aggregate_results import aggregate
from scripts.ci_driver import manifest_job

def job(name="one", runtime="python", runner="ubuntu-24.04", timeout="short", commands=None):
    return {"id": name, "runtime": runtime, "runner": runner,
            "timeout_profile": timeout, "commands": commands or [["python", "--version"]]}

class JobPlatformTests(unittest.TestCase):
    def manifest(self, root, jobs):
        folder = root / "ci" / "jobs"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "approved.json").write_text(json.dumps({"schema": 1, "jobs": jobs}))

    def test_default_job_has_one_runner_and_bounded_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_plan(Path(tmp), "python_tests", "")
            self.assertEqual(plan["include"][0]["runner"], "ubuntu-24.04")
            self.assertEqual(plan["include"][0]["timeout"], 30)
            self.assertEqual(len(plan["include"]), 1)

    def test_manifest_expands_to_parallel_python_and_node(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.manifest(root, [job("python"), job("node", runtime="node",
                                                     commands=[["node", "--version"]])])
            plan = build_plan(root, "script", "approved")
            self.assertEqual(len(plan["include"]), 2)
            self.assertEqual([j["runtime"] for j in plan["include"]], ["python", "node"])

    def test_invalid_script_and_unapproved_commands_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                build_plan(root, "script", "../outside")
            self.manifest(root, [job(commands=[["bash", "-c", "curl example.com"]])])
            with self.assertRaises(ValueError):
                read_manifest(root, "approved")

    def test_unknown_runner_and_excess_parallel_jobs_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.manifest(root, [job(runner="self-hosted")])
            with self.assertRaises(ValueError):
                read_manifest(root, "approved")
            self.manifest(root, [job(str(i)) for i in range(21)])
            with self.assertRaises(ValueError):
                read_manifest(root, "approved")

    def test_arm64_runner_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.manifest(root, [job("arm", runner="ubuntu-24.04-arm")])
            plan = build_plan(root, "script", "approved")
            self.assertEqual(plan["include"][0]["runner"], "ubuntu-24.04-arm")

    def test_cc_compiler_commands_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.manifest(root, [job("cc", commands=[
                ["gcc", "-std=c11", "-o", "hello-c", "hello.c"],
                ["g++", "-std=c++17", "-o", "hello-cpp", "hello.cpp"],
            ])])
            self.assertEqual(read_manifest(root, "approved")["jobs"][0]["id"], "cc")

    def test_aggregator_detects_missing_job_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "only").mkdir()
            (root / "only" / "result.json").write_text(json.dumps({
                "schema": 1, "job_id": "only", "runtime": "python",
                "task": "script", "status": "success", "exit_code": 0
            }))
            with self.assertRaisesRegex(ValueError, "missing|Expected|count"):
                aggregate(root, expected_jobs=2)

    def test_aggregator_rejects_duplicate_job_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for folder in ("first", "second"):
                (root / folder).mkdir()
                (root / folder / "result.json").write_text(json.dumps({
                    "schema": 1, "job_id": "same", "runtime": "python",
                    "task": "script", "status": "success", "exit_code": 0
                }))
            with self.assertRaisesRegex(ValueError, "Duplicate|duplicate"):
                aggregate(root, expected_jobs=2)

    def test_generic_manifest_executes_reviewed_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "output"
            out.mkdir()
            self.manifest(root, [job(commands=[["python", "--version"]])])
            with patch.dict(os.environ, {"ZEIBAEL_JOB_RUNTIME": "python"}):
                rc, output = manifest_job(root, "approved", "one", out, 30)
            self.assertEqual(rc, 0)
            self.assertIn("Python", output)

    def test_runner_identity_passed_without_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "output"
            out.mkdir()
            self.manifest(root, [job(commands=[[
                "python", "-c",
                "import os; assert os.getenv('RUNNER_OS') == 'Linux'; "
                "assert os.getenv('RUNNER_ARCH') == 'ARM64'; "
                "assert not os.getenv('ZEIBAEL_TEST_PRIVATE_VALUE'); "
                "print('ZEIBAEL_RUNNER_ENV_OK')"
            ]])])
            with patch.dict(os.environ, {
                "ZEIBAEL_JOB_RUNTIME": "python",
                "RUNNER_OS": "Linux",
                "RUNNER_ARCH": "ARM64",
                "ZEIBAEL_TEST_PRIVATE_VALUE": "must-not-inherit",
            }):
                rc, detail = manifest_job(root, "approved", "one", out, 30)
            self.assertEqual(rc, 0, detail)
            self.assertIn("ZEIBAEL_RUNNER_ENV_OK", detail)

    def test_result_aggregator_counts_success_and_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "success").mkdir()
            (root / "failure").mkdir()
            (root / "success" / "result.json").write_text(json.dumps(
                {"schema": 1, "job_id": "one", "task": "script", "runtime": "python",
                 "status": "success", "exit_code": 0, "duration_seconds": 0.1}))
            (root / "failure" / "result.json").write_text(json.dumps(
                {"schema": 1, "job_id": "two", "task": "script", "runtime": "node",
                 "status": "failure", "exit_code": 1, "duration_seconds": 0.1}))
            doc = aggregate(root)
            self.assertEqual(doc["job_count"], 2)
            self.assertEqual(doc["status"], "failure")


    def test_eight_reviewed_jobs_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.manifest(root, [job("step" + str(i)) for i in range(8)])
            plan = build_plan(root, "script", "approved")
            self.assertEqual(len(plan["include"]), 8)

    def test_aggregate_rejects_wrong_ids_even_if_count_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "actual").mkdir()
            (root / "actual" / "result.json").write_text(json.dumps({
                "schema": 1, "job_id": "unexpected", "runtime": "python",
                "task": "script", "status": "success", "exit_code": 0
            }))
            with self.assertRaisesRegex(ValueError, "job ids"):
                aggregate(root, expected_jobs=1, expected_ids=["expected"])

    def test_aggregate_rejects_inconsistent_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bad").mkdir()
            (root / "bad" / "result.json").write_text(json.dumps({
                "schema": 1, "job_id": "bad", "runtime": "python",
                "task": "script", "status": "success", "exit_code": 42
            }))
            with self.assertRaisesRegex(ValueError, "Inconsistent"):
                aggregate(root, expected_jobs=1)

    def test_manifest_commands_share_one_deadline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "output"
            out.mkdir()
            self.manifest(root, [job(commands=[["python", "--version"], ["python", "--version"]])])
            with patch.dict(os.environ, {"ZEIBAEL_JOB_RUNTIME": "python"}), \
                 patch("scripts.ci_driver.execute", return_value=(0, "ok")) as mocked, \
                 patch("scripts.ci_driver.time.monotonic", side_effect=[0, 1, 5]):
                rc, _ = manifest_job(root, "approved", "one", out, 10)
            self.assertEqual(rc, 0)
            self.assertEqual([c.kwargs["timeout"] for c in mocked.call_args_list], [9, 5])

    def test_expired_manifest_deadline_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "output"
            out.mkdir()
            self.manifest(root, [job(commands=[["python", "--version"]])])
            with patch.dict(os.environ, {"ZEIBAEL_JOB_RUNTIME": "python"}), \
                 patch("scripts.ci_driver.time.monotonic", side_effect=[0, 11]):
                with self.assertRaises(subprocess.TimeoutExpired):
                    manifest_job(root, "approved", "one", out, 10)

if __name__ == "__main__":
    unittest.main()
