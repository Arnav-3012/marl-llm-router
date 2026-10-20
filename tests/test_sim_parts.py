"""KV cache, prefix cache and server service time (M1.3 to M1.8). Numbers are hand-computed."""

import pytest

from marl_lb.sim.kv_cache import KVCache
from marl_lb.sim.prefix_cache import PrefixCache
from marl_lb.sim.server import Server
from tests.helpers import FAST, SIM, req


def server(cls=None, **kw) -> Server:
    return Server(0, "fast", {**FAST, **(cls or {}), **kw}, SIM, est_output_tokens=50.0)


# ---- KV cache ---------------------------------------------------------------------------------
def test_kv_admit_release_and_fullness():
    kv = KVCache(100)
    kv.admit(1, 60)
    assert kv.fullness() == pytest.approx(0.6) and kv.can_admit(40) and not kv.can_admit(41)
    kv.release(1)
    assert kv.used == 0


def test_kv_refuses_overfull_and_double_admit():
    kv = KVCache(100)
    kv.admit(1, 60)
    with pytest.raises(ValueError):
        kv.admit(2, 50)
    with pytest.raises(ValueError):
        kv.admit(1, 10)


# ---- prefix cache -----------------------------------------------------------------------------
def test_prefix_hit_needs_history_and_an_earlier_turn():
    c = PrefixCache(10_000)
    first = req(conv=5, p=500, o=100)
    c.insert(first)  # conversation 5 is now cached up to 600 tokens
    assert c.hit_tokens(req(conv=5, turn=1, hist=True, p=700)) == 600
    assert c.hit_tokens(req(conv=5, turn=1, hist=True, p=400)) == 400  # never more than the prompt
    assert c.hit_tokens(req(conv=5, turn=1, hist=False, p=700)) == 0  # turn without re-sent history
    assert (
        c.hit_tokens(req(conv=5, turn=0, hist=True, p=700)) == 0
    )  # a first turn has nothing before it
    assert c.hit_tokens(req(conv=6, turn=1, hist=True, p=700)) == 0  # other conversation


def test_prefix_cache_evicts_least_recently_used():
    c = PrefixCache(1000)
    c.insert(req(conv=1, p=300, o=100))  # 400
    c.insert(req(conv=2, p=300, o=100))  # 400
    c.hit_tokens(req(conv=1, turn=1, hist=True), touch=True)  # conversation 1 is now the freshest
    c.insert(req(conv=3, p=300, o=100))  # needs room: evicts conversation 2
    assert c.hit_tokens(req(conv=2, turn=1, hist=True)) == 0
    assert c.hit_tokens(req(conv=1, turn=1, hist=True)) > 0
    assert c.used <= c.capacity


def test_prefix_cache_ignores_an_entry_bigger_than_itself():
    c = PrefixCache(100)
    c.insert(req(conv=1, p=300, o=100))
    assert c.used == 0


# ---- server -----------------------------------------------------------------------------------
def finish(s, reqs, window=1000.0, step=None):
    """Enqueue at t=0 and advance either in one window or in `step`-sized windows."""
    for r in reqs:
        s.enqueue(r, 0.0)
    done, t = [], 0.0
    while t < window - 1e-12 and (s.n_present() or t == 0.0):
        t2 = min(t + (step or window), window)
        done += s.advance(t, t2, 0, 4)
        t = t2
    return done


def test_single_request_prefill_then_decode_time():
    s = server()
    r = req(p=1000, o=10)
    finish(s, [r])
    # prefill 1000 * 0.001 = 1.0 s, then 10 decode steps of t0 + k*1 = 0.012 s
    assert r.t_first == pytest.approx(1.0 + 0.012)
    assert r.t_done == pytest.approx(1.0 + 10 * 0.012)
    assert r.tpot == pytest.approx(0.012)


def test_prefill_quadratic_term_prices_effective_tokens():
    s = server(prefill_quad=1.0e-6)
    r = req(p=1000, o=10)
    s.enqueue(r, 0.0)
    # 0.001 * 1000 + 1e-6 * 1000^2 = 1.0 + 1.0 = 2.0 s (curving up with prompt length)
    assert r.pf_left == pytest.approx(2.0) and s.prefill_seconds(r) == pytest.approx(2.0)


