import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.ci_driver import validate, package, script


class ModularCIDriverTests(unittest.TestCase):
    def test_validates_python_json_shell(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "code.py").write_text("x = 1\n")
            (root / "data.json").write_text(json.dumps({"works": True}))
            (root / "check.sh").write_text("echo good\n")
            rc, output = validate(root)
            self.assertEqual(rc, 0)
            self.assertIn('"python": 1', output)
            self.assertIn('"json": 1', output)
            self.assertIn('"shell": 1', output)

    def test_invalid_json_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "invalid.json").write_text("{invalid")
            with self.assertRaises(ValueError):
                validate(root)

    def test_package_is_temporary_and_has_expected_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source"
            root.mkdir()
            (root / "README.md").write_text("# test\n")
            output_dir = Path(temp) / "out"
            output_dir.mkdir()
            rc, report = package(root, output_dir)
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(report)["files"], 1)
            self.assertTrue((output_dir / "zeibael-source.zip").is_file())

    def test_script_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(ValueError):
                script(root, "../bad", root)

    def test_script_runs_and_does_not_inherit_unrelated_env(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source"
            jobs = root / "ci" / "jobs"
            jobs.mkdir(parents=True)
            result_dir = Path(temp) / "results"
            result_dir.mkdir()
            (jobs / "testjob.py").write_text(
                "import os\n"
                "from pathlib import Path\n"
                "assert not os.environ.get('ZEIBAEL_TEST_PRIVATE_VALUE')\n"
                "assert Path(os.environ['ZEIBAEL_OUTPUT_DIR']).is_dir()\n"
                "print('script job ok')\n"
            )
            original = os.environ.get("ZEIBAEL_TEST_PRIVATE_VALUE")
            os.environ["ZEIBAEL_TEST_PRIVATE_VALUE"] = "do-not-inherit"
            try:
                rc, output = script(root, "testjob", result_dir)
            finally:
                if original is None:
                    os.environ.pop("ZEIBAEL_TEST_PRIVATE_VALUE", None)
                else:
                    os.environ["ZEIBAEL_TEST_PRIVATE_VALUE"] = original
            self.assertEqual(rc, 0)
            self.assertIn("script job ok", output)


if __name__ == "__main__":
    unittest.main()
