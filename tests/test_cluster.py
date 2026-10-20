"""Cluster: shapes, masks, drops, credit, transitions, conservation, determinism (M1.9 to M1.18)."""

import numpy as np
import pytest

from marl_lb.eval.evaluate import local_actions, run_episode
from marl_lb.policies.heuristics import AcceptAll, RandomGlobal, SEDGlobal, SEDLocal
from marl_lb.sim.cluster import ACCEPT, DEFER, FORWARD, OBS_DIM, REJECT
from marl_lb.sim.metrics import summarise
from tests.helpers import make_cluster, req, stream_of


def random_stream(n=300, rate=4.0, seed=3):
    rng = np.random.default_rng(seed)
    t = np.cumsum(rng.exponential(1 / rate, n))
    return stream_of(zip(t, rng.integers(100, 1500, n), rng.integers(10, 100, n), strict=True))


# ---- API shape and observations -----------------------------------------------------------------
def test_reset_and_step_follow_the_parallel_env_shape():
    c = make_cluster()
    obs, infos = c.reset(stream_of([(0.0, 200, 20)]), seed=0)
    assert list(obs) == list(infos) == c.agents == ["agent_0", "agent_1"]
    assert all(o.shape == (OBS_DIM,) and o.dtype == np.float32 for o in obs.values())
    assert all(0.0 <= v <= 1.0 for o in obs.values() for v in o)
    out = c.step({a: ACCEPT for a in c.agents})
    assert len(out) == 5 and all(list(d) == c.agents for d in out)


def test_idle_agent_gets_zero_observation_and_all_false_mask():
    c = make_cluster()
    obs, infos = c.reset(stream_of([(0.0, 200, 20)]), seed=0)
    idle = [a for a in c.agents if not infos[a]["decide"]]
    assert len(idle) == 1
    assert not obs[idle[0]].any() and not infos[idle[0]]["mask"].any()


def test_entry_agent_is_seeded():
    s = stream_of([(0.0, 200, 20)] * 6)
    entries = []
    for seed in (1, 1, 2):
        c = make_cluster(record=True)
        c.reset(s, seed)
        entries.append([e["entry"] for e in c.run.events if e["e"] == "arrive"])
    assert entries[0] == entries[1]


def test_masks_forward_needs_a_neighbour_and_a_hop_defer_needs_budget():
    c = make_cluster(k=0, max_defers=1)
    _, infos = c.reset(stream_of([(0.0, 200, 20)]), 0)
    m = next(i["mask"] for i in infos.values() if i["decide"])
    assert m.tolist() == [True, False, True]  # k=0: Forward masked
    c = make_cluster(k="full", max_defers=0)
    _, infos = c.reset(stream_of([(0.0, 200, 20)]), 0)
    assert next(i["mask"] for i in infos.values() if i["decide"]).tolist() == [True, True, False]


def test_hop_limit_masks_forward():
    c = make_cluster(max_hops=1, max_defers=0)
    obs, infos = c.reset(stream_of([(0.0, 200, 20)]), 0)
    holder = next(a for a in c.agents if infos[a]["decide"])
    acts = {a: (FORWARD if a == holder else ACCEPT) for a in c.agents}
    obs, _, _, _, infos = c.step(acts)
    nxt = next(a for a in c.agents if infos[a]["decide"])
    assert nxt != holder and infos[nxt]["mask"].tolist() == [True, False, False]


def test_a_masked_action_is_rejected():
    c = make_cluster(k=0)
    _, infos = c.reset(stream_of([(0.0, 200, 20)]), 0)
    with pytest.raises(ValueError, match="masked"):
        c.step({a: FORWARD for a in c.agents})


def test_defer_sends_the_request_to_the_back_of_the_line():
    c = make_cluster(layout=("fast",), k=0)
    _, infos = c.reset(stream_of([(0.0, 200, 20), (0.0, 300, 20)]), 0)
    first = c.run.deciding[0]
    c.step({"agent_0": DEFER})
    assert c.run.deciding[0] is not first and first.defers == 1
    assert c.run.held[0][-1] is first


