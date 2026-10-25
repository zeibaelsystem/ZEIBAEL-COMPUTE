#!/usr/bin/env python3
"""Bounded public scientific workflow. No private data or live trading orders."""
import csv
import json
import math
import os
import random
import statistics
from pathlib import Path


def validate_prices(values):
    if not isinstance(values, (list, tuple)) or not all(
        isinstance(x, (int, float)) and not isinstance(x, bool)
        and math.isfinite(x) and x > 0 for x in values
    ):
        raise ValueError("Prices must be positive finite numbers")
    if len(values) > 100_000:
        raise ValueError("ZEIBAEL public fixture length exceeds internal compute budget")
    return [float(x) for x in values]


def backtest_long_only(prices, short_window=3, long_window=7, fee_bps=18):
    """Yesterday's rolling close generates today's long/cash exposure.

    Fees+slippage charged per change, no same-bar signal/execution, no shorts,
    leverage, private source, future data, or order submission.
    """
    values = validate_prices(prices)
    if (not isinstance(short_window, int) or isinstance(short_window, bool)
        or not isinstance(long_window, int) or isinstance(long_window, bool)
        or not 1 <= short_window < long_window or len(values) <= long_window):
        raise ValueError("Invalid SMA windows or insufficient bars")
    if (not isinstance(fee_bps, (int, float)) or isinstance(fee_bps, bool)
        or not math.isfinite(fee_bps) or not 0 <= fee_bps < 10_000):
        raise ValueError("Invalid transaction cost bps")
    equity = peak = 1.0
    max_drawdown = 0.0
    position = 0
    turns = 0
    first_entry = None
    curve = [(0, equity, 0)]
    for t in range(1, len(values)):
        new_position = 0
        if t >= long_window:
            short_mean = statistics.fmean(values[t-short_window:t])
            long_mean = statistics.fmean(values[t-long_window:t])
            new_position = int(short_mean > long_mean)
        if new_position != position:
            equity *= 1.0 - fee_bps / 10_000.0
            turns += 1
            if new_position == 1 and first_entry is None:
                first_entry = t
        daily_return = values[t] / values[t-1] - 1.0
        equity *= 1.0 + new_position * daily_return
        position = new_position
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, 1.0 - equity / peak)
        curve.append((t, equity, position))
    return {
        "strategy": "lagged_long_only_sma",
        "ending_equity": round(equity, 12),
        "total_return_pct": round((equity - 1.0) * 100, 6),
        "max_drawdown_pct": round(max_drawdown * 100, 6),
        "first_entry_index": first_entry,
        "turnover_events": turns,
        "position_at_end": position,
        "fee_plus_slippage_bps_per_turn": fee_bps,
        "no_lookahead": True,
        "equity_curve": curve,
    }


def monte_carlo_summary(seed=2026, trials=500, steps=40, drift=0.0002, volatility=0.01):
    if (not isinstance(seed, int) or isinstance(seed, bool)
        or not isinstance(trials, int) or isinstance(trials, bool)
        or not isinstance(steps, int) or isinstance(steps, bool)
        or not 1 <= trials <= 2000 or not 1 <= steps <= 1000
        or not math.isfinite(drift) or not math.isfinite(volatility)
        or volatility < 0):
        raise ValueError("Invalid bounded simulation parameters")
    rng = random.Random(seed)
    final = []
    for _ in range(trials):
        value = 1.0
        for _ in range(steps):
            value *= math.exp(rng.gauss(drift, volatility))
        final.append(value)
    final.sort()
    return {
        "seed": seed,
        "trials": trials,
        "steps": steps,
        "mean_terminal_value": round(statistics.fmean(final), 9),
        "p05_terminal_value": round(final[int((len(final) - 1) * .05)], 9),
        "p95_terminal_value": round(final[int((len(final) - 1) * .95)], 9),
    }


def run():
    # Dependencies are installed only by a reviewed FREE-ONLY manifest.
    import numpy as np
    import pandas as pd
    from scipy.optimize import minimize_scalar

    root = Path(__file__).resolve().parents[1]
    csv_path = root / "ci" / "fixtures" / "science" / "public_demo_prices.csv"
    if csv_path.stat().st_size > 5_000_000:
        raise ValueError("ZEIBAEL internal public CSV size budget exceeded")
    frame = pd.read_csv(csv_path, comment="#", parse_dates=["date"])
    if list(frame.columns) != ["date", "close"] or len(frame) <= 7 or len(frame) > 100_000:
        raise ValueError("Unexpected public fixture schema/size")
    if (frame["date"].isna().any() or frame["date"].duplicated().any()
        or not frame["date"].is_monotonic_increasing):
        raise ValueError("Public dates invalid, unordered, or duplicated")
    prices = validate_prices(frame["close"].tolist())
    log_returns = np.diff(np.log(np.asarray(prices, dtype=np.float64)))
    stats = {
        "rows": len(prices),
        "mean_close": round(float(np.mean(prices)), 6),
        "sample_std_log_return": round(float(np.std(log_returns, ddof=1)), 9),
        "median_close": round(float(frame["close"].median()), 6),
        "min_close": round(float(np.min(prices)), 6),
        "max_close": round(float(np.max(prices)), 6),
    }
    # Smoke validation of a known convex objective, not optimization of trades.
    opt = minimize_scalar(lambda x: (x - 1.75)**2 + 0.1,
                          bounds=(0.0, 4.0), method="bounded",
                          options={"xatol": 1e-9})
    if not opt.success or abs(opt.x - 1.75) > 0.00001:
        raise AssertionError("SciPy optimization smoke failed")
    strategy = backtest_long_only(prices, short_window=3, long_window=7, fee_bps=18)
    curve = strategy.pop("equity_curve")
    report = {
        "schema": 1,
        "dataset": "SYNTHETIC_PUBLIC_NON_MARKET_DEMO",
        "libraries": {"numpy": np.__version__, "pandas": pd.__version__},
        "statistics": stats,
        "simulation": monte_carlo_summary(),
        "optimization": {"solver": "scipy.optimize.minimize_scalar",
                         "converged": bool(opt.success),
                         "argmin": round(float(opt.x), 8),
                         "minimum_value": round(float(opt.fun), 8)},
        "backtest": strategy,
        "note": "Synthetic, in-sample educational demo. No live orders or investment advice.",
    }
    output_root = os.environ.get("ZEIBAEL_OUTPUT_DIR")
    if not output_root:
        raise ValueError("ZEIBAEL_OUTPUT_DIR required for public output")
    out = Path(output_root) / "files"
    out.mkdir(parents=True, exist_ok=True)
    (out / "scientific_summary.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    with (out / "equity_curve.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["bar_index", "equity", "position"])
        writer.writerows(curve)
    print("ZEIBAEL_SCIENTIFIC_STATS_OK")
    print("ZEIBAEL_SCIENTIFIC_MONTE_CARLO_OK")
    print("ZEIBAEL_SCIENTIFIC_OPTIMIZATION_OK")
    print("ZEIBAEL_SCIENTIFIC_BACKTEST_OK")
    print("ZEIBAEL_SCIENTIFIC_RESULT_JSON=" + json.dumps(report, separators=(",", ":")))


if __name__ == "__main__":
    run()
