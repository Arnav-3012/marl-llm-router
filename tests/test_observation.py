"""Live observation equals the simulator's for the same state (Sh.L1)."""

import copy

import numpy as np
import pytest

from marl_lb.router.observation import LiveCluster
from marl_lb.sim.cluster import ACCEPT
from tests.helpers import CLASSES, make_cluster, make_params, req, stream_of


# ---- observation (Sh.L1: live observation equals the simulator's for the same state) ---------
def clone_into(live, sim_cluster):
    """Copy the simulator servers' queue, active, KV and cache state into the shadow servers."""
    for s_sim, s_live in zip(sim_cluster.servers, live.servers, strict=True):
        for src, dst in ((s_sim.queue, s_live.queue), (s_sim.active, s_live.active)):
            for r in src:
                dst.append(copy.copy(r))
        for r in s_sim.active:
            s_live.kv.admit(r.id, r.prompt_tokens + r.output_tokens)
        s_live.cache._store = dict(s_sim.cache._store)
        s_live.cache.used = s_sim.cache.used


def test_live_observation_equals_the_simulator_observation_for_the_same_state():
    c = make_cluster(layout=("fast", "slow", "fast"), k="full")
    rows = [(0.0, 400, 30), (0.1, 900, 40), (0.2, 300, 20), (0.3, 1200, 60)]
    c.reset(stream_of(rows), seed=0)
    for _ in range(6):  # let some requests start and run
        c.step({a: ACCEPT for a in c.agents})
    live = LiveCluster(c.p, CLASSES, c.p.est_output_tokens)
    clone_into(live, c)
    probe = req(id=99, p=700, o=30, arrival=c.run.t - 0.5)
    for i in range(3):
        sim_obs = c._obs_vector(i, probe)
        live_obs = live.observation(i, probe, c.run.t)
        assert np.array_equal(sim_obs, live_obs), (i, sim_obs, live_obs)
        assert np.array_equal(c._mask(i, probe), live.mask(i, probe))
    assert any(s.n_present() > 0 for s in c.servers)  # the state was not empty


def test_shadow_bookkeeping_follows_dispatch_first_token_and_finish():
    live = LiveCluster(make_params(("fast", "slow")), CLASSES, 50.0)
    s, r = live.servers[0], req(id=1, p=400, o=10, arrival=0.0)
    s.dispatch(r, 0.0)
    assert len(s.queue) == 1 and s.expected_wait() > 0 and s.kv_fullness() == 0
    s.refresh(0.2)
    assert r.pf_left == pytest.approx(max(s._pf0[1] - 0.2, 0.0))
    n = s.first_token(r, 0.3)
    assert n == 1 and len(s.active) == 1 and not s.queue and s.kv_fullness() > 0 and r.pf_left == 0
    before = s.expected_wait()
    for _ in range(5):
        s.token(r)
    assert s.expected_wait() < before  # fewer tokens still expected
    s.finish(r, 1.0)
    assert (
        not s.active
        and s.kv_fullness() == 0
        and s.completed == 1
        and s.busy_seconds == pytest.approx(1.0)
    )
    assert s.cache.hit_tokens(req(id=2, p=500, o=5, conv=r.conv_id, turn=1, hist=True)) > 0
