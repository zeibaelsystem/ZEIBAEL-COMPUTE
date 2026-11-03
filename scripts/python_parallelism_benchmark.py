#!/usr/bin/env python3
"""Reproducible public CPU-bound Python benchmark for ZEIBAEL-COMPUTE.

Measures Python pure-bytecode workloads with warm executor pools. Measures
elapsed wall time only and does not pretend worker CPU time was observed.
No secrets, network, third-party dependencies, or private inputs.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import json
import multiprocessing
import os
from pathlib import Path
import platform
import statistics
import sys
import time


def cpu_task(iterations):
    """A deterministic Python-integer workload that retains the GIL."""
    state = 0
    for i in range(iterations):
        state = (state * 1664525 + i + 1013904223) & 0xffffffff
    return state


def _timed_tasks(executor, workers, iterations):
    start = time.perf_counter()
    if executor is None:
        result = [cpu_task(iterations) for _ in range(workers)]
    else:
        result = list(executor.map(cpu_task, [iterations] * workers))
    return time.perf_counter() - start, result


def run_benchmark(workers=4, iterations=4000000, repeats=3):
    """Run the same public CPU work in three strategies, validating outputs."""
    if any(type(x) is not int or x < 1 for x in (workers, iterations, repeats)):
        raise ValueError('workers, iterations and repeats must be positive integers')

    strategies = {}
    expected = [cpu_task(iterations)] * workers
    for label, executor_class in (
        ('sequential', None),
        ('threading', ThreadPoolExecutor),
        ('multiprocessing', ProcessPoolExecutor),
    ):
        durations = []
        if executor_class is None:
            # Warm interpreter and task before recording wall time.
            cpu_task(min(iterations, 10000))
            for _ in range(repeats):
                elapsed, results = _timed_tasks(None, workers, iterations)
                if results != expected:
                    raise AssertionError(label + ' changed computation results')
                durations.append(elapsed)
        else:
            executor_kwargs = ({"mp_context": multiprocessing.get_context("spawn")}
                               if label == "multiprocessing" else {})
            with executor_class(max_workers=workers, **executor_kwargs) as pool:
                # Executor start-up is deliberately excluded; report this fact.
                list(pool.map(cpu_task, [1000] * workers))
                for _ in range(repeats):
                    elapsed, results = _timed_tasks(pool, workers, iterations)
                    if results != expected:
                        raise AssertionError(label + ' changed computation results')
                    durations.append(elapsed)
        strategies[label] = {
            'seconds': [round(x, 6) for x in durations],
            'median_seconds': round(statistics.median(durations), 6),
            'work_digest_count': len(expected),
        }

    thread_time = strategies['threading']['median_seconds']
    process_time = strategies['multiprocessing']['median_seconds']
    sequential_time = strategies['sequential']['median_seconds']
    return {
        'schema': 1,
        'source': 'public_synthetic_benchmark',
        'workload': {'tasks': workers, 'iterations_per_task': iterations,
                     'repeats': repeats, 'pure_python_cpu_bound': True},
        'runtime': {'python': sys.version.split()[0], 'implementation': platform.python_implementation(),
                    'platform': platform.platform(), 'logical_cpu_count': os.cpu_count(),
                    'gil_enabled': sys._is_gil_enabled() if hasattr(sys, '_is_gil_enabled') else None},
        'method': {'wall_clock': 'time.perf_counter', 'warm_executor_pools': True,
                   'startup_included': False, 'worker_cpu_time_measured': False},
        'strategies': strategies,
        'all_results_equal': True,
        'ratios': {
            'threading_vs_process_speedup': round(thread_time / process_time, 5),
            'process_vs_sequential_speedup': round(sequential_time / process_time, 5),
        },
        'caveat': 'Machine workload, concurrency and system load can change timing. No cross-host speedup is guaranteed.',
    }


def publish_report(report):
    """Publish an artifact only into the restricted public CI output directory."""
    output_root = os.environ.get('ZEIBAEL_OUTPUT_DIR')
    if not output_root:
        return None
    directory = Path(output_root) / 'files'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'python-parallelism.json'
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--iterations', type=int, default=4000000)
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    report = run_benchmark(args.workers, args.iterations, args.repeats)
    publish_report(report)
    print('ZEIBAEL_PYTHON_PARALLELISM_JSON=' + json.dumps(report, separators=(',', ':')))


if __name__ == '__main__':
    main()
