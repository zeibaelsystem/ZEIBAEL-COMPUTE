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

    def test_signed_private_ci_verifier(self):
        import hashlib
        import hmac
        import time
        ts = str(int(time.time()))
        key = "temporary-ci-unit-test-secret-string-strong"
        nonce = "abcdef0123456789abcdef0123456789"
        message = f"v1|ci|private|validate||{ts}|{nonce}"
        sig = hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()
        env = dict(os.environ, ZEIBAEL_DISPATCH_SIGNING_KEY=key,
                   ZEIBAEL_CI_SOURCE="private", ZEIBAEL_CI_TASK="validate",
                   ZEIBAEL_SCRIPT_ID="", ZEIBAEL_ISSUED_AT=ts,
                   ZEIBAEL_NONCE=nonce, ZEIBAEL_SIGNATURE=sig)
        ok = subprocess.run([sys.executable, "scripts/verify_ci_dispatch.py"],
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.assertEqual(ok.returncode, 0)
        env["ZEIBAEL_SIGNATURE"] = "0" * 64
        invalid = subprocess.run([sys.executable, "scripts/verify_ci_dispatch.py"],
                                 env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.assertNotEqual(invalid.returncode, 0)


if __name__ == "__main__":
    unittest.main()
