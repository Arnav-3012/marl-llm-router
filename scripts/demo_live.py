"""Run one policy on a held-out slice and print its metrics (Sh.H3). Tier B.

uv run python -m scripts.demo_live --policy {random,sed,cache,dqn} --rho 0.8 --seed 0
    [--agents-exp e8_mix]

Uses the same functions as the evaluation behind the dashboard (eval/experiments.py): the same slice
for a given rho and seed, the same config, so the numbers printed here are the numbers the recorded
pages show for that slice. dqn uses the saved weights of --agents-exp (epsilon = 0).
"""

from __future__ import annotations

import argparse
import json
import sys

from marl_lb.data.load import load_lambda_sat, rho_to_rate
from marl_lb.eval.evaluate import World
from marl_lb.eval.experiments import eval_agents, eval_baseline
from marl_lb.train.loop import load_agents

NAMES = {"random": "random", "sed": "sed_global", "cache": "cache_aware_global"}


def run_policy(
    policy: str, rho: float, seed: int, agents_exp: str = "e8_mix", world: World | None = None
) -> dict:
    """Held-out metrics of `policy` at load `rho` and `seed`: the dashboard's numbers for it."""
    world = world or World()
    rate = rho_to_rate(rho, load_lambda_sat())
    if policy == "dqn":
        agents, cfg = load_agents(agents_exp, seed, len(world.params.layout))
        return eval_agents(
            world,
            agents,
            rate,
            seed,
            cfg["k"],
            None,
            "heldout",
            None,
            lambda_cost=cfg["lambda_cost"],
            beta_coop=cfg["beta_coop"],
            reject_enabled=cfg.get("reject_enabled", False),
        )
    return eval_baseline(world, NAMES.get(policy, policy), 1.0, rate, seed, None, "heldout", None)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True, help="random, sed, cache, dqn or any suite name")
    ap.add_argument("--rho", type=float, default=0.8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--agents-exp", default="e8_mix", dest="exp")
    a = ap.parse_args()
    m = run_policy(a.policy, a.rho, a.seed, a.exp)
    keys = ("goodput_rps", "sla_attainment", "drop_rate", "ttft_p95", "cost_per_request")
    print(json.dumps({k: m[k] for k in keys}, indent=2, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