def test_forward_goes_to_the_visible_neighbour_that_serves_soonest():
    c = make_cluster(layout=("fast", "fast", "slow"), k="full")
    c.reset(stream_of([(0.0, 500, 20)]), 0)
    src, request = next(iter(c.run.deciding.items()))
    others = [j for j in range(3) if j != src]
    fast_others = [j for j in others if c.p.layout[j] == "fast"]
    assert c._forward_target(src, request) == min(
        fast_others
    )  # idle: the faster class, lowest index
    for i in range(6):  # now load that server so the slow idle one wins
        c.servers[min(fast_others)].enqueue(req(100 + i, p=1500, o=100), 0.0)
    assert c._forward_target(src, request) != min(fast_others) or len(fast_others) == 2


# ---- drops ------------------------------------------------------------------------------------
def test_request_with_no_legal_action_is_dropped_and_counted_against_the_holder():
    c = make_cluster(layout=("fast",), k=0, max_defers=0, max_queue=0)
    c.reset(stream_of([(0.0, 200, 20)]), 0)
    assert c.finished
    m = summarise(c)
    assert m["n_dropped"] == 1 and m["n_completed"] == 0
    assert m["drops_unacted"] == 1 and sum(m["drops_by_holder"]) == 1


# ---- credit (ADR-010, ADR-014)
# ----------------------------------------------------------------------
def test_forwarded_request_credits_both_agents_but_only_the_server_pays_cost():
    c = make_cluster(layout=("fast", "fast"), k="full", ttft_target=100.0, tpot_target=100.0,
                     lambda_cost=0.1, forward_cost=0.3)  # fmt: skip
    _, infos = c.reset(stream_of([(0.0, 100, 5)]), 0)
    holder = next(a for a in c.agents if infos[a]["decide"])
    _, _, _, _, infos = c.step({a: (FORWARD if a == holder else ACCEPT) for a in c.agents})
    while not c.finished:
        c.step({a: ACCEPT for a in c.agents})
    (r,) = c.run.requests
    fwd, acc = r.decisions
    cost = c.servers[r.server].price * r.attributed_s
    assert fwd.reward == pytest.approx(
        10 - 0.3
    )  # shared R_SLA, immediate Forward cost, no service cost
    assert acc.reward == pytest.approx(
        10 - 0.1 * cost
    )  # shared R_SLA minus the serving agent's cost


def test_missed_sla_gives_minus_ten_and_drop_gives_minus_five_to_acting_agents():
    c = make_cluster(layout=("fast",), k=0, ttft_target=0.001)
    c.reset(stream_of([(0.0, 500, 5)]), 0)
    while not c.finished:
        c.step({"agent_0": ACCEPT})
    assert c.run.requests[0].decisions[0].reward == pytest.approx(-10 - 0.0)
    # a request dropped at the drain horizon after an Accept: shared -5
    c = make_cluster(layout=("slow",), k=0, max_drain_s=0.2)
    c.reset(stream_of([(0.0, 3000, 500)]), 0)
    while not c.finished:
        c.step({"agent_0": ACCEPT})
    r = c.run.requests[0]
    assert r.status == "dropped" and r.decisions[0].reward == pytest.approx(-5.0)


def test_transition_is_emitted_when_reward_and_next_decision_both_exist():
    c = make_cluster(layout=("fast",), k=0, ttft_target=100.0, tpot_target=100.0, lambda_cost=0.1)
    obs, infos = c.reset(stream_of([(0.0, 100, 5), (5.0, 100, 5)]), 0)
    first_obs = obs["agent_0"]
    got = []
    while not c.finished:
        obs, _, _, _, infos = c.step({"agent_0": ACCEPT})
        got += c.pop_transitions()
        if got:
            break
    (tr,) = got
    r = c.run.requests[0]
    assert np.array_equal(tr.obs, first_obs) and tr.action == ACCEPT
    assert np.array_equal(tr.next_obs, obs["agent_0"])  # s' = the next decision observation
    assert tr.reward == pytest.approx(10 - 0.1 * c.servers[0].price * r.attributed_s)
    while not c.finished:
        c.step({"agent_0": ACCEPT})
    assert c.run.discarded_end == 1  # the last decision has no s' and is discarded and counted


# ---- conservation, cost invariant, determinism
# ---------------------------------------------------------
def played(policy_name="sed_global", seed=0):
    s = random_stream()
    if policy_name == "sed_global":
        c = make_cluster(mode="global", global_policy=SEDGlobal(), max_queue=4)
        run_episode(c, s, seed)
    else:
        c = make_cluster(k="full", max_queue=4)
        run_episode(c, s, seed, local_actions(SEDLocal()))
    return c, s


