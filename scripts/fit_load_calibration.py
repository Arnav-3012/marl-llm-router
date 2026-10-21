"""Fit the simulator's load terms to real runs under load (ADR-037, step 2). Tier B.

uv run python -m scripts.fit_load_calibration --profile results/live_profile/<ts> [--write]

For every real run (results/live/<run_id>/) it rebuilds the same slice (held-out, same rate, seed
and window) and replays it in the simulator with the same policy, for each point of a parameter
grid over the ADR-037 terms (ctx_decode per class, g_prefill, g_decode; profiling/calibration.json
is the base, its fitted ADR-015 values are kept). The grid point with the smallest loss on the FIT
runs wins; it is then checked on the VALIDATION runs against the pass bar fixed in ADR-037 (SLA
attainment within 0.10, median TTFT within a factor of 1.5, on every validation run).

Loss per run: (SLA_sim - SLA_real)^2 + 0.25 log(TTFT50_sim / TTFT50_real)^2
              + 0.25 log(TPOT50_sim / TPOT50_real)^2 (TPOT only where the real run logged it).
--write saves profiling/calibration_load.json (base calibration + fitted terms + provenance) and
results/calibration_load/<ts>/fit.json; the simulator uses it with MARL_CALIBRATION.
"""

from __future__ import annotations

import argparse
import copy
import itertools
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime

import numpy as np
import yaml

from marl_lb.config import ROOT
from marl_lb.eval.evaluate import World, local_actions, run_episode
from marl_lb.eval.experiments import suite
from marl_lb.router.runs import make_slice

LIVE = ROOT / "results" / "live"
# fixed in ADR-037: fit on 0.10 and 0.30 req/s, validate on the rest
FIT_RATES = {0.10, 0.30}
EARLIER_VALIDATION = [  # first real runs (sed_global, 40 s, no ignore_eos), validation only
    "20261021-090154_001_sed_global_seed0",
    "20261021-090339_003_sed_global_seed0",
]
GRID = {  # third form (ADR-037 amendment 2): load terms split into same-class and other-class
    "ctx_fast": [0.0, 1e-6, 2.5e-6, 5e-6],
    "ctx_slow": [0.0, 1e-5, 2e-5, 4e-5],
    "g_same_dec": [0.0, 0.1, 0.2, 0.4, 0.8],
    "g_same_pre": [0.0, 0.2, 0.4],
    "g_diff": [0.0, 0.1, 0.2],
}
SLA_TOL, TTFT_FACTOR = 0.10, 1.5
_W: dict = {}


def real_metrics(run_id: str) -> dict:
    d = LIVE / run_id
    m = json.loads((d / "metrics.json").read_text())
    cfg = yaml.safe_load((d / "config.yaml").read_text())
    ev = [json.loads(x) for x in (d / "events.jsonl").read_text().splitlines()]
    tpot = [
        (e["t"] - e["t_first"]) / (e["n_tokens"] - 1)
        for e in ev
        if e["e"] == "resolve" and e.get("t_first") is not None and (e.get("n_tokens") or 0) > 1
    ]
    return {
        "run_id": run_id,
        "policy": cfg["policy"],
        "rate": float(cfg["rate_rps"]),
        "seed": int(cfg.get("seed", 0)),
        "seconds": float(cfg["seconds"]),
        "sla": m["sla_attainment"],
        "ttft50": m["ttft_p50"],
        "tpot50": float(np.median(tpot)) if tpot else None,
    }


def calib_with(base: dict, p: dict) -> dict:
    c = copy.deepcopy(base)
    for name, cls in c["classes"].items():
        cls["ctx_decode"] = p["ctx_fast"] if name.startswith("fast") else p["ctx_slow"]
        cls["g_same_decode"], cls["g_same_prefill"] = p["g_same_dec"], p["g_same_pre"]
        cls["g_diff_decode"] = cls["g_diff_prefill"] = p["g_diff"]
        cls.pop("g_decode", None), cls.pop("g_prefill", None)
    return c


def sim_metrics(world: World, calib: dict, run: dict) -> dict:
    world.calib = calib
    stream = make_slice(world, run["rate"], run["seed"], run["seconds"])
    mode, kw, factory = suite(world, 1.0)[run["policy"]]
    pol = factory(run["seed"])
    if mode == "global":
        c = world.cluster(mode="global", global_policy=pol, **kw)
        m, _ = run_episode(c, stream, run["seed"])
    else:
        c = world.cluster(**kw)
        m, _ = run_episode(c, stream, run["seed"], local_actions(pol))
    done = [r for r in c.run.requests if r.status == "done" and r.output_tokens > 1]
    tpot = [(r.t_done - r.t_first) / (r.output_tokens - 1) for r in done]
    return {
        "sla": m["sla_attainment"],
        "ttft50": m["ttft_p50"],
        "tpot50": float(np.median(tpot)) if tpot else None,
    }