def test_prefill_quadratic_term_applies_to_effective_tokens_after_a_cache_hit():
    s = server(prefill_quad=1.0e-6)
    finish(s, [req(0, conv=5, p=500, o=100)])
    nxt = req(1, conv=5, turn=1, hist=True, p=700)
    s.enqueue(nxt, 0.0)
    # effective = (700 - 600) + 0.1 * 600 = 160 tokens: 0.001 * 160 + 1e-6 * 160^2 = 0.1856
    assert nxt.pf_left == pytest.approx(0.1856)


def test_two_requests_share_decode_steps_after_sequential_prefill():
    s = server()
    a, b = req(0, p=100, o=10), req(1, p=100, o=10)
    finish(s, [a, b])
    # prefill A 0..0.1, prefill B 0.1..0.2, then B=2: step = 0.01 + 0.002 * 2 = 0.014
    assert a.t_first == pytest.approx(0.2 + 0.014) and b.t_first == pytest.approx(0.2 + 0.014)
    assert a.t_done == pytest.approx(0.2 + 10 * 0.014)


def test_result_does_not_depend_on_how_time_is_cut_into_windows():
    one, many = server(), server()
    ra = [req(0, p=100, o=10), req(1, p=300, o=25)]
    rb = [req(0, p=100, o=10), req(1, p=300, o=25)]
    finish(one, ra, window=2.0)
    finish(many, rb, window=2.0, step=0.1)
    for x, y in zip(ra, rb, strict=True):
        assert x.t_first == pytest.approx(y.t_first, abs=1e-9)
        assert x.t_done == pytest.approx(y.t_done, abs=1e-9)
    assert one.busy_seconds == pytest.approx(many.busy_seconds)


def test_interference_stretches_prefill_and_decode_separately():
    s = server(s_prefill=0.5, s_decode=0.2)
    r = req(p=1000, o=10)
    r2 = r
    s.enqueue(r2, 0.0)
    s.advance(0.0, 100.0, n_other_busy=3, n_servers=4)  # scale = 3/3 = 1
    assert r.t_first == pytest.approx(1.5 + 0.012 * 1.2)
    assert r.t_done == pytest.approx(1.5 + 10 * 0.012 * 1.2)


def test_cached_prefix_shortens_prefill_by_the_fitted_ratio():
    s = server()
    first = req(0, conv=5, p=500, o=100)
    finish(s, [first])
    nxt = req(1, conv=5, turn=1, hist=True, p=700)
    s.enqueue(nxt, 0.0)
    # hit = min(700, 600) = 600 cached tokens: 0.001 * ((700 - 600) + 0.1 * 600) = 0.16
    assert nxt.cached_tokens == 600 and nxt.pf_left == pytest.approx(0.16)


def test_attributed_seconds_add_up_to_busy_seconds():
    s = server()
    rs = [req(i, p=100 * (i + 1), o=8 + i) for i in range(3)]
    finish(s, rs)
    assert sum(r.attributed_s for r in rs) == pytest.approx(s.busy_seconds)


def test_kv_budget_holds_back_a_second_big_request_until_the_first_finishes():
    s = server(kv_token_budget=10_000)
    a, b = req(0, p=6000, o=1000), req(1, p=6000, o=1000)
    s.enqueue(a, 0.0)
    s.enqueue(b, 0.0)
    s.advance(0.0, 0.5, 0, 4)
    assert len(s.active) == 1 and len(s.queue) == 1
    s.advance(0.5, 1000.0, 0, 4)
    assert a.t_done < b.t_first  # FIFO: b only started after a released its KV


def test_slots_limit_the_batch():
    s = server(max_batch=2)
    for i in range(4):
        s.enqueue(req(i, p=10, o=5), 0.0)
    s.advance(0.0, 0.05, 0, 4)
    assert len(s.active) <= 2


def test_expected_wait_is_zero_when_idle_and_grows_with_work():
    s = server()
    assert s.expected_wait() == 0.0
    s.enqueue(req(0, p=1000, o=10), 0.0)
    w1 = s.expected_wait()
    s.enqueue(req(1, p=1000, o=10), 0.0)
    assert w1 > 0 and s.expected_wait() > w1


def test_can_accept_respects_the_queue_cap_and_kv_size():
    s = server()
    assert not s.can_accept(req(p=20_000, o=10))  # can never fit the KV budget
    s = Server(0, "fast", FAST, {"max_queue": 1, "prefix_cache_fraction": 0.5}, 50.0)
    s.enqueue(req(0), 0.0)
    assert not s.can_accept(req(1))