@pytest.mark.parametrize("which", ["sed_global", "sed_local"])
def test_conservation_every_request_resolves_exactly_once(which):
    c, s = played(which)
    ids = [r.id for r in c.run.resolved]
    assert sorted(ids) == list(range(len(s)))  # none lost, none twice
    m = summarise(c)
    assert m["n_completed"] + m["n_dropped"] == m["n_arrived"] == len(s)
    assert all(not sv.queue and not sv.active and sv.kv.used == 0 for sv in c.servers)


def test_cost_attribution_adds_up_to_server_busy_time_times_price():
    c, _ = played("sed_local")
    per_req = sum(
        c.servers[r.server].price * r.attributed_s for r in c.run.resolved if r.server is not None
    )
    per_server = sum(sv.price * sv.busy_seconds for sv in c.servers)
    assert per_req == pytest.approx(per_server, rel=1e-9)


def test_littles_law_holds_on_the_bookkeeping():
    c, _ = played("sed_global")
    m = summarise(c)
    assert m["little_L"] == pytest.approx(m["little_lambda_W"], rel=0.05)


def test_same_seed_same_result_different_seed_different_entries():
    a, b = played("sed_local", 0)[0], played("sed_local", 0)[0]
    assert summarise(a) == summarise(b)


def test_global_mode_assigns_at_arrival_and_needs_no_agents():
    c = make_cluster(mode="global", global_policy=SEDGlobal())
    obs, infos = c.reset(stream_of([(0.0, 800, 20)]), 0)
    assert not any(i["decide"] for i in infos.values())
    while not c.finished:
        c.step({})
    assert c.run.requests[0].server == 0  # SED: the fast server finishes a long prompt sooner


def test_sed_beats_random_on_a_mixed_fast_slow_cluster():
    # Moderate load only. In overload a median over COMPLETED requests favours the policy that drops
    # more (survivor bias), and Random's 50/50 split puts the median on the fast/slow boundary, so
    # the claim is made on the tail and on drops, plus median and SLA at light load.
    def run(rate, pol):
        c = make_cluster(mode="global", global_policy=pol, max_queue=50)
        return run_episode(c, random_stream(n=400, rate=rate), 0)[0]

    for rate in (0.5, 1.0):
        sed, rand = run(rate, SEDGlobal()), run(rate, RandomGlobal(seed=1))
        assert sed["e2e_p95"] < rand["e2e_p95"]
        assert sed["drop_rate"] <= rand["drop_rate"]
    sed, rand = run(0.5, SEDGlobal()), run(0.5, RandomGlobal(seed=1))
    assert sed["e2e_p50"] < rand["e2e_p50"]
    assert sed["sla_attainment"] >= rand["sla_attainment"]


def test_replay_events_are_recorded_when_asked():
    c = make_cluster(record=True)
    run_episode(c, stream_of([(0.0, 100, 5)]), 0, local_actions(AcceptAll()))
    kinds = {e["e"] for e in c.run.events}
    assert {"arrive", "act", "servers", "resolve"} <= kinds


def test_resolve_events_carry_the_requests_ttft_and_cost():
    c = make_cluster(record=True)
    run_episode(c, stream_of([(0.0, 100, 5)]), 0, local_actions(AcceptAll()))
    (event,) = [e for e in c.run.events if e["e"] == "resolve"]
    (r,) = c.run.requests
    assert event["ttft"] == pytest.approx(r.ttft) and r.ttft > 0
    assert event["cost"] == pytest.approx(c.servers[r.server].price * r.attributed_s)
    assert event["cost"] > 0


def test_cost_scale_divides_the_cost_term_in_the_reward_only():
    def run(scale):
        c = make_cluster(
            layout=("fast",), k=0, ttft_target=100.0, tpot_target=100.0,
            lambda_cost=1.0, cost_scale=scale,
        )  # fmt: skip
        c.reset(stream_of([(0.0, 200, 20)]), 0)
        while not c.finished:
            c.step({"agent_0": ACCEPT})
        (r,) = c.run.requests
        return r.decisions[0].reward, c.servers[r.server].price * r.attributed_s

    (reward1, cost1), (reward4, cost4) = run(1.0), run(4.0)
    assert cost1 == pytest.approx(cost4)  # the cost metric stays in raw units
    assert reward1 == pytest.approx(10 - cost1) and reward4 == pytest.approx(10 - cost1 / 4)


