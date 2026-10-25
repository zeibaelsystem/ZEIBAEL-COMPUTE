"""Contract tests: FREE-ONLY resource aware routing and attributable failures."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.failure_diagnosis import diagnose_failure, summarize_failed_jobs
from scripts.job_plan import read_manifest, build_plan


class FailureDiagnosisTests(unittest.TestCase):
    def test_windows_nuget_path1_is_internal_not_provider(self):
        log = ("2026-10-24T18:21:57Z C:\\dotnet\\NuGet.targets: error : "
               "Value cannot be null. (Parameter 'path1')\n"
               "##[error]Process completed with exit code 1.")
        result = diagnose_failure(log)
        self.assertEqual(result["category"], "ZEIBAEL_INTERNAL")
        self.assertIn("path1", result["first_error"])

    def test_first_root_cause_wins_over_generic_exit_code(self):
        result = diagnose_failure("Traceback (most recent call last):\n"
                                  "FileNotFoundError: [WinError 2] The system cannot find the file specified\n"
                                  "##[error]Process completed with exit code 1.")
        self.assertEqual(result["category"], "ZEIBAEL_INTERNAL")
        self.assertIn("FileNotFoundError", result["first_error"])

    def test_user_syntax_error(self):
        result = diagnose_failure("main.py:13: SyntaxError: invalid syntax\nexit code 1")
        self.assertEqual(result["category"], "USER_CODE")

    def test_github_provider_quota_requires_explicit_evidence(self):
        result = diagnose_failure("GitHub Actions: You've hit the limit for GitHub-hosted runners.")
        self.assertEqual(result["category"], "PROVIDER_LIMIT")

    def test_transient_error_needs_explicit_signal(self):
        result = diagnose_failure("GitHub API HTTP 503 Service Unavailable")
        self.assertEqual(result["category"], "TRANSIENT")

    def test_unrecognized_failure_is_unknown_not_provider(self):
        self.assertEqual(diagnose_failure("Process completed with exit code 1.")["category"], "UNKNOWN")

    def test_redacts_secrets_and_truncates_output(self):
        result = diagnose_failure("SyntaxError: token=ghp_" + "a"*48)
        self.assertNotIn("ghp_", json.dumps(result))
        self.assertLessEqual(len(result["first_error"]), 280)

    def test_summarize_first_real_failure_in_job_order(self):
        jobs = [{"name": "build", "conclusion": "failure", "log": "SyntaxError: bad syntax"},
                {"name": "aggregate", "conclusion": "failure", "log": "Process completed with exit code 1"}]
        result = summarize_failed_jobs(jobs)
        self.assertEqual(result["category"], "USER_CODE")
        self.assertEqual(result["job"], "build")


class IntelligentRouterTests(unittest.TestCase):
    def manifest(self, job):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        (root / "ci" / "jobs").mkdir(parents=True)
        (root / "ci" / "jobs" / "reviewed.json").write_text(
            json.dumps({"schema": 1, "jobs": [job]}), encoding="utf-8")
        return root

    def base(self, **extra):
        job = {"id": "resource_test", "runtime": "python", "runner": "auto",
               "timeout_profile": "short", "commands": [["python", "--version"]]}
        job.update(extra)
        return job

    def test_default_existing_routing_preserved(self):
        root = self.manifest(self.base())
        self.assertEqual(read_manifest(root, "reviewed")["jobs"][0]["runner"], "ubuntu-24.04")

    def test_linux_arm64_requirement(self):
        root = self.manifest(self.base(requirements={"os": "linux", "arch": "arm64",
                                                      "min_cpu": 4, "min_memory_gb": 12}))
        self.assertEqual(build_plan(root, "script", "reviewed")["include"][0]["runner"], "ubuntu-24.04-arm")

    def test_mac_intel_ram_and_cpu_match(self):
        root = self.manifest(self.base(runtime="swift", commands=[["swift", "--version"]],
                                            requirements={"os": "macos", "arch": "x64",
                                                          "min_cpu": 4, "min_memory_gb": 12}))
        self.assertEqual(read_manifest(root, "reviewed")["jobs"][0]["runner"], "macos-15-intel")

    def test_explicit_runner_not_replaced_but_insufficient_fails(self):
        root = self.manifest(self.base(runner="macos-15", requirements={"min_memory_gb": 15}))
        with self.assertRaisesRegex(ValueError, "ZEIBAEL|resource|runner"):
            read_manifest(root, "reviewed")

    def test_oversized_output_rejected_as_zeibael_internal_limit(self):
        root = self.manifest(self.base(output_files=True, requirements={"output_mb": 51}))
        with self.assertRaisesRegex(ValueError, "ZEIBAEL.*output|output.*ZEIBAEL"):
            read_manifest(root, "reviewed")

    def test_unsupported_large_cpu_fails_no_paid_upgrade(self):
        root = self.manifest(self.base(requirements={"min_cpu": 8}))
        with self.assertRaisesRegex(ValueError, "ZEIBAEL|standard|FREE"):
            read_manifest(root, "reviewed")

    def test_toolchain_mismatch_fails_closed(self):
        root = self.manifest(self.base(requirements={"toolchains": ["cuda"]}))
        with self.assertRaisesRegex(ValueError, "ZEIBAEL|toolchain"):
            read_manifest(root, "reviewed")

    def test_matching_toolchain_is_permitted(self):
        root = self.manifest(self.base(runtime="dotnet", commands=[["dotnet", "--version"]],
                                       requirements={"os": "windows", "arch": "arm64",
                                                     "toolchains": ["dotnet"]}))
        self.assertEqual(read_manifest(root, "reviewed")["jobs"][0]["runner"], "windows-11-arm")

    def test_zero_or_boolean_resource_demand_rejected(self):
        root = self.manifest(self.base(requirements={"min_cpu": True}))
        with self.assertRaises(ValueError):
            read_manifest(root, "reviewed")

    def test_unknown_requirement_rejected(self):
        root = self.manifest(self.base(requirements={"gpu": 1}))
        with self.assertRaises(ValueError):
            read_manifest(root, "reviewed")


if __name__ == "__main__":
    unittest.main()