def run_loss(sim: dict, real: dict) -> float:
    loss = (sim["sla"] - real["sla"]) ** 2
    loss += 0.25 * np.log(max(sim["ttft50"], 1e-3) / max(real["ttft50"], 1e-3)) ** 2
    if real["tpot50"] and sim["tpot50"]:
        loss += 0.25 * np.log(sim["tpot50"] / real["tpot50"]) ** 2
    return float(loss)


def eval_point(job):
    p, runs = job
    world = _W.setdefault("w", World())
    base = _W.setdefault("base", copy.deepcopy(world.calib))
    calib = calib_with(base, p)
    sims = [sim_metrics(world, calib, r) for r in runs]
    return p, sims, sum(run_loss(s, r) for s, r in zip(sims, runs, strict=True))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True, help="results/live_profile/<ts>")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--workers", type=int, default=max((os.cpu_count() or 2) - 1, 1))
    a = ap.parse_args()
    prof = json.loads((ROOT / a.profile / "runs.json").read_text())
    reals = [real_metrics(r["run_id"]) for r in prof["runs"]]
    fit = [r for r in reals if r["rate"] in FIT_RATES and r["policy"] != "random"]
    val = [r for r in reals if r not in fit] + [
        real_metrics(x) for x in EARLIER_VALIDATION if (LIVE / x).exists()
    ]
    pts = [dict(zip(GRID, v, strict=True)) for v in itertools.product(*GRID.values())]
    print(f"{len(pts)} grid points x {len(fit)} fit runs", flush=True)
    with ProcessPoolExecutor(a.workers) as pool:
        scored = list(pool.map(eval_point, [(p, fit) for p in pts], chunksize=4))
    scored.sort(key=lambda x: x[2])
    base_p = dict.fromkeys(GRID, 0.0)
    best_p = scored[0][0]
    with ProcessPoolExecutor(2) as pool:
        (_, val_best, _), (_, val_base, _) = pool.map(eval_point, [(best_p, val), (base_p, val)])
        (_, fit_base, _) = eval_point((base_p, fit))
    print("best:", best_p, "fit loss", round(scored[0][2], 4))

    def show(tag, runs, sims, base_sims):
        rows, ok_all = [], True
        for r, s, b in zip(runs, sims, base_sims, strict=True):
            ok = abs(s["sla"] - r["sla"]) <= SLA_TOL and (
                1 / TTFT_FACTOR <= max(s["ttft50"], 1e-3) / max(r["ttft50"], 1e-3) <= TTFT_FACTOR
            )
            ok_all &= ok
            rows.append({"real": r, "sim_new": s, "sim_old": b, "pass": ok})
            print(
                f"{tag} {r['policy']:14s} {r['rate']:.2f}  SLA real {r['sla']:.2f} "
                f"old {b['sla']:.2f} new {s['sla']:.2f} | TTFT50 real {r['ttft50']:.2f} "
                f"old {b['ttft50']:.2f} new {s['ttft50']:.2f} | TPOT50 real {r['tpot50']} "
                f"new {s['tpot50'] and round(s['tpot50'], 3)}  {'ok' if ok else 'MISS'}"
            )
        return rows, ok_all

    fit_rows, _ = show("FIT", fit, scored[0][1], fit_base)
    val_rows, passed = show("VAL", val, val_best, val_base)
    print("ADR-037 pass bar:", "PASSED" if passed else "FAILED", flush=True)
    doc = {
        "best": best_p,
        "grid": GRID,
        "fit_loss": scored[0][2],
        "top5": [[p, loss] for p, _, loss in scored[:5]],
        "fit": fit_rows,
        "validation": val_rows,
        "passed": passed,
        "profile": a.profile,
        "created": datetime.now().isoformat(timespec="seconds"),
    }
    out = ROOT / "results" / "calibration_load" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    (out / "fit.json").write_text(json.dumps(doc, indent=2, default=float))
    if a.write:
        world = World()
        calib = calib_with(world.calib, best_p)
        calib["source"]["load_fit"] = {"fit": str(out.relative_to(ROOT)), "adr": "ADR-037"}
        (ROOT / "profiling" / "calibration_load.json").write_text(json.dumps(calib, indent=2))
        print("wrote profiling/calibration_load.json")
    print(f"DONE fit_load_calibration {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
