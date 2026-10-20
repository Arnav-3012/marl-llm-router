"""Do the learned agents depend on each observation feature? (ADR-032, test 1) Tier B.

uv run python -m scripts.shuffle_features [--agents-exp main_v2] [--seeds 0-4] [--workers 4]
    [--smoke]

For every seed and load, the held-out stream is played once with the agents unchanged and once per
feature with that feature replaced, at every decision, by a value drawn at random from the values
the feature took in the unchanged run. The goodput difference (shuffled minus unchanged) is
averaged over seeds with a 95% interval. A feature counts as "used" when the loss is larger than
the interval and larger than 0.01 req/s at some load (the rule is fixed in ADR-032). Shuffling
creates combinations the agent never saw, so a drop shows dependence, not that the feature is used
well. Writes results/shuffle/<agents-exp>.json (results/shuffle_smoke with --smoke).
Prints DONE shuffle.
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
from marl_lb.eval.evaluate import World, run_episode
from marl_lb.eval.experiments import stream_for
from marl_lb.eval.stats import mean_ci
from marl_lb.train.loop import greedy_actions
from scripts.analyse_behaviour import record_run
from scripts.evaluate import parse_seeds
from scripts.evaluate_paired import load_agents

FEATURES = ["own_wait", "own_kv", "prompt_size", "slack", "hops", "neighbour_wait", "prefix_hit"]
MIN_LOSS_RPS = 0.01  # a loss below this is not called a dependence (ADR-032)
_CTX: dict = {}


def run_job(job: tuple) -> dict:
    exp, seed, rho = job
    world = _CTX.setdefault("world", World())
    lam = load_lambda_sat()
    agents, cfg = load_agents(exp, seed, len(world.params.layout))
    rate = rho_to_rate(rho, lam)
    rows, base = record_run(world, agents, cfg, rate, seed)
    pool = rows[:, :7]  # the values each feature took in the unchanged run
    out = {"seed": seed, "rho": rho, "base": base["goodput_rps"], "shuffled": {}}
    for j, name in enumerate(FEATURES):
        rng = np.random.default_rng(seed * 100 + j)
        cluster = world.cluster(
            k=cfg["k"],
            lambda_cost=cfg["lambda_cost"],
            beta_coop=cfg["beta_coop"],
            reject_enabled=cfg.get("reject_enabled", False),
        )
        inner = greedy_actions(agents, None)

        def act(obs, infos, j=j, rng=rng, inner=inner):
            seen = {}
            for agent, v in obs.items():
                if infos[agent]["decide"]:
                    v = v.copy()
                    v[j] = rng.choice(pool[:, j])
                seen[agent] = v
            return inner(seen, infos)

        m, _ = run_episode(cluster, stream_for(world, rate, seed, "heldout"), seed, act)
        out["shuffled"][name] = m["goodput_rps"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents-exp", default="main_v2", dest="exp")
    ap.add_argument("--seeds", default="0-4")
    ap.add_argument("--rhos", default="0.5,0.8,0.95")
    ap.add_argument("--workers", type=int, default=max((os.cpu_count() or 2) - 1, 1))
    ap.add_argument("--smoke", action="store_true", help="1 seed, 1 load, results/shuffle_smoke")
    a = ap.parse_args()
    seeds, rhos = parse_seeds(a.seeds), [float(x) for x in a.rhos.split(",")]
    if a.smoke:
        seeds, rhos = [0], [0.5]
    jobs = [(a.exp, s, r) for r in rhos for s in seeds]
    with ProcessPoolExecutor(a.workers) as pool:
        results = list(pool.map(run_job, jobs))
    doc = {
        "agents_experiment": a.exp, "split": "heldout", "seeds": seeds, "features": FEATURES,
        "rule": f"used = loss > the 95% interval and > {MIN_LOSS_RPS} req/s at some load",
        "created": datetime.now().isoformat(timespec="seconds"), "rhos": {},
    }  # fmt: skip
    for rho in rhos:
        mine = [r for r in results if r["rho"] == rho]
        entry = {"base_goodput": mean_ci([r["base"] for r in mine])[0], "features": {}}
        for name in FEATURES:
            diffs = [r["shuffled"][name] - r["base"] for r in mine]
            mean, ci = mean_ci(diffs)
            half = 0.0 if np.isnan(ci) else ci
            entry["features"][name] = {
                "mean_diff": mean, "ci": None if np.isnan(ci) else ci,
                "per_seed": diffs, "n": len(diffs),
                "loss_beyond_interval": bool(-mean > half),
                "used_at_this_load": bool(-mean > MIN_LOSS_RPS and -mean > half),
            }  # fmt: skip
        doc["rhos"][str(rho)] = entry
    doc["used"] = {
        n: any(doc["rhos"][str(r)]["features"][n]["used_at_this_load"] for r in rhos)
        for n in FEATURES
    }
    out = ROOT / "results" / ("shuffle_smoke" if a.smoke else "shuffle")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{a.exp}.json").write_text(json.dumps(doc, indent=2, default=float))
    print(f"{'feature':15s} " + " ".join(f"rho {r:<4} diff (req/s)" for r in rhos) + "   used")
    for n in FEATURES:
        cells = []
        for r in rhos:
            f = doc["rhos"][str(r)]["features"][n]
            cells.append(
                f"{f['mean_diff']:+.3f} ± {(f['ci'] if f['ci'] is not None else float('nan')):.3f}"
            )
        print(
            f"{n:15s} "
            + " | ".join(f"{c:>18s}" for c in cells)
            + f"   {'yes' if doc['used'][n] else 'no'}"
        )
    print(f"DONE shuffle {a.exp}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as e:  # noqa: BLE001
        print(f"FAILED shuffle_features: {e!r}", file=sys.stderr)
        raise
    sys.exit(code)
