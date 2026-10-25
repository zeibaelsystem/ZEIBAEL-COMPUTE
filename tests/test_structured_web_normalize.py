"""Regression tests for FREE-ONLY offline evidence deduplication."""

import unittest
from scripts.structured_web_normalize import normalize_projects


class TestStructuredWebNormalize(unittest.TestCase):
    def setUp(self):
        self.row = {
            "company": "Example Cell Co", "country": "France",
            "location": "Amiens", "facility_type": "cell",
            "chemistry_scope": "sodium-ion",
            "capacity_gwh_per_year": 5, "capacity_basis": "cell",
            "status": "announced", "event_date": "2026-05-01",
            "event_type": "announcement",
            "source_url": "https://example.org/release-a",
        }

    def test_dedupe_keeps_both_sources_and_events(self):
        next_row = {**self.row, "source_url": "https://example.org/release-b",
                    "event_date": "2026-06-01", "event_type": "update"}
        result = normalize_projects([self.row, next_row])
        self.assertEqual(result["summary"]["distinct_projects"], 1)
        self.assertEqual(len(result["projects"][0]["sources"]), 2)
        self.assertEqual(len(result["projects"][0]["events"]), 2)
        self.assertEqual(result["projects"][0]["first_announced_date"], "2026-05-01")

    def test_bess_and_cell_never_merge_or_sum(self):
        second = {**self.row, "facility_type": "bess",
                  "capacity_basis": "bess", "capacity_gwh_per_year": 4}
        result = normalize_projects([self.row, second])
        self.assertEqual(result["summary"]["distinct_projects"], 2)
        self.assertEqual([p["capacity_gwh_per_year"][0]["value"]
                          for p in result["projects"]], [4.0, 5.0])

    def test_conflicting_capacity_flagged_without_averaging(self):
        second = {**self.row, "capacity_gwh_per_year": 9,
                  "source_url": "https://example.org/new"}
        result = normalize_projects([self.row, second])
        project = result["projects"][0]
        self.assertEqual(len(project["capacity_gwh_per_year"]), 2)
        self.assertIn("conflicting_capacity_reports", project["review_reasons"])

    def test_unknown_location_no_merge(self):
        a = {**self.row, "location": None}
        b = {**a, "source_url": "https://example.org/other"}
        result = normalize_projects([a, b])
        self.assertEqual(result["summary"]["distinct_projects"], 2)
        self.assertTrue(all("unknown_location_no_automatic_merge" in p["review_reasons"]
                            for p in result["projects"]))

    def test_project_id_preserves_independent_expansions(self):
        a = {**self.row, "project_id": "phase-1"}
        b = {**self.row, "project_id": "phase-2"}
        self.assertEqual(normalize_projects([a, b])["summary"]["distinct_projects"], 2)

    def test_missing_source_flagged_not_invented(self):
        a = {**self.row, "source_url": None}
        result = normalize_projects([a])
        self.assertEqual(result["projects"][0]["sources"], [])
        self.assertIn("missing_source_url", result["projects"][0]["review_reasons"])

    def test_non_numeric_capacity_not_fabricated(self):
        a = {**self.row, "capacity_gwh_per_year": "not announced"}
        result = normalize_projects([a])
        self.assertEqual(result["projects"][0]["capacity_gwh_per_year"], [])
        self.assertIn("capacity_not_verified", result["projects"][0]["review_reasons"])

    def test_construction_date_does_not_become_announcement(self):
        a = {**self.row, "event_type": "construction"}
        self.assertIsNone(normalize_projects([a])["projects"][0]["first_announced_date"])


if __name__ == "__main__":
    unittest.main()
