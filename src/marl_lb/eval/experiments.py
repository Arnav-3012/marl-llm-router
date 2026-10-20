"""The policy suite and the held-out evaluation used by scripts/evaluate.py and
scripts/run_experiment.py. Tier B.

Every policy is evaluated on the SAME held-out stream: world.stream(rate, seed, "heldout") depends
only on
(rate, seed), not on the policy (CLAUDE.md: baselines run on the exact same traffic as the learned
policies).
"""

from __future__ import annotations

from marl_lb.eval.evaluate import World, local_actions, run_episode, save_events
from marl_lb.policies import heuristics as H
from marl_lb.sim.cluster import slice_stream
from marl_lb.train.loop import greedy_actions

# Development windows on TRAIN traffic start after the stream's session ramp-up (ADR-022): think
# times are not rescaled, so the first ~1800 s have far fewer arrivals than the mean rate.
DEV_WINDOW_START_S = 1800.0


def stream_for(
    world: World, rate: float, seed: int, split: str, window_s: float | None = None
) -> list:
    """Held-out traffic for the final numbers (the whole stream). split='train' with a window is
    for development checks only: [1800 s, 1800 s + window_s) of the train stream, re-zeroed.
    """
    s = world.stream(rate, seed, split)
    return s if window_s is None else slice_stream(s, DEV_WINDOW_START_S, window_s)


def suite(world: World, cache_w: float) -> dict:
    """name -> (mode, cluster kwargs, policy factory). Local forms run in the agents cluster with
    the
    given k.
    """
    scale = world.params.wait_scale_s
    return {
        "random": ("agents", {"k": "full"}, lambda seed: H.AcceptAll()),
        "sed_local_k0": ("agents", {"k": 0}, lambda seed: H.SEDLocal()),
        "sed_local_k1": ("agents", {"k": 1}, lambda seed: H.SEDLocal()),
        "sed_local_full": ("agents", {"k": "full"}, lambda seed: H.SEDLocal()),
        "cache_aware_local_full": (
            "agents",
            {"k": "full"},
            lambda seed: H.CacheAwareLocal(cache_w),
        ),
        "route_to_fast": ("agents", {"k": "full"}, lambda seed: H.RouteToFast(world.params.layout)),
        # ADR-029: the same rule plus load shedding, run in the 4-action cluster
        "route_to_fast_shed": (
            "agents",
            {"k": "full", "reject_enabled": True},
            lambda seed: H.RouteToFastShed(world.params.layout),
        ),
        "round_robin": ("global", {}, lambda seed: H.RoundRobin()),
        "jsq_global": ("global", {}, lambda seed: H.JSQ()),
        "po2_global": ("global", {}, lambda seed: H.Po2(seed)),
        "sed_global": ("global", {}, lambda seed: H.SEDGlobal()),
        "cache_aware_global": ("global", {}, lambda seed: H.CacheAwareGlobal(cache_w, scale)),
    }


def eval_baseline(
    world: World,
    name: str,
    cache_w: float,
    rate: float,
    seed: int,
    events_path=None,
    split: str = "heldout",
    window_s=None,
) -> dict:
    mode, kw, factory = suite(world, cache_w)[name]
    policy = factory(seed)
    record = events_path is not None
    if mode == "global":
        cluster = world.cluster(mode="global", global_policy=policy, record_events=record, **kw)
        metrics, _ = run_episode(cluster, stream_for(world, rate, seed, split, window_s), seed)
    else:
        cluster = world.cluster(record_events=record, **kw)
        metrics, _ = run_episode(
            cluster, stream_for(world, rate, seed, split, window_s), seed, local_actions(policy)
        )
    if record:
        save_events(cluster, events_path)
    return metrics


def eval_agents(
    world: World,
    agents: list,
    rate: float,
    seed: int,
    k,
    events_path=None,
    split: str = "heldout",
    window_s=None,
    fallback=None,
    **cluster_kw,
) -> dict:
    record = events_path is not None
    cluster = world.cluster(k=k, record_events=record, **cluster_kw)
    metrics, _ = run_episode(
        cluster,
        stream_for(world, rate, seed, split, window_s),
        seed,
        greedy_actions(agents, fallback),
    )
    if record:
        save_events(cluster, events_path)
    return metrics
