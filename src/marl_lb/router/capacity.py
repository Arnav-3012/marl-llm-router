"""Saturation criteria on a live run's own events (ADR-011 on the live cluster). Tier B."""

from __future__ import annotations

import numpy as np

THRESHOLDS = {"completion_min": 0.95, "drop_max": 0.01, "backlog_max": 1.5}


def criteria_from_events(events: list, window_s: float, n_samples: int = 400) -> dict:
    """The three ADR-011 criteria from a run's event log (arrival window [0, window_s])."""
    arrive = {e["req"]: e["t"] for e in events if e["e"] == "arrive" and e["t"] < window_s}
    done = {e["req"]: e for e in events if e["e"] == "resolve"}
    n = max(len(arrive), 1)
    completed_in = sum(
        1 for r in arrive if r in done and done[r]["status"] == "done" and done[r]["t"] <= window_s
    )
    dropped = sum(1 for r in arrive if r in done and done[r]["status"] != "done")
    ts = np.linspace(0, window_s, n_samples, endpoint=False)
    a = np.array(list(arrive.values())) if arrive else np.zeros(0)
    end = (
        np.array([done[r]["t"] if r in done else np.inf for r in arrive]) if arrive else np.zeros(0)
    )
    count = (
        ((a[None, :] <= ts[:, None]) & (end[None, :] > ts[:, None])).sum(axis=1)
        if len(a)
        else np.zeros(n_samples)
    )
    q = n_samples // 4
    q2, q4 = count[q : 2 * q].mean(), count[3 * q :].mean()
    return {
        "n_arrived": len(arrive),
        "completion_ratio": completed_in / n,
        "drop_rate": dropped / n,
        "backlog_ratio": float(q4 / q2) if q2 > 0 else 1.0,
    }
