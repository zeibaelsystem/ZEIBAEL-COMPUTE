"""Windows runtime regressions: preserve needed OS paths without forwarding secrets."""
import unittest
from unittest.mock import patch

from scripts.ci_driver import safe_job_environment, resolve_job_command


class WindowsLanguageRuntimeTests(unittest.TestCase):
    def test_windows_dotnet_receives_safe_standard_paths_not_secrets(self):
        values = {
            "PATH": r"C:\\Windows\\System32",
            "ProgramFiles": r"C:\\Program Files",
            "ProgramFiles(x86)": r"C:\\Program Files (x86)",
            "ProgramData": r"C:\\ProgramData",
            "CommonProgramFiles": r"C:\\Program Files\\Common Files",
            "CommonProgramFiles(x86)": r"C:\\Program Files (x86)\\Common Files",
            "HOMEDRIVE": "C:",
            "HOMEPATH": r"\\Users\\runneradmin",
            "SystemDrive": "C:",
            "COMSPEC": r"C:\\Windows\\system32\\cmd.exe",
            "PATHEXT": ".COM;.EXE;.BAT;.CMD",
            "DOTNET_ROOT": r"C:\\Program Files\\dotnet",
            "GITHUB_TOKEN": "should-not-pass",
            "NUGET_AUTH_TOKEN": "should-not-pass",
            "ZEIBAEL_TEST_PRIVATE_VALUE": "should-not-pass",
        }
        safe = safe_job_environment(values)
        for name in ("ProgramFiles", "ProgramFiles(x86)", "ProgramData",
                     "CommonProgramFiles", "CommonProgramFiles(x86)",
                     "HOMEDRIVE", "HOMEPATH",
                     "COMSPEC", "PATHEXT", "DOTNET_ROOT", "SystemDrive"):
            self.assertEqual(safe[name], values[name])
        for name in ("GITHUB_TOKEN", "NUGET_AUTH_TOKEN", "ZEIBAEL_TEST_PRIVATE_VALUE"):
            self.assertNotIn(name, safe)

    def test_kotlin_windows_resolves_batch_compiler(self):
        with patch("scripts.ci_driver.shutil.which", side_effect=lambda x:
                   r"C:\\Kotlin\\bin\\kotlinc.bat" if x == "kotlinc.bat" else None):
            self.assertEqual(
                resolve_job_command(["kotlinc", "-version"], runner_os="Windows"),
                [r"C:\\Kotlin\\bin\\kotlinc.bat", "-version"],
            )

    def test_kotlin_non_windows_stays_unchanged(self):
        self.assertEqual(
            resolve_job_command(["kotlinc", "-version"], runner_os="Linux"),
            ["kotlinc", "-version"],
        )

    def test_missing_windows_kotlinc_is_attributed_to_runtime(self):
        with patch("scripts.ci_driver.shutil.which", return_value=None):
            with self.assertRaisesRegex(FileNotFoundError, "Kotlin"):
                resolve_job_command(["kotlinc", "-version"], runner_os="Windows")


if __name__ == "__main__":
    unittest.main()
