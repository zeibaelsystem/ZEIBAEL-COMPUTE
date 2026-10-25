"""Read-only diagnosis from GitHub job APIs: no dispatch, no write API."""
import json
import urllib.error
import urllib.request
import unittest
from unittest.mock import patch

from scripts.run_failure_report import diagnose_run, read_api, NoCrossHostAuth


class WorkflowFailureReporterTests(unittest.TestCase):
    def test_two_failed_jobs_report_first_root_cause_not_aggregate(self):
        payload = {"jobs": [
            {"id": 1001, "name": "dotnet-windows-x64", "conclusion": "failure",
             "started_at": "2026-10-25T09:06:01Z"},
            {"id": 1002, "name": "Aggregate machine-readable results",
             "conclusion": "failure", "started_at": "2026-10-25T09:07:00Z"}]}
        def fetch(url, token):
            self.assertEqual(token, "test-token")
            if url.endswith("/jobs?per_page=100"):
                return json.dumps(payload).encode()
            if url.endswith("/1001/logs"):
                return b"C:\\dotnet\\NuGet.targets(782,5): error : Value cannot be null. (Parameter 'path1')"
            return b"##[error]Process completed with exit code 1."
        with patch("scripts.run_failure_report.read_api", side_effect=fetch):
            report = diagnose_run("zeibaelsystem/ZEIBAEL-COMPUTE", 1234, "test-token")
        self.assertEqual(report["diagnosis"]["category"], "ZEIBAEL_INTERNAL")
        self.assertEqual(report["diagnosis"]["job"], "dotnet-windows-x64")
        self.assertEqual(report["failed_job_count"], 2)

    def test_inaccessible_logs_fail_closed_to_unknown(self):
        payload = {"jobs": [{"id": 123, "name": "build",
                             "conclusion": "failure", "started_at": ""}]}
        def fetch(url, token):
            if url.endswith("per_page=100"):
                return json.dumps(payload).encode()
            raise urllib.error.URLError("not accessible")
        with patch("scripts.run_failure_report.read_api", side_effect=fetch):
            report = diagnose_run("zeibaelsystem/ZEIBAEL-COMPUTE", 20, "token")
        self.assertEqual(report["diagnosis"]["category"], "UNKNOWN")

    def test_api_rejects_non_github_hosts(self):
        with self.assertRaisesRegex(ValueError, "Unexpected"):
            read_api("https://other.example.com/api", "fake")

    def test_authorization_not_forwarded_to_signed_log_host(self):
        req = urllib.request.Request("https://api.github.com/repos/owner/repo/actions/jobs/1/logs",
                                     headers={"Authorization": "Bearer fake"})
        redirect = NoCrossHostAuth().redirect_request(
            req, None, 302, "Found", {},
            "https://objects.githubusercontent.com/signed-logs")
        self.assertFalse(redirect.has_header("Authorization"))

    def test_invalid_run_id_and_repo_are_rejected(self):
        with self.assertRaises(ValueError):
            diagnose_run("other/../../outside", 1, "token")
        with self.assertRaises(ValueError):
            diagnose_run("owner/repo", 0, "token")


if __name__ == "__main__":
    unittest.main()
