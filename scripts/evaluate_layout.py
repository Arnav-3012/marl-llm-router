"""Layout test (ADR-035): a cluster with one fast and three slow servers. Tier B.

MARL_LAYOUT=fast_expensive,slow_cheap,slow_cheap,slow_cheap MARL_SAT_DIR=saturation_l13 \
  uv run python -m scripts.evaluate_layout --agents-exp l13_agents --tag l13

1. Tunes tau of the rewritten hand rule (RouteToFastShedTau) on TRAIN windows (start 1800 s, 6000 s,
   seeds 0-2) from the grid below by the mean goodput over rho 0.8 and 0.95; ties go to the smaller.
2. Held-out evaluation, 5 seeds, rho 0.5, 0.8, 0.95 of THIS layout's lambda_sat: the agents trained
   for this layout (same recipe as e8_scratch, no code changes), the old rules unchanged, the
   rewritten rule with the tuned tau, SED global, SED local, Random.
Writes results/layout/<tag>.json; prints goodput, drop rate, paired differences and the ADR verdict.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime

import numpy as np

from marl_lb.config import ROOT
from marl_lb.data.load import load_lambda_sat, rho_to_rate
from marl_lb.eval.evaluate import World, local_actions, run_episode
from marl_lb.eval.experiments import stream_for, suite
from marl_lb.eval.stats import mean_ci
from marl_lb.policies import heuristics as H
from marl_lb.train.loop import greedy_actions
from scripts.evaluate import parse_seeds
from scripts.evaluate_paired import load_agents

TAU_GRID = [0.0, 0.02, 0.05, 0.1, 0.2, 0.4, 0.8]  # own expected wait / 10 s; fixed in ADR-035
TUNE_RHOS, TUNE_SEEDS, TUNE_WINDOW = [0.8, 0.95], [0, 1, 2], 6000.0
RHOS = [0.5, 0.8, 0.95]
POLICIES = [
    "agents",
    "route_to_fast_shed_tau",
    "route_to_fast_shed",
    "route_to_fast",
    "sed_global",
    "sed_local_full",
    "random",
]
_CTX: dict = {}


def run_job(job):
    kind, exp, policy, rho, seed, tau = job
    world = _CTX.setdefault("world", World())
    rate = rho_to_rate(rho, load_lambda_sat())
    split, window = ("train", TUNE_WINDOW) if kind == "tune" else ("heldout", None)
    stream = stream_for(world, rate, seed, split, window)
    if policy == "agents":
        agents, cfg = load_agents(exp, seed, len(world.params.layout))
        cluster = world.cluster(
            k=cfg["k"],
            lambda_cost=cfg["lambda_cost"],
            beta_coop=cfg["beta_coop"],
            reject_enabled=cfg.get("reject_enabled", False),
        )
        m, _ = run_episode(cluster, stream, seed, greedy_actions(agents, None))
    elif policy == "route_to_fast_shed_tau":
        cluster = world.cluster(k="full", reject_enabled=True)
        m, _ = run_episode(
            cluster, stream, seed, local_actions(H.RouteToFastShedTau(world.params.layout, tau))
        )
    else:
        mode, kw, factory = suite(world, 1.0)[policy]
        pol = factory(seed)
        if mode == "global":
            m, _ = run_episode(world.cluster(mode="global", global_policy=pol, **kw), stream, seed)
        else:
            m, _ = run_episode(world.cluster(**kw), stream, seed, local_actions(pol))
    return {
        "kind": kind,
        "policy": policy,
        "rho": rho,
        "seed": seed,
        "tau": tau,
        "goodput": m["goodput_rps"],
        "drop": m["drop_rate"],
        "arrival": m["n_arrived"] / m["arrival_window_s"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents-exp", required=True, dest="exp")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--seeds", default="0-4")
    ap.add_argument("--workers", type=int, default=max((os.cpu_count() or 2) - 1, 1))
    ap.add_argument("--smoke", action="store_true", help="1 seed, 1 load, 2 taus, small window")
    a = ap.parse_args()
    seeds, rhos, grid = parse_seeds(a.seeds), RHOS, TAU_GRID
    global TUNE_WINDOW, TUNE_SEEDS, TUNE_RHOS
    if a.smoke:
        seeds, rhos, grid, TUNE_WINDOW, TUNE_SEEDS, TUNE_RHOS = (
            [0],
            [0.5],
            [0.0, 0.1],
            300.0,
            [0],
            [0.8],
        )
    layout = World().params.layout
    with ProcessPoolExecutor(a.workers) as pool:
        tune = list(
            pool.map(
                run_job,
                [
                    ("tune", a.exp, "route_to_fast_shed_tau", r, s, t)
                    for t in grid
                    for r in TUNE_RHOS
                    for s in TUNE_SEEDS
                ],
            )
        )
        score = {t: float(np.mean([x["goodput"] for x in tune if x["tau"] == t])) for t in grid}
        tau = max(grid, key=lambda t: (score[t], -t))
        print(
            "tau tuning on train windows (mean goodput):",
            {t: round(v, 3) for t, v in score.items()},
            "-> tau",
            tau,
        )
        res = list(
            pool.map(
                run_job,
                [("final", a.exp, p, r, s, tau) for p in POLICIES for r in rhos for s in seeds],
            )
        )

    def vals(p, r, key="goodput"):
        by = {x["seed"]: x[key] for x in res if x["policy"] == p and x["rho"] == r}
        return np.array([by[s] for s in seeds])

    doc = {
        "agents_experiment": a.exp,
        "layout": layout,
        "seeds": seeds,
        "tau": tau,
        "tau_scores": score,
        "created": datetime.now().isoformat(timespec="seconds"),
        "rhos": {},
    }
    for r in rhos:
        e = {
            "arrival_rate": float(np.mean([x["arrival"] for x in res if x["rho"] == r])),
            "policies": {},
            "agents_minus": {},
        }
        for p in POLICIES:
            e["policies"][p] = {
                "goodput": mean_ci(vals(p, r)),
                "drop_rate": float(vals(p, r, "drop").mean()),
            }
        for ref in POLICIES[1:]:
            m, h = mean_ci(vals("agents", r) - vals(ref, r))
            h = 0.0 if np.isnan(h) else h
            e["agents_minus"][ref] = {
                "mean": m,
                "ci": h,
                "beats": bool(m - h > 0 and m > 0.01),
                "loses": bool(m + h < 0 and m < -0.01),
            }
        doc["rhos"][str(r)] = e
    out = ROOT / "results" / ("layout_smoke" if a.smoke else "layout")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{a.tag}.json").write_text(json.dumps(doc, indent=2, default=float))
    print("layout", layout, "tau", tau)
    for r in rhos:
        e = doc["rhos"][str(r)]
        print(
            f"rho {r} (arrival {e['arrival_rate']:.3f} req/s): "
            + ", ".join(
                f"{p} {v['goodput'][0]:.3f} (drop {v['drop_rate']:.2f})"
                for p, v in e["policies"].items()
            )
        )
        for ref, d in e["agents_minus"].items():
            verdict = "BEATS" if d["beats"] else "LOSES" if d["loses"] else "tie"
            print(f"   agents minus {ref:24s} {d['mean']:+.3f} ± {d['ci']:.3f}  {verdict}")
    print(f"DONE layout {a.tag}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as e:  # noqa: BLE001
        print(f"FAILED evaluate_layout: {e!r}", file=sys.stderr)
        raise
    sys.exit(code)
