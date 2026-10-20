"""lambda_sat: the arrival rate at which the global-SED cluster saturates (ADR-011). Tier B.

A rate is SATURATED if, averaged over seeds, ANY of these holds over the arrival window:
  * completion ratio < 0.95   (requests that finished inside the window / requests that arrived in
  it)
  * drop rate > 1%
  * backlog growth: mean in-system count over the last quarter of the window > 1.5 x its mean over
  the
    second quarter
(the thresholds are assumptions, ADR-011). lambda_sat is the smallest saturated rate on a geometric
grid,
refined by bisection between the last passing and the first failing grid rate.

find_lambda_sat takes a function rate -> aggregated criteria, so the search logic is tested on
synthetic
sweeps without running the simulator.
"""

from __future__ import annotations

import numpy as np

COMPLETION_MIN, DROP_MAX, BACKLOG_MAX = (
    0.95,
    0.01,
    1.5,
)  # ADR-011 assumptions; overridable via thresholds


def point_criteria(cluster, window_s: float) -> dict:
    """The three criteria and a few diagnostics from one finished episode (arrival window [0,
    window_s]).
    """
    reqs = cluster.run.requests
    arrived = [r for r in reqs if r.arrival < window_s]
    n = max(len(arrived), 1)
    completed_in = sum(1 for r in arrived if r.status == "done" and r.t_done <= window_s)
    dropped = sum(1 for r in arrived if r.status == "dropped")
    # in-system count at 400 sample times: arrived and not yet finished or dropped
    ts = np.linspace(0, window_s, 400, endpoint=False)
    arr = np.array([r.arrival for r in arrived])
    end = np.array([r.t_done if r.t_done is not None else np.inf for r in arrived])
    count = (
        ((arr[None, :] <= ts[:, None]) & (end[None, :] > ts[:, None])).sum(axis=1)
        if len(arrived)
        else np.zeros(400)
    )
    q2, q4 = count[100:200].mean(), count[300:400].mean()
    ok = [r for r in arrived if r.sla_met()]
    return {
        "n_arrived": len(arrived),
        "completion_ratio": completed_in / n,
        "drop_rate": dropped / n,
        "backlog_ratio": float(q4 / q2) if q2 > 0 else 1.0,
        "in_flight_at_end": float(count[-1] / n),
        "sla_attainment": len(ok) / n,
    }


def is_saturated(agg: dict, th: dict | None = None) -> bool:
    th = {
        "completion_min": COMPLETION_MIN,
        "drop_max": DROP_MAX,
        "backlog_max": BACKLOG_MAX,
        **(th or {}),
    }
    return (
        agg["completion_ratio"] < th["completion_min"]
        or agg["drop_rate"] > th["drop_max"]
        or agg["backlog_ratio"] > th["backlog_max"]
    )


def find_lambda_sat(evaluate, grid: list, refine_steps: int = 6, th: dict | None = None) -> dict:
    """Search lambda_sat. evaluate(rate) -> dict with completion_ratio, drop_rate, backlog_ratio
    (seed means).

    Returns lambda_sat (None if the whole grid passes), the evaluated points in rate order and a
    monotonicity report (completion ratio should not rise with the rate, beyond seed noise).
    """
    points: dict[float, dict] = {}

    def probe(rate: float) -> bool:
        if rate not in points:
            points[rate] = evaluate(rate)
        return is_saturated(points[rate], th)

    first_fail = None
    for rate in sorted(grid):
        if probe(rate):
            first_fail = rate
            break
    if first_fail is None:
        lam = None
    else:
        passing = [r for r in sorted(grid) if r < first_fail]
        lo, hi = (passing[-1] if passing else 0.0), first_fail
        for _ in range(refine_steps if passing else 0):
            mid = (lo + hi) / 2
            lo, hi = (lo, mid) if probe(mid) else (mid, hi)
        lam = hi
    for rate in sorted(grid):  # fill the rest of the grid so monotonicity can be checked
        probe(rate)
    ordered = [dict(rate=r, **points[r]) for r in sorted(points)]
    return {"lambda_sat_rps": lam, "points": ordered, "monotone": monotonicity(ordered)}


def monotonicity(points: list, noise: float = 0.02) -> dict:
    """Completion ratio should fall, drop rate and backlog ratio should rise, within seed noise."""
    bad = []
    for a, b in zip(points, points[1:], strict=False):
        if b["completion_ratio"] > a["completion_ratio"] + noise:
            bad.append(("completion_ratio", a["rate"], b["rate"]))
        if b["drop_rate"] < a["drop_rate"] - noise:
            bad.append(("drop_rate", a["rate"], b["rate"]))
        if b["backlog_ratio"] < a["backlog_ratio"] - 0.5:
            bad.append(("backlog_ratio", a["rate"], b["rate"]))
    return {"ok": not bad, "violations": bad}
