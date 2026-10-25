"""Windows os.environ uppercase-key regression for NuGet and .NET restore.

Windows Python os.environ normalizes keys to uppercase; ZEIBAEL safe allowlist
must match regardless of case without admitting credential variables.
"""
import unittest

from scripts.ci_driver import safe_job_environment


class WindowsEnvironmentCaseTests(unittest.TestCase):
    def test_windows_uppercase_programdata_and_common_program_files_pass(self):
        env = {
            "PATH": r"C:\\Windows\\System32",
            "PROGRAMDATA": r"C:\\ProgramData",
            "PROGRAMFILES": r"C:\\Program Files",
            "PROGRAMFILES(X86)": r"C:\\Program Files (x86)",
            "COMMONPROGRAMFILES": r"C:\\Program Files\\Common Files",
            "COMMONPROGRAMFILES(X86)": r"C:\\Program Files (x86)\\Common Files",
            "SYSTEMDRIVE": "C:",
            "APPDATA": r"C:\\Users\\runneradmin\\AppData\\Roaming",
            "DOTNET_ROOT": r"C:\\Program Files\\dotnet",
        }
        self.assertEqual(safe_job_environment(env), env)

    def test_uppercase_or_lowercase_secrets_still_excluded(self):
        env = {
            "PROGRAMDATA": r"C:\\ProgramData",
            "GITHUB_TOKEN": "token",
            "github_token": "another-token",
            "NUGET_API_KEY": "secret",
            "SECRET_KEY": "secret",
            "AZURE_CLIENT_SECRET": "secret",
            "Zeibael_Test_Private_Value": "secret",
        }
        self.assertEqual(
            safe_job_environment(env),
            {"PROGRAMDATA": r"C:\\ProgramData"},
        )

    def test_mixed_case_windows_names_preserved(self):
        env = {"ProgramData": r"C:\\ProgramData", "CommonProgramFiles": r"C:\\Common"}
        self.assertEqual(safe_job_environment(env), env)


if __name__ == "__main__":
    unittest.main()
