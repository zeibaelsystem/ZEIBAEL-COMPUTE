#!/usr/bin/env python3
"""Deterministic 20M-point Monte Carlo pi benchmark across GitHub OS runners.

Only public mathematical data. Per-run measured time excludes pip installation.
"""
import json
import math
import os
import platform
import statistics
import sys
import time

import numpy as np

TOTAL = 20_000_000
CHUNK = 1_000_000
SEED = 20261027
EXPECTED_INSIDE = 15_706_689
REPEATS = 3


def sample(seed, total, chunk):
    rng = np.random.default_rng(seed)
    inside = 0
    independent_geometry = 0
    generated = 0
    while generated < total:
        size = min(chunk, total - generated)
        x = rng.random(size)
        y = rng.random(size)
        inside += int(np.count_nonzero(x*x + y*y <= 1.0))
        independent_geometry += int(np.count_nonzero(np.hypot(x, y) <= 1.0))
        generated += size
    assert generated == total
    assert inside == independent_geometry, (inside, independent_geometry)
    return inside


def selftest():
    assert sample(SEED, 10007, 2000) == sample(SEED, 10007, 2000)
    assert 0 <= sample(SEED, 100, 31) <= 100
    assert sample(SEED, 10007, 2000) == sample(SEED, 10007, 10007)
    print("MONTE_CARLO_SELFTEST_PASS: reproducibility, count bounds, chunk invariance")


def benchmark():
    times = []
    hits = []
    for i in range(REPEATS):
        start = time.perf_counter()
        found = sample(SEED, TOTAL, CHUNK)
        elapsed = time.perf_counter() - start
        times.append(round(elapsed, 6))
        hits.append(found)
        print(f"MONTE_CARLO_REPEAT {i+1}/{REPEATS}: inside={found} elapsed_seconds={elapsed:.6f}")
    assert hits == [EXPECTED_INSIDE] * REPEATS, f"PCG64 / pi count differs: {hits}"
    estimate = 4 * hits[0] / TOTAL
    absolute_error = abs(estimate - math.pi)
    relative_error_percent = absolute_error / math.pi * 100
    theoretical_sigma = math.sqrt(math.pi * (4 - math.pi) / TOTAL)
    deviation_sigma = (estimate - math.pi) / theoretical_sigma
    assert abs(deviation_sigma) < 3
    report = {
        "status": "PASS",
        "os": platform.system(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "runner_os": os.environ.get("RUNNER_OS", "unknown"),
        "runner_arch": os.environ.get("RUNNER_ARCH", "unknown"),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "generator": "NumPy PCG64",
        "seed": SEED,
        "samples_per_repeat": TOTAL,
        "repeats": REPEATS,
        "total_samples_across_repeats": TOTAL * REPEATS,
        "inside": hits[0],
        "outside": TOTAL - hits[0],
        "pi_estimate": estimate,
        "math_pi": math.pi,
        "absolute_error": absolute_error,
        "relative_error_percent": relative_error_percent,
        "deviation_sigma": deviation_sigma,
        "compute_seconds_repeats": times,
        "compute_seconds_median": statistics.median(times),
        "timing_scope": "NumPy random generation + both geometry checks; excludes setup/pip/CI",
    }
    print("ZEIBAEL_MONTE_CARLO_JSON=" + json.dumps(report, sort_keys=True))
    print("MONTE_CARLO_BENCHMARK_PASS")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--selftest":
        selftest()
    elif len(sys.argv) == 1:
        benchmark()
    else:
        raise SystemExit("Usage: python scripts/monte_carlo_pi_benchmark.py [--selftest]")
