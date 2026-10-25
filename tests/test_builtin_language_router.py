"""Runtime router contract: reviewed language aliases -> safe installed runner."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.job_plan import read_manifest, build_plan, RUNTIMES
from scripts.runtime_router import resolve_language, select_runner, BUILTIN_RUNNERS

ROOT = Path(__file__).resolve().parents[1]
EXTRA = {"powershell", "perl", "julia", "haskell", "fortran", "r", "scala"}


class BuiltinLanguageRouterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "ci" / "jobs").mkdir(parents=True)

    def write(self, jobs):
        (self.root / "ci" / "jobs" / "approved.json").write_text(
            json.dumps({"schema": 1, "jobs": jobs}), encoding="utf-8")

    def job(self, **kwargs):
        out = {"id": "one", "timeout_profile": "short",
               "commands": [["python", "--version"]]}
        out.update(kwargs)
        return out

    def test_seven_additions_extend_existing_runtime_set(self):
        self.assertEqual(len(RUNTIMES), 18)
        self.assertTrue(EXTRA.issubset(RUNTIMES))

    def test_aliases_cover_common_user_names(self):
        cases = {"PowerShell": "powershell", "pwsh": "powershell",
                 "Perl": "perl", "Julia": "julia", "Haskell": "haskell",
                 "GHC": "haskell", "Fortran": "fortran", "R": "r",
                 "R Language": "r", "Scala": "scala", "C#": "dotnet",
                 "Javascript": "node", "TypeScript": "node"}
        for name, runtime in cases.items():
            with self.subTest(name=name):
                self.assertEqual(resolve_language(name), runtime)

    def test_auto_runtime_and_auto_runner_are_resolved_in_committed_manifest(self):
        self.write([self.job(language="Julia", runtime="auto", runner="auto")])
        job = read_manifest(self.root, "approved")["jobs"][0]
        self.assertEqual(job["runtime"], "julia")
        self.assertEqual(job["runner"], "ubuntu-24.04")
        self.assertEqual(build_plan(self.root, "script", "approved")["include"][0]["runner"],
                         "ubuntu-24.04")

    def test_language_alone_is_enough_for_a_reviewed_job(self):
        self.write([self.job(language="R")])
        job = read_manifest(self.root, "approved")["jobs"][0]
        self.assertEqual(job["runtime"], "r")
        self.assertEqual(job["runner"], "windows-2022")

    def test_runtime_alone_selects_safe_runner(self):
        self.write([self.job(runtime="scala")])
        job = read_manifest(self.root, "approved")["jobs"][0]
        self.assertEqual(job["runner"], "windows-2022")

    def test_old_explicit_runner_stays_unchanged(self):
        self.write([self.job(runtime="python", runner="ubuntu-24.04-arm")])
        self.assertEqual(read_manifest(self.root, "approved")["jobs"][0]["runner"],
                         "ubuntu-24.04-arm")

    def test_conflicting_explicit_runtime_and_language_is_rejected(self):
        self.write([self.job(language="Fortran", runtime="ruby")])
        with self.assertRaisesRegex(ValueError, "language|runtime"):
            read_manifest(self.root, "approved")

    def test_unknown_language_is_rejected_and_no_auto_installation(self):
        self.write([self.job(language="imaginary-plugin-runtime")])
        with self.assertRaises(ValueError):
            read_manifest(self.root, "approved")

    def test_unverified_runner_rejected_as_internal_zeibael_policy(self):
        self.write([self.job(runtime="r", runner="ubuntu-slim")])
        with self.assertRaisesRegex(ValueError, "ZEIBAEL|runtime|runner"):
            read_manifest(self.root, "approved")

    def test_no_shell_injection_even_with_router(self):
        self.write([self.job(language="Julia", commands=[["bash", "-c", "curl x"]])])
        with self.assertRaises(ValueError):
            read_manifest(self.root, "approved")

    def test_router_only_recommends_approved_runners(self):
        self.assertEqual(BUILTIN_RUNNERS["r"], ("windows-2022",))
        self.assertEqual(BUILTIN_RUNNERS["scala"], ("windows-2022",))
        for name in EXTRA:
            self.assertIn(select_runner(name), BUILTIN_RUNNERS[name])

    def test_committed_seven_language_smoke_manifest_is_reviewed(self):
        manifest = read_manifest(ROOT, "builtin_languages_smoke")
        self.assertEqual({j["runtime"] for j in manifest["jobs"]}, EXTRA)
        self.assertEqual(len(manifest["jobs"]), 7)
        self.assertTrue(all(j.get("output_files", False) is False for j in manifest["jobs"]))


if __name__ == "__main__":
    unittest.main()
