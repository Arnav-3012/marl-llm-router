"""Evaluate all baseline policies on held-out traffic at several loads, several seeds (M1.29). Tier
B.

uv run python -m scripts.evaluate [--workers N] [--seeds 0-4] [--rhos 0.5,0.8,0.95]

Needs results/saturation/lambda_sat_flat.json (scripts/saturation_sweep.py). One result folder per
seed:
results/baselines/<timestamp>_seed<k>/{metrics.json, config.yaml, events_<policy>_rho<rho>.jsonl
(seed 0 only: replay logs)}.
Resumable: a seed whose folder holds DONE is skipped. Prints "DONE evaluate <timestamp>".
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime

import yaml

from marl_lb.config import ROOT
from marl_lb.data.load import load_lambda_sat, rho_to_rate
from marl_lb.eval.evaluate import World
from marl_lb.eval.experiments import eval_baseline, suite
from marl_lb.utils.io import make_run_dir

EXP = "baselines"


def parse_seeds(text: str) -> list:
    if "-" in text:
        a, b = text.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in text.split(",")]


def finished(exp: str, seed: int) -> bool:
    return any((d / "DONE").exists() for d in (ROOT / "results" / exp).glob(f"*_seed{seed}"))


def run_seed(job) -> str:
    seed, rhos, cfg, setting, exp = job  # exp is passed in: spawned workers do not share globals
    world = World()
    lam = load_lambda_sat(key=setting)
    run = make_run_dir(exp, seed, {**cfg, "seed": seed, "lambda_sat_rps": lam, "rhos": rhos})
    out = {}
    for name in suite(world, cfg["cache_aware_w"]):
        for rho in rhos:
            ev = run / f"events_{name}_rho{rho}.jsonl" if seed == 0 else None
            out[f"{name}@{rho}"] = eval_baseline(
                world, name, cfg["cache_aware_w"], rho_to_rate(rho, lam), seed, ev
            )
    (run / "metrics.json").write_text(json.dumps(out, indent=2, default=float))
    (run / "DONE").write_text(datetime.now().isoformat())
    return str(run)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=max((os.cpu_count() or 2) - 1, 1))
    ap.add_argument("--seeds", default="0-4")
    ap.add_argument("--rhos", default="0.5,0.8,0.95")
    ap.add_argument("--setting", default="cache_on")
    ap.add_argument("--smoke", action="store_true", help="1 seed, 1 load (fast plumbing check)")
    ap.add_argument("--exp", default=EXP, help="results folder name, e.g. baselines_v2 (ADR-027)")
    a = ap.parse_args()
    cfg = yaml.safe_load((ROOT / "configs" / "experiments" / "baselines.yaml").read_text()) or {}
    cfg.setdefault("cache_aware_w", 1.0)
    seeds, rhos = parse_seeds(a.seeds), [float(x) for x in a.rhos.split(",")]
    if a.smoke:
        seeds, rhos = [0], [0.5]
    exp = a.exp + ("_smoke" if a.smoke else "")  # smoke runs never touch real results/baselines
    todo = [(s, rhos, cfg, a.setting, exp) for s in seeds if not finished(exp, s)]
    print(f"seeds to run: {[j[0] for j in todo]} (skipping finished)", flush=True)
    with ProcessPoolExecutor(a.workers) as pool:
        for path in pool.map(run_seed, todo):
            print("wrote", path, flush=True)
    print(f"DONE evaluate {datetime.now().isoformat(timespec='seconds')}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as e:  # noqa: BLE001
        print(f"FAILED evaluate: {e!r}", file=sys.stderr)
        raise
    sys.exit(code)
