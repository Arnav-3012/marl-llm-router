"""Shared builders for simulator tests: tiny, hand-checkable classes, params and streams."""

from marl_lb.data.traces import StreamRequest
from marl_lb.sim.cluster import Cluster, SimParams
from marl_lb.sim.request import Request

FAST = {
    "a": 0.001, "cached_token_cost_ratio": 0.1, "t0": 0.01, "k": 0.002,
    "s_prefill": 0.0, "s_decode": 0.0, "kv_token_budget": 10_000, "max_batch": 4,
    "price_per_busy_second": 3.0,
}  # fmt: skip
SLOW = {**FAST, "a": 0.008, "t0": 0.02, "k": 0.004, "price_per_busy_second": 1.0}
CLASSES = {"fast": FAST, "slow": SLOW}
SIM = {"max_queue": 8, "prefix_cache_fraction": 0.5}


def make_params(layout=("fast", "slow"), **kw) -> SimParams:
    base = dict(
        layout=list(layout), dt=0.1, max_hops=2, max_defers=2, max_queue=8,
        prefix_cache_fraction=0.5, ttft_target=2.0, tpot_target=0.05, est_output_tokens=50.0,
        prompt_norm=4000.0, wait_scale_s=10.0, max_drain_s=100.0, k="full",
    )  # fmt: skip
    base.update(kw)
    return SimParams(**base)


def make_cluster(layout=("fast", "slow"), mode="agents", global_policy=None, record=False, **kw):
    return Cluster(make_params(layout, **kw), CLASSES, mode, global_policy, record)


def stream_of(rows) -> list:
    """rows: (arrival_s, prompt_tokens, output_tokens) -> StreamRequests, one conversation each."""
    return [StreamRequest(a, p, o, i, 0, False) for i, (a, p, o) in enumerate(rows)]


def req(
    id=0, p=100, o=10, conv=0, turn=0, hist=False, arrival=0.0, ttft=100.0, tpot=100.0
) -> Request:
    return Request(id, arrival, p, o, conv, turn, hist, ttft, tpot)
