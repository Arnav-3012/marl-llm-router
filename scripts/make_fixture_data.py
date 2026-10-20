"""Write FIXTURE dashboard data (made-up numbers) to demo/site/public/fixture-data/ to check page
layouts. Tier B.

The site shows a red banner "FIXTURE DATA" when opened with ?data=fixture. Nothing here is a result
and nothing here
is ever written to public/data/. Run:  uv run python -m scripts.make_fixture_data
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np

from marl_lb.config import ROOT
from marl_lb.eval import paired
from scripts.export_dashboard_data import run_export

POLICIES = {
    "sed_global": 1.0,
    "sed_local_full": 0.93,
    "sed_local_k1": 0.9,
    "sed_local_k0": 0.78,
    "cache_aware_global": 0.97,
    # fmt: skip
    "cache_aware_local_full": 0.91,
    "jsq_global": 0.88,
    "po2_global": 0.84,
    "round_robin": 0.74,
    "random": 0.7,
}


def metrics(rng, goodput, cost, rho):
    jitter = lambda s: float(1 + rng.normal(0, s))  # noqa: E731
    return {
        "goodput_rps": goodput * jitter(0.03),
        "sla_attainment": min(0.99, 0.55 + 0.4 * goodput / 5) * jitter(0.01),
        "breach_rate": 0.2 * jitter(0.05),
        "drop_rate": max(0.0, 0.02 * (rho - 0.4)) * jitter(0.1),
        "ttft_p95": (1.5 + 3 * rho) * jitter(0.05),
        "tpot_p95": 0.04 * jitter(0.03),
        "e2e_p95": (4 + 6 * rho) * jitter(0.05),
        # fmt: skip
        "cost_per_request": cost * jitter(0.02),
        "cache_hit_rate": 0.2 * jitter(0.05),
        "jain_utilisation": 0.85 * jitter(0.02),
    }


def make_run(root, exp, seed, files):
    d = root / "results" / exp / f"fixture_seed{seed}"
    d.mkdir(parents=True)
    (d / "config.yaml").write_text("fixture: true\n")
    for name, content in files.items():
        (d / name).write_text(content if isinstance(content, str) else json.dumps(content))
    (d / "DONE").write_text("fixture")
    return d


def events(rng, n_ticks=900, dt=0.1, quality=0.8):
    ev, rid = [], 0
    for t in range(n_ticks):
        for _ in range(rng.poisson(0.5)):
            ev.append(
                {
                    "tick": t,
                    "t": round(t * dt, 4),
                    "e": "arrive",
                    "req": rid,
                    "entry": int(rng.integers(4)),
                    "p": int(rng.integers(100, 3000)),
                    "o": 100,
                }
            )
            ev.append(
                {
                    "tick": t,
                    "t": round(t * dt, 4),
                    "e": "act",
                    "agent": int(rng.integers(4)),
                    "req": rid,
                    "action": int(rng.choice([0, 0, 0, 1, 2])),
                }
            )
            rid += 1
        if t % 6 == 0 and rid:
            ev.append(
                {
                    "tick": t,
                    "t": round(t * dt, 4),
                    "e": "resolve",
                    "req": max(rid - 3, 0),
                    "status": "done",
                    "ok": bool(rng.random() < quality),
                    "server": int(rng.integers(4)),
                    "ttft": round(float(rng.gamma(2.0, (3.2 - 2.6 * quality) / 2)), 3),
                    "cost": round(float(rng.gamma(4.0, 4.5 - 2.0 * quality)), 3),
                }
            )
        ev.append(
            {
                "tick": t,
                "t": round(t * dt, 4),
                "e": "servers",
                "queue": [
                    int(max(0, 4 + 5 * np.sin(t / 60 + i) + rng.normal(0, 1))) for i in range(4)
                ],
                "active": [int(rng.integers(0, 5)) for _ in range(4)],
                "kv": [
                    round(float(min(1, 0.4 + 0.5 * abs(np.sin(t / 90 + i)))), 3) for i in range(4)
                ],
            }
        )
    return "\n".join(json.dumps(e) for e in ev)


# policy -> (goodput factor, event quality); the learned policy is deliberately close to SED
PAIRED = {
    "ddqn_agents": (1.06, 0.82),
    "sed_global": (1.0, 0.9),
    "sed_local_full": (0.93, 0.7),
    "cache_aware_global": (0.97, 0.78),
    "cache_aware_local_full": (0.91, 0.68),
    "random": (0.7, 0.55),
}


def write_paired_fixture(root: Path, rng) -> None:
    """results/paired/fixture/ in the layout scripts/evaluate_paired.py writes (made-up numbers)."""
    import yaml

    run = root / "results" / "paired" / "fixture"
    run.mkdir(parents=True)
    seeds = list(range(5))
    for rho in (0.5, 0.8, 0.95):
        for name, (g, quality) in PAIRED.items():
            results = [
                {
                    "seed": s,
                    "slice_id": f"fx{rho}-{s}",  # identical for every policy at this load and seed
                    "metrics": metrics(rng, 5 * g * (1.1 - 0.2 * rho), 3.0, rho),
                    "events": [json.loads(x) for x in events(rng, quality=quality).splitlines()]
                    if s == 0
                    else [],
                }
                for s in seeds
            ]
            paired.write_policy_file(
                run, name, rho, rho * 0.59, "heldout", "fixture0", results, 0, 60000
            )
    cfg = {
        "learned": {"name": "ddqn_agents", "experiment": "main"},
        "baselines": [p for p in PAIRED if p != "ddqn_agents"],
        "event_seed": 0,
        "split": "heldout",
    }
    (run / "config.yaml").write_text(yaml.safe_dump(cfg))
    (run / "DONE").write_text("fixture")


def main() -> None:
    rng = np.random.default_rng(0)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for seed in range(5):
            base = {
                f"{p}@{r}": metrics(rng, 5 * g * (1.1 - 0.2 * r), 3.0 if "global" in p else 3.4, r)
                for p, g in POLICIES.items()
                for r in (0.5, 0.8, 0.95)
            }
            files = {"metrics.json": base}
            if seed == 0:
                for p in ("random", "sed_local_full", "cache_aware_local_full", "sed_global"):
                    for r in (0.5, 0.8, 0.95):
                        files[f"events_{p}_rho{r}.jsonl"] = events(rng)
            make_run(root, "baselines", seed, files)
            for exp, g, cost in (
                ("main", 1.06, 3.1),
                ("k0", 0.88, 3.3),
                ("lambda0", 1.1, 4.4),
                ("lambda2", 0.95, 2.4),
            ):
                ev = {
                    str(r): metrics(rng, 5 * g * (1.1 - 0.2 * r), cost, r) for r in (0.5, 0.8, 0.95)
                }
                log = (
                    "episode,return_mean,goodput_rps,sla_attainment,td_loss,mean_q,epsilon,"
                    "act_accept,act_forward,act_defer\n"
                    + "\n".join(
                        f"{e},{-5 + 0.1 * e + rng.normal(0, 0.3):.3f},"
                        f"{2 + 0.03 * e + rng.normal(0, 0.1):.3f},{0.5 + 0.004 * e:.3f},"
                        f"{max(0.02, 1 / (1 + e / 5)):.3f},{0.1 * e / 10:.3f},"
                        f"{max(0.05, 1 - e / 60):.3f},50,10,5"
                        for e in range(100)
                    )
                )
                f2 = {"eval_metrics.json": ev, "train_log.csv": log}
                if exp == "main" and seed == 0:
                    for r in (0.5, 0.8, 0.95):
                        f2[f"events_rho{r}.jsonl"] = events(rng)
                make_run(root, exp, seed, f2)
        write_paired_fixture(root, rng)
        eda = ROOT / "results" / "eda" / "trace_summary.json"
        (root / "results" / "eda").mkdir(parents=True, exist_ok=True)
        if eda.exists():  # the EDA summary is a real result file; reuse it as is
            (root / "results" / "eda" / "trace_summary.json").write_text(eda.read_text())
        out = ROOT / "demo" / "site" / "public" / "fixture-data"
        run_export(root / "results", out, root=ROOT, cap=900)
        print(f"fixture data written to {out} (banner shown with ?data=fixture)")


if __name__ == "__main__":
    main()
