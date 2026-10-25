"""Contract tests for browser automation and scientific compute smoke jobs."""
import json
import math
import tempfile
import unittest
from pathlib import Path

from scripts.job_plan import read_manifest
from scripts.scientific_compute import backtest_long_only, validate_prices, monte_carlo_summary

ROOT = Path(__file__).resolve().parents[1]


class BrowserScientificContractTests(unittest.TestCase):
    def test_three_playwright_browsers_and_real_screenshot_artifacts(self):
        doc = read_manifest(ROOT, "playwright_browser_smoke")
        by_id = {job["id"]: job for job in doc["jobs"]}
        self.assertEqual(set(by_id), {"browser_chromium", "browser_firefox", "browser_webkit"})
        for name, job in by_id.items():
            browser = name.split("_", 1)[1]
            self.assertEqual(job["runtime"], "node")
            self.assertEqual(job["runner"], "ubuntu-24.04")
            self.assertTrue(job["output_files"])
            self.assertEqual(job["requirements"]["os"], "linux")
            self.assertEqual(job["requirements"]["toolchains"], ["node", "npm"])
            commands = job["commands"]
            self.assertTrue(any(browser in args and "install" in args
                                for args in commands))
            self.assertTrue(any(any(part.endswith("/browser_matrix.mjs") for part in args)
                                and browser in args for args in commands))
        chromium_commands = by_id["browser_chromium"]["commands"]
        self.assertTrue(any(any(part.endswith("/playwright_smoke.mjs") for part in c)
                            for c in chromium_commands))

    def test_browser_fixture_has_real_local_ui_interaction_and_screenshot(self):
        content = (ROOT / "ci/fixtures/web/browser_matrix.mjs").read_text()
        self.assertIn("127.0.0.1", content)
        self.assertIn(".screenshot(", content)
        self.assertIn(".click(", content)
        self.assertIn("BROWSER_MATRIX_", content)
        self.assertIn("ZEIBAEL_OUTPUT_DIR", content)
        self.assertNotIn("process.env.GITHUB_TOKEN", content)

    def test_scientific_smoke_is_public_and_bounded(self):
        job = read_manifest(ROOT, "scientific_compute_smoke")["jobs"][0]
        self.assertEqual(job["runner"], "ubuntu-24.04")
        self.assertEqual(job["runtime"], "python")
        self.assertTrue(job["output_files"])
        self.assertEqual(job["requirements"]["os"], "linux")
        self.assertLessEqual(job["requirements"]["output_mb"], 5)
        self.assertTrue(any("pip" in command for command in job["commands"]))
        self.assertTrue(any(any(part.endswith("/scientific_compute.py") for part in command)
                            for command in job["commands"]))

    def test_scientific_demo_prices_are_public_synthetic_csv(self):
        path = ROOT / "ci/fixtures/science/public_demo_prices.csv"
        self.assertTrue(path.is_file())
        self.assertIn("SYNTHETIC", path.read_text().splitlines()[0])
        self.assertGreater(len(path.read_text().splitlines()), 15)


class BacktestIntegrityTests(unittest.TestCase):
    def test_validate_prices_rejects_invalid_data(self):
        with self.assertRaises(ValueError):
            validate_prices([1.0, 0.0, 3.0])
        with self.assertRaises(ValueError):
            validate_prices([1, float("nan"), 3])

    def test_signal_uses_only_past_prices(self):
        values = [10.0, 10.5, 11.0, 11.5, 12.0, 13.0, 14.0, 15.0]
        result = backtest_long_only(values, short_window=2, long_window=4, fee_bps=18)
        self.assertGreaterEqual(result["first_entry_index"], 4)
        self.assertEqual(result["first_entry_index"], 4)

    def test_fees_reduce_equity_with_same_signals(self):
        values = [10, 11, 12, 13, 14, 12, 11, 10, 12, 14, 16, 18]
        no_fee = backtest_long_only(values, short_window=2, long_window=4, fee_bps=0)
        fee = backtest_long_only(values, short_window=2, long_window=4, fee_bps=18)
        self.assertLess(fee["ending_equity"], no_fee["ending_equity"])
        self.assertGreater(fee["turnover_events"], 0)

    def test_seeded_simulation_is_reproducible(self):
        a = monte_carlo_summary(seed=17, trials=200, steps=12)
        b = monte_carlo_summary(seed=17, trials=200, steps=12)
        self.assertEqual(a, b)
        self.assertEqual(a["trials"], 200)

    def test_backtest_rejects_insufficient_bars(self):
        with self.assertRaises(ValueError):
            backtest_long_only([1, 2, 3], short_window=2, long_window=4, fee_bps=18)


if __name__ == "__main__":
    unittest.main()
