"""Safety contract for reviewed acquisition jobs; no provider execution."""
import importlib.util
import unittest
from pathlib import Path
from scripts.job_plan import read_manifest

class Admission(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("scripts.acquisition_admission"),"admission module missing")
        from scripts import acquisition_admission
        self.a=acquisition_admission
        self.request={"purpose":"development_test","sensitivity":"public_safe","source_access":"allowed",
                      "free_entitlement":"verified","job_id":"acquisition_owned_public","parameters":{}}

    def test_known_reviewed_fixed_job(self):
        self.assertEqual(self.a.admit_compute(self.request)["decision"],"ADMIT")
        self.assertEqual(self.a.admit_compute({**self.request,"job_id":"acquisition_archive_example"})["decision"],"ADMIT")
        self.assertIsNotNone(read_manifest(Path.cwd(),"acquisition_archive_example"))

    def test_reject_untrusted_unknown_and_paid_inputs(self):
        for patch in [{"job_id":"arbitrary_crawl"},{"sensitivity":"private"},{"purpose":"production_crawl"},
                      {"free_entitlement":"unknown"},{"free_entitlement":"trial"},{"source_access":"unknown"},
                      {"source_access":"denied"},{"parameters":{"url":"https://example.org/"}},
                      {"extra":"unexpected"},{"job_id":"spider_cloud"}]:
            with self.subTest(patch=patch):
                self.assertEqual(self.a.admit_compute({**self.request,**patch})["decision"],"STOP")

    def test_terminal_source_and_quota_stops(self):
        for reason in ["rate_limited","access_denied","robots_denied","robots_unavailable",
                       "provider_quota","billing_required","unknown"]:
            self.assertEqual(self.a.fallback_policy(reason),"STOP")
        self.assertEqual(self.a.fallback_policy("technical_failure"),"RECHECK_ELIGIBLE_ALTERNATIVE")

if __name__=="__main__":unittest.main()
