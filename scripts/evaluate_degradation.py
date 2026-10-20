"""Server degradation test (ADR-032, test 3). Tier B.

uv run python -m scripts.evaluate_degradation [--agents-exp main_v2] [--seeds 0-4] [--workers 6]
    [--smoke]

Halfway through the arrival window one fast server (agent 0's) is slowed by a factor of 3; the
agents were trained without this. Each policy is played on the same held-out slice with and without
the slowdown, at the loads fixed in ADR-032. The paired goodput difference (agents minus a
reference, under degradation) decides "adapts better" by the ADR's rule: the interval excludes 0 on
the positive side and the mean difference is above 0.01 req/s at either load. Writes
results/degradation/<agents-exp>.json (results/degradation_smoke with --smoke); prints DONE.
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
from marl_lb.eval.experiments import suite
from marl_lb.eval.stats import mean_ci
from marl_lb.train.loop import greedy_actions
from scripts.evaluate import parse_seeds
from scripts.evaluate_paired import load_agents

DEGRADE = {"server": 0, "factor": 3.0, "at_fraction": 0.5}  # fixed in ADR-032, not tuned
LEARNED = "ddqn_agents"
REFERENCES = ["route_to_fast", "route_to_fast_shed", "sed_global", "sed_local_full", "random"]
MIN_GAIN_RPS = 0.01
_CTX: dict = {}


def run_job(job: tuple) -> dict:
    exp, policy, rho, seed, degraded = job
    world = _CTX.setdefault("world", World())
    rate = rho_to_rate(rho, load_lambda_sat())
    stream = world.stream(rate, seed, "heldout")
    extra = {"degrade": DEGRADE} if degraded else {}
    if policy == LEARNED:
        agents, cfg = load_agents(exp, seed, len(world.params.layout))
        cluster = world.cluster(
            k=cfg["k"],
            lambda_cost=cfg["lambda_cost"],
            beta_coop=cfg["beta_coop"],
            reject_enabled=cfg.get("reject_enabled", False),
            **extra,
        )
        metrics, _ = run_episode(cluster, stream, seed, greedy_actions(agents, None))
    else:
        mode, kw, factory = suite(world, 1.0)[policy]
        pol = factory(seed)
        if mode == "global":
            cluster = world.cluster(mode="global", global_policy=pol, **kw, **extra)
            metrics, _ = run_episode(cluster, stream, seed)
        else:
            cluster = world.cluster(**kw, **extra)
            metrics, _ = run_episode(cluster, stream, seed, local_actions(pol))
    return {"policy": policy, "rho": rho, "seed": seed, "degraded": degraded,
            "goodput": metrics["goodput_rps"], "drop_rate": metrics["drop_rate"],
            "sla": metrics["sla_attainment"], "ttft_p95": metrics["ttft_p95"]}  # fmt: skip


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents-exp", default="main_v2", dest="exp")
    ap.add_argument("--seeds", default="0-4")
    ap.add_argument("--rhos", default="0.5,0.8")
    ap.add_argument("--workers", type=int, default=max((os.cpu_count() or 2) - 1, 1))
    ap.add_argument(
        "--smoke", action="store_true", help="1 seed, 1 load, results/degradation_smoke"
    )
    a = ap.parse_args()
    seeds, rhos = parse_seeds(a.seeds), [float(x) for x in a.rhos.split(",")]
    if a.smoke:
        seeds, rhos = [0], [0.5]
    policies = [LEARNED, *REFERENCES]
    jobs = [
        (a.exp, p, r, s, d) for p in policies for r in rhos for s in seeds for d in (False, True)
    ]
    with ProcessPoolExecutor(a.workers) as pool:
        res = list(pool.map(run_job, jobs))

    def goodputs(policy, rho, degraded):
        by_seed = {
            r["seed"]: r["goodput"]
            for r in res
            if (r["policy"], r["rho"], r["degraded"]) == (policy, rho, degraded)
        }
        return np.array([by_seed[s] for s in seeds])

    doc = {"agents_experiment": a.exp, "split": "heldout", "seeds": seeds, "degrade": DEGRADE,
           "created": datetime.now().isoformat(timespec="seconds"), "rhos": {}}  # fmt: skip
    for rho in rhos:
        entry = {"policies": {}, "agents_minus": {}}
        for p in policies:
            ok, bad = goodputs(p, rho, False), goodputs(p, rho, True)
            drop = [
                r["drop_rate"]
                for r in res
                if (r["policy"], r["rho"], r["degraded"]) == (p, rho, True)
            ]
            entry["policies"][p] = {
                "goodput_normal": mean_ci(ok), "goodput_degraded": mean_ci(bad),
                "loss": mean_ci(ok - bad), "drop_rate_degraded": float(np.mean(drop)),
            }  # fmt: skip
        mine = goodputs(LEARNED, rho, True)
        for ref in REFERENCES:
            diff = mine - goodputs(ref, rho, True)
            mean, ci = mean_ci(diff)
            half = 0.0 if np.isnan(ci) else ci
            entry["agents_minus"][ref] = {
                "mean": mean, "ci": None if np.isnan(ci) else ci, "per_seed": diff.tolist(),
                "beats": bool(mean - half > 0 and mean > MIN_GAIN_RPS),
                "loses": bool(mean + half < 0 and mean < -MIN_GAIN_RPS),
            }  # fmt: skip
        doc["rhos"][str(rho)] = entry
    doc["adapts_better_than_route_to_fast"] = any(
        doc["rhos"][str(r)]["agents_minus"]["route_to_fast"]["beats"] for r in rhos
    )
    out = ROOT / "results" / ("degradation_smoke" if a.smoke else "degradation")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{a.exp}.json").write_text(json.dumps(doc, indent=2, default=float))
    for rho in rhos:
        print(f"rho {rho}: goodput normal -> degraded (loss), drop rate when degraded")
        for p in policies:
            e = doc["rhos"][str(rho)]["policies"][p]
            print(f"  {p:16s} {e['goodput_normal'][0]:.3f} -> {e['goodput_degraded'][0]:.3f}"
                  f"  (loss {e['loss'][0]:+.3f})  drop {e['drop_rate_degraded']:.2f}")  # fmt: skip
        for ref, d in doc["rhos"][str(rho)]["agents_minus"].items():
            ci = d["ci"] if d["ci"] is not None else float("nan")
            verdict = "BEATS" if d["beats"] else "LOSES" if d["loses"] else "tie"
            print(f"  agents minus {ref:15s} {d['mean']:+.3f} ± {ci:.3f}  {verdict}")
    print(f"agents adapt better than route-to-fast: {doc['adapts_better_than_route_to_fast']}")
    print(f"DONE degradation {a.exp}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as e:  # noqa: BLE001
        print(f"FAILED evaluate_degradation: {e!r}", file=sys.stderr)
        raise
    sys.exit(code)
