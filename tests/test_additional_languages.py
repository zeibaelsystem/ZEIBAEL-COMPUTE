"""Regression tests for five new bounded standard-runner language runtimes."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.job_plan import RUNTIMES, build_plan, read_manifest

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("php", "ruby", "dotnet", "kotlin", "swift")
LANG_COMMANDS = {
    "php": ["php", "--version"],
    "ruby": ["ruby", "--version"],
    "dotnet": ["dotnet", "--version"],
    "kotlin": ["kotlinc", "-version"],
    "swift": ["swift", "--version"],
}


class LanguageExtensionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "ci" / "jobs").mkdir(parents=True)

    def manifest(self, jobs):
        (self.root / "ci" / "jobs" / "language.json").write_text(
            json.dumps({"schema": 1, "jobs": jobs}), encoding="utf-8")

    def one(self, runtime, runner="ubuntu-24.04", commands=None):
        return {"id": "test_" + runtime, "runtime": runtime, "runner": runner,
                "timeout_profile": "short", "commands": commands or [LANG_COMMANDS[runtime]]}

    def test_five_new_runtime_names_are_supported(self):
        self.assertTrue(set(LANGS).issubset(RUNTIMES))
        self.assertEqual(len(RUNTIMES), 11)

    def test_each_language_cli_is_accepted_and_planned(self):
        self.manifest([self.one(language) for language in LANGS])
        plan = build_plan(self.root, "script", "language")
        self.assertEqual([j["runtime"] for j in plan["include"]], list(LANGS))
        self.assertTrue(all(not j["output_files"] for j in plan["include"]))

    def test_swift_mac_apple_silicon_runner(self):
        self.manifest([self.one("swift", runner="macos-15")])
        self.assertEqual(build_plan(self.root, "script", "language")["include"][0]["runner"],
                         "macos-15")

    def test_newly_reviewed_windows_arm_kotlin_is_accepted(self):
        self.manifest([self.one("kotlin", runner="windows-11-arm")])
        self.assertEqual(
            read_manifest(self.root, "language")["jobs"][0]["runner"],
            "windows-11-arm",
        )

    def test_bash_shell_injection_still_rejected(self):
        self.manifest([self.one("php", commands=[["bash", "-c", "echo arbitrary"]])])
        with self.assertRaises(ValueError):
            read_manifest(self.root, "language")

    def test_existing_docker_runner_limit_remains(self):
        job = self.one("php")
        job["id"] = "docker_bad"
        job["runtime"] = "docker"
        job["runner"] = "windows-2022"
        job["commands"] = [["docker", "--version"]]
        self.manifest([job])
        with self.assertRaises(ValueError):
            read_manifest(self.root, "language")

    def test_committed_smoke_manifest_covers_all_languages_and_two_swift_platforms(self):
        manifest = read_manifest(ROOT, "additional_languages_smoke")
        self.assertEqual(len(manifest["jobs"]), 6)
        self.assertEqual(set(job["runtime"] for job in manifest["jobs"]), set(LANGS))
        self.assertEqual({j["runner"] for j in manifest["jobs"] if j["runtime"] == "swift"},
                         {"ubuntu-24.04", "macos-15"})
        self.assertTrue(all(not j.get("output_files", False) for j in manifest["jobs"]))


if __name__ == "__main__":
    unittest.main()
