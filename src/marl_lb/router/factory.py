"""Build a live policy by name, with the simulator parameters it needs. Tier B.

Names are the evaluation suite's (random, sed_local_full, sed_global, cache_aware_local_full,
cache_aware_global, route_to_fast, route_to_fast_shed) plus ddqn_agents (saved weights, epsilon = 0,
Sh.L5). The parameters follow the policy exactly as in the simulator evaluation: its neighbour
radius, and the Reject action for the shed rule and for agents trained with it.
"""

from __future__ import annotations

from marl_lb.eval.experiments import suite
from marl_lb.router.policy_router import LearnedPolicy
from marl_lb.sim.cluster import SimParams
from marl_lb.train.loop import load_agents

POLICIES = [
    "random", "sed_local_full", "sed_global", "cache_aware_local_full", "cache_aware_global",
    "route_to_fast", "route_to_fast_shed", "ddqn_agents", "ddqn_robust",
]  # fmt: skip


def build_policy(
    name: str,
    world,
    agents_exp: str | None = None,
    seed: int = 0,
    robust_exp: str | None = None,
):
    """(policy object, SimParams) for `name` on `world`'s layout."""
    if name == "ddqn_robust":  # ADR-038: agents trained on random server slowdowns
        name, agents_exp = "ddqn_agents", robust_exp
    if name == "ddqn_agents":
        if not agents_exp:
            raise ValueError("ddqn_agents needs the agents experiment (for example e8_mix)")
        agents, cfg = load_agents(agents_exp, seed, len(world.params.layout))
        params = SimParams(
            **{
                **world.params.__dict__,
                "k": cfg["k"],
                "reject_enabled": cfg.get("reject_enabled", False),
            }
        )
        return LearnedPolicy(agents), params
    if name not in POLICIES:
        raise ValueError(f"unknown policy {name!r}; choose from {POLICIES}")
    mode, kw, factory = suite(world, 1.0)[name]
    return factory(seed), SimParams(**{**world.params.__dict__, **kw})
