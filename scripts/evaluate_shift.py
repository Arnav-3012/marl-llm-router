"""Shift test (ADR-033): saved agents, no retraining, on a load ramp and the code trace. Tier B.

uv run python -m scripts.evaluate_shift [--agents-exp e8_scratch] [--seeds 0-4] [--workers 6]

Writes results/shift/<agents-exp>.json and prints goodput, drop rate and paired differences with the
ADR-033 verdict.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime

import numpy as np
import yaml

from marl_lb.config import ROOT
from marl_lb.data.load import load_lambda_sat, rho_to_rate
from marl_lb.data.traces import load_azure_2023, sample_stream
from marl_lb.eval.evaluate import World, local_actions, run_episode
from marl_lb.eval.experiments import suite
from marl_lb.eval.stats import mean_ci
from marl_lb.train.loop import greedy_actions
from scripts.evaluate import parse_seeds
from scripts.evaluate_paired import load_agents

LEARNED = "agents"
REFS = ["route_to_fast_shed", "route_to_fast", "sed_global", "sed_local_full"]
CONDITIONS = ["ramp", "code_0.5", "code_0.8", "code_0.95"]
_CTX: dict = {}


def code_trace(world):
    if "code" not in _CTX:
        raw = yaml.safe_load((ROOT / "configs" / "data.yaml").read_text())
        raw_dir = ROOT / "data" / "raw"
        name = next(s["filename"] for s in raw["sources"] if s["name"] == "azure_code_2023")
        _CTX["code"] = load_azure_2023(raw_dir / name, drop_failures=True)
    return _CTX["code"]


def stream_for(world, cond: str, seed: int):
    lam = load_lambda_sat()
    if cond == "ramp":  # thirds of the held-out window at rho 0.5, 1.0, 0.5
        parts = {r: world.stream(rho_to_rate(r, lam), seed, "heldout") for r in (0.5, 1.0)}
        end = parts[0.5][-1].arrival_s
        cut1, cut2 = end / 3, 2 * end / 3
        out = [s for s in parts[0.5] if s.arrival_s < cut1]
        out += [s for s in parts[1.0] if cut1 <= s.arrival_s < cut2]
        out += [s for s in parts[0.5] if s.arrival_s >= cut2]
        return sorted(out, key=lambda s: s.arrival_s)
    rho = float(cond.split("_")[1])
    return sample_stream(code_trace(world), rho_to_rate(rho, lam), seed, "heldout",
                         train_fraction=world.train_fraction)  # fmt: skip


def run_job(job):
    exp, policy, cond, seed = job
    world = _CTX.setdefault("world", World())
    stream = stream_for(world, cond, seed)
    if policy == LEARNED:
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
    return {"policy": policy, "cond": cond, "seed": seed, "goodput": m["goodput_rps"],
            "drop": m["drop_rate"], "sla": m["sla_attainment"]}  # fmt: skip


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents-exp", default="e8_scratch", dest="exp")
    ap.add_argument("--seeds", default="0-4")
    ap.add_argument("--workers", type=int, default=max((os.cpu_count() or 2) - 1, 1))
    a = ap.parse_args()
    seeds = parse_seeds(a.seeds)
    pols = [LEARNED, *REFS]
    jobs = [(a.exp, p, c, s) for p in pols for c in CONDITIONS for s in seeds]
    with ProcessPoolExecutor(a.workers) as pool:
        res = list(pool.map(run_job, jobs))

    def vals(p, c, key="goodput"):
        by = {r["seed"]: r[key] for r in res if r["policy"] == p and r["cond"] == c}
        return np.array([by[s] for s in seeds])

    created = datetime.now().isoformat(timespec="seconds")
    doc = {"agents_experiment": a.exp, "seeds": seeds, "created": created, "conditions": {}}
    for c in CONDITIONS:
        pol_stats = {
            p: {"goodput": mean_ci(vals(p, c)), "drop_rate": float(vals(p, c, "drop").mean())}
            for p in pols
        }
        e = {"policies": pol_stats, "agents_minus": {}}
        for ref in REFS:
            m, h = mean_ci(vals(LEARNED, c) - vals(ref, c))
            h = 0.0 if np.isnan(h) else h
            e["agents_minus"][ref] = {"mean": m, "ci": h, "beats": bool(m - h > 0 and m > 0.01),
                                      "loses": bool(m + h < 0 and m < -0.01)}  # fmt: skip
        e["holds_up"] = not any(
            e["agents_minus"][r]["loses"]
            for r in ("route_to_fast_shed", "route_to_fast", "sed_global")
        )
        doc["conditions"][c] = e
    out = ROOT / "results" / "shift"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{a.exp}.json").write_text(json.dumps(doc, indent=2, default=float))
    for c, e in doc["conditions"].items():
        print(
            f"{c}: "
            + ", ".join(
                f"{p} {v['goodput'][0]:.3f} (drop {v['drop_rate']:.2f})"
                for p, v in e["policies"].items()
            )
        )
        for ref, d in e["agents_minus"].items():
            v = "BEATS" if d["beats"] else "LOSES" if d["loses"] else "tie"
            print(f"   agents minus {ref:18s} {d['mean']:+.3f} ± {d['ci']:.3f}  {v}")
        print(f"   holds up without retraining: {e['holds_up']}")
    print(f"DONE shift {a.exp}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as e:  # noqa: BLE001
        print(f"FAILED evaluate_shift: {e!r}", file=sys.stderr)
        raise
    sys.exit(code)
