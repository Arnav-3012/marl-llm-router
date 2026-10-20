"""What do the learned agents do? (ADR-031) Tier B.

Records every decision (observation, mask, action) of the saved agents on the held-out stream and
tabulates action shares by server class, own wait and prompt size.

uv run python -m scripts.analyse_behaviour [--agents-exp main_v2] [--seeds 0-2]
    [--rhos 0.5,0.8,0.95]

Descriptive only (nothing is selected from it). Writes results/behaviour/<agents-exp>.json and
prints a table.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

import numpy as np

from marl_lb.config import ROOT
from marl_lb.data.load import load_lambda_sat, rho_to_rate
from marl_lb.eval.evaluate import World, run_episode
from marl_lb.eval.experiments import stream_for
from marl_lb.train.loop import greedy_actions
from scripts.evaluate import parse_seeds
from scripts.evaluate_paired import load_agents

ACTIONS = ["accept", "forward", "defer", "reject"]
WAIT_BINS = [0.0, 0.1, 0.3, 0.6, 1.01]  # own expected wait / wait_scale (10 s)
PROMPT_BINS = [0.0, 0.05, 0.1, 0.25, 1.01]  # prompt tokens / prompt normaliser


def bin_label(edges: list, i: int) -> str:
    return f"{edges[i]:.2f}-{min(edges[i + 1], 1.0):.2f}"


def record_run(world, agents, train_cfg, rate, seed):
    """Greedy held-out episode; returns an (n_decisions, 9) array: 7 obs features, agent, action."""
    cluster = world.cluster(
        k=train_cfg["k"],
        lambda_cost=train_cfg["lambda_cost"],
        beta_coop=train_cfg["beta_coop"],
        reject_enabled=train_cfg.get("reject_enabled", False),
    )
    inner, rows = greedy_actions(agents, None), []

    def act(obs, infos):
        actions = inner(obs, infos)
        for i, name in enumerate(cluster.agents):
            if infos[name]["decide"]:
                rows.append([*obs[name].tolist(), i, actions[name]])
        return actions

    metrics, _ = run_episode(cluster, stream_for(world, rate, seed, "heldout"), seed, act)
    return np.array(rows), metrics


def shares(rows: np.ndarray, n_actions: int) -> dict:
    if len(rows) == 0:
        return {"n": 0}
    acts = rows[:, 8].astype(int)
    out = {"n": int(len(rows))}
    for a in range(n_actions):
        out[ACTIONS[a]] = float((acts == a).mean())
    return out


def analyse(rows: np.ndarray, layout: list, n_actions: int) -> dict:
    out: dict = {}
    for cls in ("fast", "slow"):
        idx = [i for i, c in enumerate(layout) if c.startswith(cls)]
        mine = rows[np.isin(rows[:, 7].astype(int), idx)]
        entry = {"all": shares(mine, n_actions), "by_wait": {}, "by_prompt": {}}
        for b in range(len(WAIT_BINS) - 1):
            sel = mine[(mine[:, 0] >= WAIT_BINS[b]) & (mine[:, 0] < WAIT_BINS[b + 1])]
            entry["by_wait"][bin_label(WAIT_BINS, b)] = shares(sel, n_actions)
        for b in range(len(PROMPT_BINS) - 1):
            sel = mine[(mine[:, 2] >= PROMPT_BINS[b]) & (mine[:, 2] < PROMPT_BINS[b + 1])]
            entry["by_prompt"][bin_label(PROMPT_BINS, b)] = shares(sel, n_actions)
        out[cls] = entry
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents-exp", default="main_v2", dest="exp")
    ap.add_argument("--seeds", default="0-2")
    ap.add_argument("--rhos", default="0.5,0.8,0.95")
    a = ap.parse_args()
    world, lam = World(), load_lambda_sat()
    layout = world.params.layout
    result = {"agents_experiment": a.exp, "seeds": parse_seeds(a.seeds), "split": "heldout",
              "created": datetime.now().isoformat(timespec="seconds"), "rhos": {}}  # fmt: skip
    for rho in [float(x) for x in a.rhos.split(",")]:
        pooled = []
        for seed in result["seeds"]:
            agents, cfg = load_agents(a.exp, seed, len(layout))
            rows, _ = record_run(world, agents, cfg, rho_to_rate(rho, lam), seed)
            pooled.append(rows)
        n_actions = 4 if cfg.get("reject_enabled") else 3
        result["rhos"][str(rho)] = analyse(np.vstack(pooled), layout, n_actions)
        print(f"rho {rho}", flush=True)
        for cls in ("fast", "slow"):
            e = result["rhos"][str(rho)][cls]
            print(f"  {cls:4s} all {e['all']}")
            for key in ("by_wait", "by_prompt"):
                for label, s in e[key].items():
                    if s["n"]:
                        txt = ", ".join(f"{k} {s[k]:.2f}" for k in ACTIONS if k in s)
                        print(f"       {key[3:]:6s} {label}: n {s['n']}, {txt}")
    out = ROOT / "results" / "behaviour"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{a.exp}.json").write_text(json.dumps(result, indent=2))
    print(f"DONE behaviour {a.exp}")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as e:  # noqa: BLE001
        print(f"FAILED analyse_behaviour: {e!r}", file=sys.stderr)
        raise
    sys.exit(code)
