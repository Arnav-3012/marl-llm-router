"""Rehearsal check before a live demo (Sh.L6): prints READY or NOT READY with the reason. Tier B.

uv run python -m scripts.demo_check [--api http://127.0.0.1:8000] [--seconds 60] [--rho 0.5]
    [--policy sed_global]

Read-only apart from the run it makes: (1) the router answers and all four backends are up, (2) a
short chat answers through a policy, (3) a baseline simulate of --seconds seconds finishes, (4) its
results folder holds config, slice, events, metrics and machine details. Exit code 0 only for READY.
Works against the mock router (the line then says MOCK) and the real one (which needs
results/live/real_lambda_sat.json).
"""

from __future__ import annotations

import argparse
import sys
import time

import httpx

REQUIRED = ("config.yaml", "slice.json", "events.jsonl", "metrics.json", "machine.json", "DONE")


def check(
    client,
    seconds: float = 60.0,
    rho: float = 0.5,
    policy: str = "sed_global",
    live_root=None,
    poll_s: float = 1.0,
    timeout_s: float = 900.0,
) -> tuple[bool, str]:
    """(ready, message). `client` is an httpx.Client or a FastAPI TestClient."""
    try:
        h = client.get("/health").json()
    except Exception as e:  # noqa: BLE001
        return False, f"NOT READY: the router does not answer ({e})"
    down = [b["name"] for b in h["backends"] if not b["up"]]
    if down:
        return False, f"NOT READY: servers not answering: {', '.join(down)}"
    r = client.post(
        "/chat", json={"prompt": "Say hello in five words.", "n_predict": 8, "policy": policy}
    )
    if r.status_code != 200:
        return False, f"NOT READY: a short chat failed ({r.status_code}: {r.text[:120]})"
    r = client.post("/simulate", json={"policy": policy, "rho": rho, "seconds": seconds, "seed": 0})
    if r.status_code != 200:
        return False, f"NOT READY: simulate refused ({r.status_code}: {r.text[:160]})"
    run_id = r.json()["run_id"]
    t0 = time.time()
    while client.get("/simulate/status").json()["state"] == "running":
        if time.time() - t0 > timeout_s:
            client.post("/simulate/stop")
            return (
                False,
                f"NOT READY: the {seconds:.0f} s run did not finish within {timeout_s:.0f} s",
            )
        time.sleep(poll_s)
    info = client.get(f"/runs/{run_id}")
    if info.status_code != 200:
        return False, f"NOT READY: run {run_id} has no results folder"
    if live_root is not None:
        missing = [f for f in REQUIRED if not (live_root / run_id / f).exists()]
        if missing:
            return False, f"NOT READY: results/live/{run_id} is missing {', '.join(missing)}"
    m = info.json()["metrics"]
    tag = " (MOCK: a rehearsal of the plumbing, not a result)" if h["mode"] == "mock" else ""
    return True, (
        f"READY{tag}: run {run_id}: {m['n_arrived']} requests, "
        f"goodput {m['goodput_rps']:.3f} req/s, SLA {m['sla_attainment']:.2f}, "
        f"dropped {m['drop_rate']:.2f}"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--rho", type=float, default=0.5)
    ap.add_argument("--policy", default="sed_global")
    a = ap.parse_args()
    from marl_lb.config import ROOT

    ok, msg = check(
        httpx.Client(base_url=a.api, timeout=120),
        a.seconds,
        a.rho,
        a.policy,
        ROOT / "results" / "live",
    )
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
