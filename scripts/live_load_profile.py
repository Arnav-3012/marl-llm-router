"""Real servers under realistic load (ADR-037, step 1). Tier B.

uv run python -m scripts.live_load_profile [--api http://127.0.0.1:8000] [--seconds 90]

Needs the router running on the REAL servers (docs/DEMO.md) with nothing else running. Replays the
held-out slice (seed 0) through the router, one run at a time, for each (policy, arrival rate) in
PLAN: requests generate exactly their recorded output length (ignore_eos) and each resolve event
carries the server's own prompt and decode timings. The run ids go to
results/live_profile/<timestamp>/runs.json; scripts/fit_load_calibration.py fits the simulator to
them. Takes about len(PLAN) x (seconds + drain) seconds (~15-20 min with the defaults).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime

import httpx

from marl_lb.config import ROOT
from marl_lb.router.runs import machine_info

# (policy, req/s): two placements (spread vs all-on-fast) over light -> heavy load, plus one run
# that loads the slow CPU servers, so both classes are seen busy. Fixed in ADR-037 before the run.
PLAN = [
    ("sed_global", 0.10),
    ("route_to_fast", 0.10),
    ("random", 0.10),
    ("sed_global", 0.20),
    ("route_to_fast", 0.20),
    ("sed_global", 0.30),
    ("route_to_fast", 0.30),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--seconds", type=float, default=90.0)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    c = httpx.Client(base_url=a.api, timeout=60)
    h = c.get("/health").json()
    if h["status"] != "ok" or h["mode"] != "real":
        print(f"NOT READY: router {h['status']}, mode {h['mode']}", file=sys.stderr)
        return 1
    out = ROOT / "results" / "live_profile" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    runs = []
    for policy, rate in PLAN:
        r = c.post(
            "/simulate",
            json={"policy": policy, "rate_rps": rate, "seconds": a.seconds, "seed": a.seed},
        )
        if r.status_code != 200:
            print(f"/simulate refused: {r.status_code} {r.text}", file=sys.stderr)
            return 1
        run_id = r.json()["run_id"]
        print(f"{datetime.now():%H:%M:%S} {policy} {rate} req/s -> {run_id}", flush=True)
        while c.get("/simulate/status").json()["state"] == "running":
            time.sleep(2)
        m = c.get("/simulate/status").json().get("metrics") or {}
        print(f"   SLA {m.get('sla_attainment')}, TTFT p95 {m.get('ttft_p95')}", flush=True)
        runs.append({"policy": policy, "rate_rps": rate, "run_id": run_id})
        (out / "runs.json").write_text(
            json.dumps(
                {"seconds": a.seconds, "seed": a.seed, "runs": runs, "machine": machine_info()},
                indent=2,
            )
        )
        time.sleep(5)  # let the servers go idle between runs
    print(f"DONE live_load_profile {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
