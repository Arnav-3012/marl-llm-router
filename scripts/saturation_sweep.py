"""Find lambda_sat for the global-SED cluster on train traffic (ADR-011, M1.26 to M1.28). Tier B.

uv run python -m scripts.saturation_sweep [--workers N]

Resumable: every (setting, rate, seed) result is appended to results/saturation/points.csv and
skipped on
a re-run. Writes results/saturation/lambda_sat.json (per cache setting: lambda_sat, all points,
monotonicity,
SLA attainment at 0.1 x lambda_sat, max arrivals per agent per tick) and copies the config beside
it.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path

import numpy as np
import yaml

from marl_lb.config import ROOT
from marl_lb.eval.evaluate import World, run_episode
from marl_lb.eval.saturation import find_lambda_sat, point_criteria
from marl_lb.policies.heuristics import SEDGlobal
from marl_lb.sim.cluster import slice_stream

OUT = ROOT / "results" / "saturation"
FIELDS = [
    "setting",
    "rate",
    "seed",
    "window_s",
    "start_s",
    "n_arrived",
    "completion_ratio",
    "drop_rate",
    "backlog_ratio",
    "in_flight_at_end",
    "sla_attainment",
]
_WORLD: World | None = None


def _init():
    global _WORLD
    _WORLD = World()


def run_point(job):
    setting, rate, seed, window_s, start_s = job
    w = _WORLD
    cache_on = setting == "cache_on"
    cluster = w.cluster(
        mode="global",
        global_policy=SEDGlobal(),
        # fmt: skip
        prefix_cache_fraction=w.params.prefix_cache_fraction if cache_on else 0.0,
    )
    stream = slice_stream(w.stream(rate, seed, "train"), start_s, window_s)
    run_episode(cluster, stream, seed)
    return {
        "setting": setting,
        "rate": rate,
        "seed": seed,
        "window_s": window_s,
        "start_s": start_s,
        **point_criteria(cluster, window_s),
    }


def load_points(window_s: float, start_s: float) -> dict:
    """Saved points for THIS window (length and start) only; older rows lack the columns."""
    path = OUT / "points.csv"
    if not path.exists():
        return {}
    with open(path) as f:
        return {
            (r["setting"], round(float(r["rate"]), 6), int(r["seed"])): {
                k: float(v) if k not in ("setting",) else v for k, v in r.items()
            }
            for r in csv.DictReader(f)
            if float(r.get("window_s") or -1) == float(window_s)
            and float(r.get("start_s") or -1) == float(start_s)
        }


def append_points(rows: list) -> None:
    path = OUT / "points.csv"
    if path.exists() and path.read_text().split("\n", 1)[0] != ",".join(FIELDS):
        # An older run wrote a different column set: keep it aside rather than mix the two layouts.
        path.rename(OUT / f"points.stale-{datetime.now():%Y%m%d-%H%M%S}.csv")
    new = not path.exists()
    with open(OUT / "points.csv", "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerows([{k: r[k] for k in FIELDS} for r in rows])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=max((os.cpu_count() or 2) - 1, 1))
    ap.add_argument("--config", type=Path, default=ROOT / "configs" / "saturation.yaml")
    ap.add_argument(
        "--smoke", action="store_true", help="tiny grid and window to check the plumbing"
    )
    args = ap.parse_args()
    global OUT
    if args.smoke:  # never mix tiny-window smoke points into the resumable real results
        OUT = ROOT / "results" / "saturation_smoke"
    cfg = yaml.safe_load(args.config.read_text())
    if args.smoke:
        cfg.update(
            window_s=20,
            seeds=[0],
            grid_rps={"min": 2.0, "max": 16.0, "n": 3},
            refine_steps=1,
            settings=["cache_on"],
        )
    OUT.mkdir(parents=True, exist_ok=True)
    world = World()
    shutil.copy(args.config, OUT / f"config_{datetime.now():%Y%m%d-%H%M%S}.yaml")
    g = cfg["grid_rps"]
    grid = [round(float(x), 6) for x in np.geomspace(g["min"], g["max"], g["n"])]
    pool = ProcessPoolExecutor(args.workers, initializer=_init)
    window, start = cfg["window_s"], cfg["start_s"]
    done = load_points(window, start)

    def ensure(setting: str, rates: list) -> None:
        jobs = [
            (setting, r, s, window, start)
            for r in rates
            for s in cfg["seeds"]
            if (setting, round(r, 6), s) not in done
        ]
        if jobs:
            rows = list(pool.map(run_point, jobs))
            append_points(rows)
            for r in rows:
                done[(r["setting"], round(r["rate"], 6), r["seed"])] = r
            print(f"{setting}: ran {len(jobs)} points", flush=True)

    result = {
        "window_s": window,
        "seeds": cfg["seeds"],
        "thresholds": cfg["thresholds"],
        "settings": {},
    }
    for setting in cfg["settings"]:
        ensure(setting, grid)  # whole coarse grid in parallel

        def evaluate(rate, setting=setting):
            ensure(setting, [rate])
            rows = [done[(setting, round(rate, 6), s)] for s in cfg["seeds"]]
            # fmt: skip
            return {
                k: float(np.mean([r[k] for r in rows]))
                for k in (
                    "completion_ratio",
                    "drop_rate",
                    "backlog_ratio",
                    "in_flight_at_end",
                    "sla_attainment",
                )
            }

        found = find_lambda_sat(evaluate, grid, cfg["refine_steps"], cfg["thresholds"])
        lam = found["lambda_sat_rps"]
        entry = {**found}
        if lam is not None:
            ref = lam * cfg["reference_fraction"]
            entry["sla_attainment_at_reference"] = {"rate_rps": ref, **evaluate(ref)}
            entry["max_arrivals_per_agent_per_tick"] = (
                lam * world.params.dt / len(world.params.layout)
            )
        result["settings"][setting] = entry
        print(f"{setting}: lambda_sat = {lam}", flush=True)
    (OUT / "lambda_sat.json").write_text(json.dumps(result, indent=2, default=float))
    # the flat file data/load.py reads
    flat = {s: {"lambda_sat_rps": e["lambda_sat_rps"]} for s, e in result["settings"].items()}
    (OUT / "lambda_sat_flat.json").write_text(json.dumps(flat, indent=2))
    pool.shutdown()
    print(f"DONE saturation_sweep {datetime.now().isoformat(timespec='seconds')}", flush=True)
    return 0


if __name__ == "__main__":
    t0 = time.time()
    try:
        code = main()
    except Exception as e:  # noqa: BLE001
        print(f"FAILED saturation_sweep: {e!r}", file=sys.stderr)
        raise
    sys.exit(code)
