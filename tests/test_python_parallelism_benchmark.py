"""Regression tests for the reviewed public Python parallelism benchmark."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.python_parallelism_benchmark import cpu_task, run_benchmark, publish_report


class PythonParallelismBenchmarkTests(unittest.TestCase):
    def test_cpu_task_is_deterministic_for_identical_work(self):
        self.assertEqual(cpu_task(10000), cpu_task(10000))
        self.assertNotEqual(cpu_task(10000), cpu_task(10001))

    def test_same_results_across_sequential_thread_and_process(self):
        result = run_benchmark(workers=2, iterations=10000, repeats=1)
        self.assertEqual(set(result['strategies']), {'sequential', 'threading', 'multiprocessing'})
        self.assertEqual(result['workload']['tasks'], 2)
        self.assertEqual(result['workload']['iterations_per_task'], 10000)
        for measurement in result['strategies'].values():
            self.assertEqual(len(measurement['seconds']), 1)
            self.assertGreater(measurement['median_seconds'], 0)
            self.assertEqual(measurement['work_digest_count'], 2)
        self.assertTrue(result['all_results_equal'])

    def test_invalid_work_is_rejected(self):
        for kwargs in [{'workers': 0}, {'iterations': 0}, {'repeats': 0}]:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    run_benchmark(**dict({'workers': 2, 'iterations': 100, 'repeats': 1}, **kwargs))

    def test_writes_public_result_only_when_output_dir_exists(self):
        result = run_benchmark(workers=1, iterations=100, repeats=1)
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {'ZEIBAEL_OUTPUT_DIR': tmp}):
                output = publish_report(result)
            self.assertEqual(output, Path(tmp) / 'files' / 'python-parallelism.json')
            self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['workload']['tasks'], 1)


if __name__ == '__main__':
    unittest.main()
