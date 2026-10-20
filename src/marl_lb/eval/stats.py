"""Mean and 95% confidence interval across seeds. Tier A.

With n seeds the sample mean has standard error s / sqrt(n); the 95% half-width uses Student's t
with
n - 1 degrees of freedom (not 1.96: with 5 seeds the t value is 2.776, so the interval is wider than
the normal-approximation one). One seed gives no interval (nan): a single seed is never a result.
"""

from __future__ import annotations

import numpy as np
from scipy import stats


def mean_ci(values, confidence: float = 0.95) -> tuple[float, float]:
    """(mean, half-width of the confidence interval)."""
    x = np.asarray(values, dtype=float)
    n = len(x)
    if n == 0:
        raise ValueError("no values")
    if n == 1:
        return float(x[0]), float("nan")
    sem = x.std(ddof=1) / np.sqrt(n)
    return float(x.mean()), float(sem * stats.t.ppf((1 + confidence) / 2, n - 1))


def aggregate(runs: list, keys: list) -> dict:
    """Per key: {mean, ci, n} over a list of per-seed metric dicts (NaN values are dropped and
    counted).
    """
    out = {}
    for k in keys:
        vals = [r[k] for r in runs if k in r and r[k] is not None and np.isfinite(r[k])]
        if not vals:
            out[k] = {"mean": None, "ci": None, "n": 0}
            continue
        m, ci = mean_ci(vals)
        out[k] = {"mean": m, "ci": None if np.isnan(ci) else ci, "n": len(vals)}
    return out
