"""Cross-platform ZEIBAEL language allowances: test before enabling."""
import json
import tempfile
import unittest
from pathlib import Path
from scripts.job_plan import read_manifest, build_plan, NEW_RUNTIME_RUNNERS

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "php": {"ubuntu-24.04", "ubuntu-24.04-arm", "windows-2022",
            "windows-11-arm", "macos-15-intel"},
    "ruby": {"ubuntu-24.04", "ubuntu-24.04-arm", "windows-2022",
             "windows-11-arm", "macos-15-intel", "macos-15"},
    "dotnet": {"ubuntu-24.04", "ubuntu-24.04-arm", "windows-2022",
               "windows-11-arm", "macos-15-intel", "macos-15"},
    "kotlin": {"ubuntu-24.04", "ubuntu-24.04-arm", "windows-2022",
               "windows-11-arm", "macos-15-intel", "macos-15"},
    "swift": {"ubuntu-24.04", "ubuntu-24.04-arm", "macos-15-intel", "macos-15"},
}


class CrossPlatformLanguages(unittest.TestCase):
    def test_exact_reviewed_platform_allowlist(self):
        self.assertEqual({k: NEW_RUNTIME_RUNNERS[k] for k in EXPECTED}, EXPECTED)

    def test_two_smoke_manifests_cover_all_new_combinations_once(self):
        jobs = []
        for stem in ("languages_platform_a", "languages_platform_b"):
            manifest = read_manifest(ROOT, stem)
            self.assertLessEqual(len(manifest["jobs"]), 20)
            self.assertGreater(len(manifest["jobs"]), 0)
            self.assertEqual(len(build_plan(ROOT, "script", stem)["include"]),
                             len(manifest["jobs"]))
            jobs.extend(manifest["jobs"])
        expected = {(language, runner) for language, runners in EXPECTED.items() for runner in runners}
        preexisting = {
            ("php", "ubuntu-24.04"), ("ruby", "ubuntu-24.04"),
            ("dotnet", "ubuntu-24.04"), ("kotlin", "ubuntu-24.04"),
            ("swift", "ubuntu-24.04"), ("swift", "macos-15"),
        }
        self.assertEqual({(j["runtime"], j["runner"]) for j in jobs}, expected - preexisting)
        self.assertEqual(len(jobs), 21)
        self.assertEqual(len({j["id"] for j in jobs}), len(jobs))

    def test_windows_swift_and_ubuntu_slim_remain_blocked_as_internal_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "ci" / "jobs"
            folder.mkdir(parents=True)
            for runner in ("windows-2022", "ubuntu-slim"):
                bad = {"schema": 1, "jobs": [{
                    "id": "bad", "runtime": "swift", "runner": runner,
                    "timeout_profile": "short", "commands": [["swift", "--version"]]
                }]}
                (folder / "reject.json").write_text(json.dumps(bad))
                with self.assertRaisesRegex(ValueError, "ZEIBAEL internal|combination|slim"):
                    read_manifest(root, "reject")

    def test_macos_arm64_php_not_claimed_as_supported_without_evidence(self):
        self.assertNotIn("macos-15", EXPECTED["php"])


if __name__ == "__main__":
    unittest.main()
