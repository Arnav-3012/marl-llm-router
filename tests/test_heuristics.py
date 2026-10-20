"""Baseline policies on hand-built observations and tiny cluster states (M1.22)."""

import numpy as np

from marl_lb.policies.heuristics import (
    JSQ,
    AcceptAll,
    CacheAwareGlobal,
    CacheAwareLocal,
    Po2,
    RandomGlobal,
    RoundRobin,
    SEDGlobal,
    SEDLocal,
)  # fmt: skip
from marl_lb.sim.cluster import ACCEPT, DEFER, FORWARD, REJECT
from tests.helpers import make_cluster, req, stream_of

ALL = np.array([True, True, True])


def ob(own=0.0, nb=0.0, hit=0.0):
    return np.array([own, 0, 0, 0, 0, nb, hit], dtype=np.float32)


def test_accept_all_always_accepts_when_legal():
    assert AcceptAll().act(ob(), ALL) == ACCEPT


def test_sed_local_forwards_only_when_a_neighbour_looks_better():
    p = SEDLocal()
    assert p.act(ob(own=0.5, nb=0.2), ALL) == FORWARD
    assert p.act(ob(own=0.1, nb=0.2), ALL) == ACCEPT
    assert (
        p.act(ob(own=0.5, nb=0.0), np.array([True, False, True])) == ACCEPT
    )  # k=0: Forward masked
    assert p.act(ob(own=0.1, nb=0.2), np.array([False, True, True])) == FORWARD  # Accept masked


def test_cache_aware_local_keeps_a_cached_request_at_home():
    p = CacheAwareLocal(w=1.0)
    assert (
        p.act(ob(own=0.3, nb=0.1, hit=0.9), ALL) == ACCEPT
    )  # big overlap outweighs the extra wait
    assert p.act(ob(own=0.3, nb=0.1, hit=0.0), ALL) == FORWARD


def cluster_with(*loads):
    c = make_cluster(mode="global", global_policy=SEDGlobal())
    c.reset(stream_of([]), 0)
    for s, n in zip(c.servers, loads, strict=True):
        for i in range(n):
            s.enqueue(req(1000 * s.index + i, p=500, o=50), 0.0)
    return c


def test_jsq_picks_the_server_with_fewest_requests():
    assert JSQ().assign(cluster_with(3, 1), req()) == 1
    assert JSQ().assign(cluster_with(2, 2), req()) == 0  # ties go to the lowest index


def test_po2_with_two_servers_is_jsq():
    assert Po2(seed=0).assign(cluster_with(3, 1), req()) == 1


def test_round_robin_cycles_and_skips_a_full_server():
    c = cluster_with(0, 0)
    rr = RoundRobin()
    assert [rr.assign(c, req()) for _ in range(4)] == [0, 1, 0, 1]
    c.servers[0].max_queue = 0
    assert rr.assign(c, req()) == 1


def test_sed_global_uses_wait_plus_service_time():
    c = cluster_with(0, 0)
    assert SEDGlobal().assign(c, req(p=2000)) == 0  # idle fast beats idle slow
    c = cluster_with(6, 0)
    assert (
        SEDGlobal().assign(c, req(p=100)) == 1
    )  # a long line on the fast server tips it to the slow one


def test_cache_aware_global_follows_the_cache_unless_load_is_too_high():
    c = cluster_with(0, 0)
    c.servers[1].cache.insert(req(conv=7, p=800, o=100))
    follow = req(conv=7, turn=1, hist=True, p=900)
    assert CacheAwareGlobal(w=0.1, wait_scale_s=10.0).assign(c, follow) == 1
    assert CacheAwareGlobal(w=1e6, wait_scale_s=10.0).assign(cluster_with(0, 5), follow) == 0


def test_random_global_is_seeded():
    c = cluster_with(0, 0)
    a = [RandomGlobal(seed=4).assign(c, req()) for _ in range(5)]
    b = [RandomGlobal(seed=4).assign(c, req()) for _ in range(5)]
    assert a == b


def test_route_to_fast_forwards_from_slow_agents_and_accepts_on_fast_ones():
    from marl_lb.policies.heuristics import RouteToFast

    p = RouteToFast(["fast_expensive", "slow_cheap"])
    obs = None  # the rule ignores the observation
    all_ok = [True, True, True]
    assert p.act_agent(0, obs, all_ok) == ACCEPT  # fast agent accepts
    assert p.act_agent(1, obs, all_ok) == FORWARD  # slow agent forwards
    assert p.act_agent(1, obs, [True, False, True]) == ACCEPT  # cannot forward: accept
    assert p.act_agent(0, obs, [False, True, True]) == DEFER  # fast agent cannot accept: wait
    assert p.act_agent(0, obs, [False, True, False]) == FORWARD


def test_route_to_fast_shed_rejects_only_on_a_fast_agent_when_slack_is_gone():
    from marl_lb.policies.heuristics import RouteToFastShed

    p = RouteToFastShed(["fast_expensive", "slow_cheap"])
    legal = [True, True, True, True]
    late, ok = np.zeros(7, np.float32), np.zeros(7, np.float32)
    ok[3] = 0.5  # slack left
    assert p.act_agent(0, late, legal) == REJECT  # fast agent, no slack: shed
    assert p.act_agent(0, ok, legal) == ACCEPT  # fast agent with slack: accept
    assert p.act_agent(1, late, legal) == FORWARD  # slow agent never sheds, it forwards
    assert p.act_agent(1, late, [True, False, True, True]) == ACCEPT


def test_route_to_fast_spill_accepts_short_requests_on_a_busy_cluster_only():
    from marl_lb.policies.heuristics import RouteToFastSpill

    p = RouteToFastSpill(["fast_expensive", "slow_cheap"], theta=0.1)
    legal = [True, True, True]

    def o(prompt, slack, own, nb):
        v = np.zeros(7, np.float32)
        v[2], v[3], v[0], v[5] = prompt, slack, own, nb
        return v

    assert (
        p.act_agent(1, o(0.05, 0.5, 0.1, 0.4), legal) == ACCEPT
    )  # short, slack, neighbours busier
    assert p.act_agent(1, o(0.30, 0.5, 0.1, 0.4), legal) == FORWARD  # too long
    assert p.act_agent(1, o(0.05, 0.0, 0.1, 0.4), legal) == FORWARD  # cannot meet the target here
    assert p.act_agent(1, o(0.05, 0.5, 0.5, 0.4), legal) == FORWARD  # neighbours not busier
    assert p.act_agent(0, o(0.05, 0.5, 0.1, 0.4), legal) == ACCEPT  # fast agent: as route-to-fast
    assert (
        RouteToFastSpill(["fast", "slow"], 0.0).act_agent(1, o(0.0, 0.5, 0.1, 0.4), legal) == ACCEPT
    )


def test_route_to_fast_shed_tau_lets_a_slow_agent_keep_work_only_while_its_queue_is_short():
    from marl_lb.policies.heuristics import RouteToFastShedTau

    p = RouteToFastShedTau(["fast_expensive", "slow_cheap"], tau=0.1)
    legal = [True, True, True, True]

    def o(wait, slack):
        v = np.zeros(7, np.float32)
        v[0], v[3] = wait, slack
        return v

    assert p.act_agent(1, o(0.05, 0.5), legal) == ACCEPT  # short queue, slack left
    assert p.act_agent(1, o(0.30, 0.5), legal) == FORWARD  # queue too long
    assert p.act_agent(1, o(0.05, 0.0), legal) == FORWARD  # cannot meet the target here
    assert p.act_agent(0, o(0.05, 0.0), legal) == REJECT  # fast agent still sheds
