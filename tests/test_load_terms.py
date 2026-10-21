"""ADR-037 load terms: zero terms leave the simulator unchanged, positive terms slow decode."""

import copy

from marl_lb.sim.cluster import ACCEPT
from marl_lb.sim.server import Server
from tests.helpers import CLASSES, SIM, make_cluster, req, stream_of


def run_total(classes, rows):
    c = make_cluster(layout=("fast", "fast"))
    c.classes = classes
    c.servers = [Server(i, "fast", classes["fast"], SIM, c.p.est_output_tokens) for i in range(2)]
    c.reset(stream_of(rows), seed=0)
    while not c.run.finished:
        c.step({a: ACCEPT for a in c.agents})
    done = [r for r in c.run.requests if r.status == "done"]
    return sorted(r.t_done for r in done), len(done)


ROWS = [(0.0, 800, 40), (0.05, 900, 40), (0.1, 700, 40), (0.15, 600, 40)]


def test_zero_load_terms_change_nothing():
    base = copy.deepcopy(CLASSES)
    zero = copy.deepcopy(CLASSES)
    zero["fast"].update(ctx_decode=0.0, g_prefill=0.0, g_decode=0.0)
    assert run_total(base, ROWS) == run_total(zero, ROWS)


def test_positive_load_terms_make_requests_finish_later():
    base = copy.deepcopy(CLASSES)
    slow = copy.deepcopy(CLASSES)
    slow["fast"].update(ctx_decode=5e-6, g_prefill=0.2, g_decode=0.2)
    t0, n0 = run_total(base, ROWS)
    t1, n1 = run_total(slow, ROWS)
    assert n0 == n1 == len(ROWS) and t1[-1] > t0[-1]


def test_expected_wait_grows_with_the_context_term():
    s0 = Server(0, "fast", {**CLASSES["fast"]}, SIM, 50.0)
    s1 = Server(0, "fast", {**CLASSES["fast"], "ctx_decode": 1e-5}, SIM, 50.0)
    for s in (s0, s1):
        for i in range(3):
            s.enqueue(req(id=i, p=2000, o=50), 0.0)
        s._admit()
    assert s1.expected_wait() > s0.expected_wait()
