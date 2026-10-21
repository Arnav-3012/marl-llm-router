"""Live showdown on the REAL servers: every policy on the same requests, fixed rates. Tier B.

uv run python -m scripts.live_showdown [--rates 0.15,0.30] [--seconds 120] [--policies a,b,...]

Needs the router on the real servers (docs/DEMO.md; start it with --robust-exp e8_robust to include
the robust agents) and nothing else running. For each rate (requests per second, an absolute number
because the quick capacity probe is noisy) it replays the same held-out slice (same seed) once per
policy, one run after the other, and writes results/live/comparison_<time>_rate<r>.json in the same
format as the guided test (ranking by goodput, mode "real"); the dashboard picks these files up.
Takes about len(rates) x len(policies) x (seconds + drain) seconds.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime

import httpx

from marl_lb.config import ROOT
from marl_lb.router.livecheck import LABEL

LIVE = ROOT / "results" / "live"
KEYS = (
    "goodput_rps", "sla_attainment", "drop_rate", "ttft_p50", "ttft_p95", "cost_per_request",
    "n_arrived", "n_completed", "n_sla_met",
)  # fmt: skip
DEFAULT = "sed_global,route_to_fast,route_to_fast_shed,ddqn_agents,ddqn_robust"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--rates", default="0.15,0.30")
    ap.add_argument("--seconds", type=float, default=120.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument(
        "--drain", type=float, default=None, help="stop waiting this long after the last arrival"
    )
    ap.add_argument("--policies", default=DEFAULT)
    a = ap.parse_args()
    c = httpx.Client(base_url=a.api, timeout=60)
    h = c.get("/health").json()
    if h["status"] != "ok" or h["mode"] != "real":
        print(f"NOT READY: router {h['status']}, mode {h['mode']}", file=sys.stderr)
        return 1
    for rate in [float(x) for x in a.rates.split(",")]:
        rows, slices = [], set()
        for pol in a.policies.split(","):
            r = c.post(
                "/simulate",
                json={
                    "policy": pol,
                    "rate_rps": rate,
                    "seconds": a.seconds,
                    "seed": a.seed,
                    "drain_s": a.drain,
                },
            )
            if r.status_code != 200:
                print(f"skip {pol}: {r.status_code} {r.text}", flush=True)
                continue
            run_id = r.json()["run_id"]
            print(f"{datetime.now():%H:%M:%S} {rate} req/s {pol} -> {run_id}", flush=True)
            while c.get("/simulate/status").json()["state"] == "running":
                time.sleep(2)
            d = LIVE / run_id
            m = json.loads((d / "metrics.json").read_text())
            sl = json.loads((d / "slice.json").read_text())["slice_id"]
            slices.add(sl)
            rows.append({"policy": pol, "label": LABEL.get(pol, pol), "run_id": run_id, "m": m})
            print(
                f"   goodput {m['goodput_rps']:.3f}, met both {m['sla_attainment']:.0%}, "
                f"refused {m['drop_rate']:.1%}, TTFT p95 {m['ttft_p95']}",
                flush=True,
            )
            time.sleep(5)
        rows.sort(key=lambda x: -x["m"]["goodput_rps"])
        doc = {
            "created": datetime.now().isoformat(timespec="seconds"),
            "mode": "real",
            "rho": None,
            "rate_rps": rate,
            "capacity_rps": None,
            "seconds": a.seconds,
            "seed": a.seed,
            "same_slice": len(slices) == 1,
            "slice_ids": sorted(slices),
            "kind": "main",
            "drain_s": a.drain,
            "note": "one run per policy is an anecdote, not a result",
            "ranking": [
                {"rank": i + 1, "policy": x["policy"], "label": x["label"], "run_id": x["run_id"],
                 **{k: x["m"].get(k) for k in KEYS}}
                for i, x in enumerate(rows)
            ],
        }  # fmt: skip
        name = f"comparison_{datetime.now():%Y%m%d-%H%M%S}_rate{rate}.json"
        LIVE.mkdir(parents=True, exist_ok=True)
        (LIVE / name).write_text(json.dumps(doc, indent=2, default=float))
        print(f"wrote results/live/{name}", flush=True)
    print(f"DONE live_showdown {datetime.now():%H:%M:%S}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