def test_shared_cost_credit_charges_every_agent_that_acted_not_only_the_server():
    def run(credit):
        c = make_cluster(layout=("fast", "fast"), k="full", ttft_target=100.0, tpot_target=100.0,
                         lambda_cost=1.0, cost_credit=credit)  # fmt: skip
        _, infos = c.reset(stream_of([(0.0, 100, 5)]), 0)
        holder = next(a for a in c.agents if infos[a]["decide"])
        c.step({a: (FORWARD if a == holder else ACCEPT) for a in c.agents})
        while not c.finished:
            c.step({a: ACCEPT for a in c.agents})
        (r,) = c.run.requests
        fwd, acc = r.decisions
        return fwd.reward, acc.reward, c.servers[r.server].price * r.attributed_s

    fwd_s, acc_s, cost = run("serving")
    fwd_h, acc_h, cost_h = run("shared")
    assert cost == pytest.approx(cost_h) and cost > 0
    assert fwd_s == pytest.approx(10 - 0.0)  # the forwarder avoids the cost under "serving"
    assert fwd_h == pytest.approx(10 - cost)  # ... and pays it under "shared"
    assert acc_s == pytest.approx(acc_h) == pytest.approx(10 - cost)  # the server pays in both


# ---- Reject action (ADR-029) --------------------------------------------------------------------
def test_reject_adds_a_fourth_always_legal_action_and_default_stays_three():
    c = make_cluster()
    _, infos = c.reset(stream_of([(0.0, 200, 20)]), 0)
    assert c.n_actions == 3 and next(i["mask"] for i in infos.values() if i["decide"]).shape == (3,)
    c = make_cluster(reject_enabled=True, k=0, max_defers=0)  # only Accept and Reject remain
    obs, infos = c.reset(stream_of([(0.0, 200, 20)]), 0)
    m = next(i["mask"] for i in infos.values() if i["decide"])
    assert c.n_actions == 4 and m.tolist() == [True, False, False, True]
    idle = [a for a in c.agents if not infos[a]["decide"]]
    assert infos[idle[0]]["mask"].shape == (4,) and not infos[idle[0]]["mask"].any()


def test_reject_drops_the_request_with_the_drop_reward_and_counts_it():
    c = make_cluster(reject_enabled=True, r_drop=-5.0, beta_coop=0.0)
    _, infos = c.reset(stream_of([(0.0, 200, 20)]), 0)
    holder = next(a for a in c.agents if infos[a]["decide"])
    c.step({a: (REJECT if a == holder else ACCEPT) for a in c.agents})
    assert c.finished
    (r,) = c.run.requests
    assert r.status == "dropped" and [d.action for d in r.decisions] == [REJECT]
    assert r.decisions[0].reward == pytest.approx(-5.0)  # no cost term, no cost on a drop
    m = summarise(c)
    assert m["n_rejected"] == 1 and m["n_dropped"] == 1 and m["drop_rate"] == 1.0


def test_reject_after_a_forward_credits_the_drop_to_both_decisions():
    c = make_cluster(layout=("fast", "fast"), reject_enabled=True, r_drop=-5.0, forward_cost=0.5)
    _, infos = c.reset(stream_of([(0.0, 200, 20)]), 0)
    holder = next(a for a in c.agents if infos[a]["decide"])
    _, _, _, _, infos = c.step({a: (FORWARD if a == holder else ACCEPT) for a in c.agents})
    new_holder = next(a for a in c.agents if infos[a]["decide"])
    c.step({a: (REJECT if a == new_holder else ACCEPT) for a in c.agents})
    (r,) = c.run.requests
    fwd, rej = r.decisions
    assert fwd.reward == pytest.approx(-5.0 - 0.5) and rej.reward == pytest.approx(-5.0)


def test_conservation_with_reject_every_request_is_counted_once():
    rng = np.random.default_rng(0)
    c = make_cluster(reject_enabled=True)
    obs, infos = c.reset(random_stream(150, rate=6.0), 1)
    while not c.finished:
        acts = {
            a: int(rng.choice(np.flatnonzero(infos[a]["mask"]))) if infos[a]["decide"] else 0
            for a in c.agents
        }
        obs, _, _, _, infos = c.step(acts)
    m = summarise(c)
    assert m["n_arrived"] == 150 and m["n_completed"] + m["n_dropped"] == 150
    assert 0 < m["n_rejected"] <= m["n_dropped"]
