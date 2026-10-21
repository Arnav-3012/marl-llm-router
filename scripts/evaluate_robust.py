"""Robust-agent test (ADR-038): agents trained on random server slowdowns vs the final agents.

Tier B.

MARL_CALIBRATION=profiling/calibration_heavy.json uv run python -m scripts.evaluate_robust \
    --tag heavy --rhos 0.17,0.34,0.51 --mix-exp e8_mix --robust-exp e8_robust

Held-out traffic, 5 seeds, the same slice for every policy. Policies: the final agents (e8_mix),
the robust agents, the hand shed rule, route-to-fast, SED global and Random. Writes
results/robust/<tag>.json with mean +- 95% interval per policy and the paired differences
robust - e8_mix and robust - shed rule (win = interval above 0 and mean > 0.01 req/s, as ADR-032).
The world (calibration) comes from MARL_CALIBRATION (default: the first calibration).
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
from marl_lb.train.loop import greedy_actions
from scripts.evaluate import parse_seeds
from scripts.evaluate_paired import load_agents

_CTX: dict = {}
BASE = ["route_to_fast_shed", "route_to_fast", "sed_global", "random"]


def run_job(job):
    policy, exp, rho, seed = job
    world = _CTX.setdefault("world", World())
    rate = rho_to_rate(rho, load_lambda_sat())
    stream = stream_for(world, rate, seed, "heldout", None)
    if exp:
        agents, cfg = load_agents(exp, seed, len(world.params.layout))
        cluster = world.cluster(
            k=cfg["k"],
            lambda_cost=cfg["lambda_cost"],
            beta_coop=cfg["beta_coop"],
            reject_enabled=cfg.get("reject_enabled", False),
        )
        m, _ = run_episode(cluster, stream, seed, greedy_actions(agents, None))
    else:
        mode, kw, factory = suite(world, 1.0)[policy]
        pol = factory(seed)
        if mode == "global":
            m, _ = run_episode(world.cluster(mode="global", global_policy=pol, **kw), stream, seed)
        else:
            m, _ = run_episode(world.cluster(**kw), stream, seed, local_actions(pol))
    return {
        "policy": policy,
        "rho": rho,
        "seed": seed,
        "goodput": m["goodput_rps"],
        "drop": m["drop_rate"],
        "sla": m["sla_attainment"],
        "arrival": m["n_arrived"] / m["arrival_window_s"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--rhos", required=True)
    ap.add_argument("--mix-exp", default="e8_mix")
    ap.add_argument("--robust-exp", default="e8_robust")
    ap.add_argument("--seeds", default="0-4")
    ap.add_argument("--workers", type=int, default=max((os.cpu_count() or 2) - 1, 1))
    a = ap.parse_args()
    seeds, rhos = parse_seeds(a.seeds), [float(x) for x in a.rhos.split(",")]
    pols = [("agents_mix", a.mix_exp), ("agents_robust", a.robust_exp)] + [(p, None) for p in BASE]
    jobs = [(p, e, r, s) for p, e in pols for r in rhos for s in seeds]
    with ProcessPoolExecutor(a.workers) as pool:
        res = list(pool.map(run_job, jobs))

    def vals(p, r, key="goodput"):
        by = {x["seed"]: x[key] for x in res if x["policy"] == p and x["rho"] == r}
        return np.array([by[s] for s in seeds])

    doc = {
        "tag": a.tag,
        "calibration": os.environ.get("MARL_CALIBRATION", "profiling/calibration.json"),
        "mix_exp": a.mix_exp,
        "robust_exp": a.robust_exp,
        "seeds": seeds,
        "created": datetime.now().isoformat(timespec="seconds"),
        "rhos": {},
    }
    for r in rhos:
        e = {
            "arrival_rate": float(np.mean([x["arrival"] for x in res if x["rho"] == r])),
            "policies": {},
            "robust_minus": {},
        }
        for p, _ in pols:
            e["policies"][p] = {
                "goodput": mean_ci(vals(p, r)),
                "drop_rate": float(vals(p, r, "drop").mean()),
                "sla": float(vals(p, r, "sla").mean()),
            }
        for ref in ["agents_mix"] + BASE:
            m, h = mean_ci(vals("agents_robust", r) - vals(ref, r))
            h = 0.0 if np.isnan(h) else h
            e["robust_minus"][ref] = {
                "mean": m,
                "ci": h,
                "beats": bool(m - h > 0 and m > 0.01),
                "loses": bool(m + h < 0 and m < -0.01),
            }
        doc["rhos"][str(r)] = e
    out = ROOT / "results" / "robust"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{a.tag}.json").write_text(json.dumps(doc, indent=2, default=float))
    for r in rhos:
        e = doc["rhos"][str(r)]
        print(
            f"rho {r} (arrival {e['arrival_rate']:.3f} req/s): "
            + ", ".join(
                f"{p} {v['goodput'][0]:.3f} (drop {v['drop_rate']:.2f}, SLA {v['sla']:.2f})"
                for p, v in e["policies"].items()
            )
        )
        for ref, d in e["robust_minus"].items():
            verdict = "BEATS" if d["beats"] else "LOSES" if d["loses"] else "tie"
            print(f"   robust minus {ref:20s} {d['mean']:+.3f} ± {d['ci']:.3f}  {verdict}")
    print(f"DONE evaluate_robust {a.tag}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
