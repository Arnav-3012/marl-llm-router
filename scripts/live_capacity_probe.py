"""Real capacity probe (Sh.L3): the ADR-011 criteria on the live cluster. Tier B.

uv run python -m scripts.live_capacity_probe [--api http://127.0.0.1:8000] [--window 60]
    [--seeds 0,1]

Needs the router running (docs/DEMO.md) on the REAL servers, with nothing else running on the
machine.
For each arrival rate on a geometric grid (then bisection between the last passing and first failing
rate) it replays the held-out slice through the router with the baseline policy (SED global) for
`--window` seconds, one run at a time, and applies the ADR-011 saturation criteria to the run's own
events: completion ratio < 0.95, drop rate > 1%, or backlog growth (mean in-system count over the
last quarter of the window above 1.5 times that of the second quarter). The smallest saturated rate
is the REAL lambda_sat, written to results/live/real_lambda_sat.json; Simulate load is then
rho x this number. Takes about (grid points + refine steps) x seeds x (window + drain) seconds.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime

import httpx
import numpy as np

from marl_lb.config import ROOT
from marl_lb.eval.saturation import find_lambda_sat
from marl_lb.router.capacity import THRESHOLDS, criteria_from_events
from marl_lb.router.runs import machine_info

OUT = ROOT / "results" / "live"


class Probe:
    def __init__(
        self, client, window_s: float, seeds: list, policy: str = "sed_global", poll_s: float = 1.0
    ):
        self.c, self.window, self.seeds, self.policy, self.poll = (
            client,
            window_s,
            seeds,
            policy,
            poll_s,
        )
        self.points: list[dict] = []

    def run_once(self, rate: float, seed: int) -> dict:
        r = self.c.post(
            "/simulate",
            json={"policy": self.policy, "rate_rps": rate, "seconds": self.window, "seed": seed},
        )
        if r.status_code != 200:
            raise RuntimeError(f"/simulate refused: {r.status_code} {r.text}")
        run_id = r.json()["run_id"]
        while self.c.get("/simulate/status").json()["state"] == "running":
            time.sleep(self.poll)
        events = self.c.get(f"/runs/{run_id}/events").json()["events"]
        crit = criteria_from_events(events, self.window)
        self.points.append({"rate_rps": rate, "seed": seed, "run_id": run_id, **crit})
        return crit

    def evaluate(self, rate: float) -> dict:
        rows = [self.run_once(rate, s) for s in self.seeds]
        return {
            k: float(np.mean([x[k] for x in rows]))
            for k in ("completion_ratio", "drop_rate", "backlog_ratio")
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--window", type=float, default=60.0)
    ap.add_argument("--seeds", default="0,1")
    ap.add_argument("--grid", default="0.1,0.2,0.4,0.8,1.6", help="arrival rates, req/s")
    ap.add_argument("--refine", type=int, default=3)
    a = ap.parse_args()
    client = httpx.Client(base_url=a.api, timeout=60)
    h = client.get("/health").json()
    if h["status"] != "ok" or h["mode"] != "real":
        print(
            f"NOT READY: router {h['status']}, mode {h['mode']}; needs 4 healthy REAL servers",
            file=sys.stderr,
        )
        return 1
    probe = Probe(client, a.window, [int(s) for s in a.seeds.split(",")])
    grid = [float(x) for x in a.grid.split(",")]
    found = find_lambda_sat(probe.evaluate, grid, a.refine, THRESHOLDS)
    lam = found["lambda_sat_rps"]
    OUT.mkdir(parents=True, exist_ok=True)
    doc = {
        "lambda_sat_rps": None if lam is None else float(lam),
        "policy": probe.policy,
        "window_s": a.window,
        "seeds": probe.seeds,
        "thresholds": THRESHOLDS,
        "points": probe.points,
        "measured": datetime.now().isoformat(timespec="seconds"),
        "machine": machine_info(),
    }
    if lam is None:
        print("The whole grid passes: raise --grid and run again (no saturation rate written).")
        (OUT / "real_lambda_sat_incomplete.json").write_text(
            json.dumps(doc, indent=2, default=float)
        )
        return 2
    (OUT / "real_lambda_sat.json").write_text(json.dumps(doc, indent=2, default=float))
    print(f"real lambda_sat = {lam:.3f} req/s (simulated: see results/saturation)")
    print(f"DONE live_capacity_probe {datetime.now().isoformat(timespec='seconds')}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
