"""Tests for opt-in, public-safe output artifacts (no extra step for default jobs)."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.job_plan import build_plan, read_manifest
from scripts.ci_driver import manifest_job, inspect_public_files


def record(*, include=None, commands=None):
    item = {"id": "output_demo", "runtime": "python", "runner": "ubuntu-24.04",
            "timeout_profile": "short", "commands": commands or [["python", "--version"]]}
    if include is not None:
        item["output_files"] = include
    return item


class OptionalOutputTests(unittest.TestCase):
    def manifest(self, root, job):
        directory = root / "ci" / "jobs"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "output_demo.json").write_text(
            json.dumps({"schema": 1, "jobs": [job]}), encoding="utf-8")

    def test_existing_jobs_do_not_upload_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.manifest(root, record())
            plan = build_plan(root, "script", "output_demo")
            self.assertIs(plan["include"][0]["output_files"], False)

    def test_opted_in_job_sets_matrix_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.manifest(root, record(include=True))
            plan = build_plan(root, "script", "output_demo")
            self.assertIs(plan["include"][0]["output_files"], True)

    def test_flag_must_be_boolean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.manifest(root, record(include="true"))
            with self.assertRaisesRegex(ValueError, "output_files"):
                read_manifest(root, "output_demo")

    def test_opted_in_output_generated_by_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "source"
            output = Path(tmp) / "output"
            output.mkdir()
            command = ("from pathlib import Path; import os; "
                       "p=Path(os.environ['ZEIBAEL_OUTPUT_DIR'])/'files'/'demo.txt'; "
                       "p.parent.mkdir(parents=True,exist_ok=True); "
                       "p.write_text('public demo')")
            self.manifest(root, record(include=True, commands=[["python", "-c", command]]))
            with patch.dict(os.environ, {"ZEIBAEL_JOB_RUNTIME": "python"}):
                rc, detail = manifest_job(root, "output_demo", "output_demo", output, 30)
            self.assertEqual(rc, 0, detail)
            self.assertIn("1 files", detail)
            self.assertEqual((output / "files" / "demo.txt").read_text(), "public demo")

    def test_opted_in_job_without_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "source"
            output = Path(tmp) / "output"
            output.mkdir()
            self.manifest(root, record(include=True))
            with patch.dict(os.environ, {"ZEIBAEL_JOB_RUNTIME": "python"}):
                with self.assertRaisesRegex(ValueError, "output|file"):
                    manifest_job(root, "output_demo", "output_demo", output, 30)

    def test_output_rejects_symlinks_hidden_files_and_oversize(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = root / "files"
            files.mkdir()
            (files / "ok.txt").write_text("ok")
            self.assertEqual(inspect_public_files(files)[0], 1)
            hidden = files / ".env"
            hidden.write_text("sensitive")
            with self.assertRaises(ValueError):
                inspect_public_files(files)
            hidden.unlink()
            symlink = files / "link"
            try:
                symlink.symlink_to(files / "ok.txt")
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are not enabled in this environment")
            with self.assertRaises(ValueError):
                inspect_public_files(files)
            symlink.unlink()
            with patch("scripts.ci_driver.MAX_PUBLIC_OUTPUT_BYTES", 1):
                with self.assertRaises(ValueError):
                    inspect_public_files(files)


if __name__ == "__main__":
    unittest.main()
