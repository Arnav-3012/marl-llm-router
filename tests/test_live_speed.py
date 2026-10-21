"""ADR-039: the live router measures real server speeds and corrects its wait estimates."""

import pytest

from marl_lb.router.observation import LiveCluster
from tests.helpers import CLASSES, make_params, req


def shadow(adapt):
    return LiveCluster(make_params(("fast", "slow")), CLASSES, 50.0, adapt).servers[0]


def stream_tokens(s, r, gap, n=60):
    s.dispatch(r, 0.0)
    s.first_token(r, 0.1)
    t = 0.1
    for _ in range(n):
        t += gap
        s.token(r, t)
    return t


def test_slow_real_tokens_raise_the_wait_estimate_when_adaptive():
    nominal_gap = CLASSES["fast"]["t0"] + CLASSES["fast"]["k"] * 1
    off, on = shadow(False), shadow(True)
    for s in (off, on):
        stream_tokens(s, req(id=1, p=300, o=200), gap=nominal_gap * 8)
    probe = req(id=2, p=300, o=50)
    assert on.live_dec > 4.0 and off.live_dec == 1.0
    on.dispatch(probe, 5.0)
    off.dispatch(probe, 5.0)
    assert on.expected_wait() > off.expected_wait() * 2


def test_nominal_speed_leaves_the_estimate_alone():
    s = shadow(True)
    stream_tokens(s, req(id=1, p=300, o=200), gap=CLASSES["fast"]["t0"] + CLASSES["fast"]["k"])
    assert s.live_dec == pytest.approx(1.0, abs=0.05)


def test_slow_prompt_processing_raises_the_prefill_factor_only_when_adaptive():
    for adapt, expect_up in ((True, True), (False, False)):
        s = shadow(adapt)
        r = req(id=1, p=2000, o=10)
        s.dispatch(r, 0.0)
        nominal = s._pf0[r.id]
        s.first_token(r, nominal * 4)
        s.finish(r, nominal * 5, prompt_ms=nominal * 4000.0)
        assert (s.live_pf > 1.5) == expect_up


def test_the_simulator_servers_keep_factor_one():
    from tests.helpers import make_cluster, stream_of

    c = make_cluster()
    c.reset(stream_of([(0.0, 400, 30)]), seed=0)
    assert all(x.live_dec == 1.0 and x.live_pf == 1.0 for x in c.servers)
