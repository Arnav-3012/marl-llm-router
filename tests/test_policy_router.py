"""Policy router and learned policy against mock servers (Sh.L1, Sh.L5)."""

import asyncio

import numpy as np

from marl_lb.policies.heuristics import AcceptAll, SEDGlobal, SEDLocal
from marl_lb.router.policy_router import LearnedPolicy
from marl_lb.sim.cluster import ACCEPT, DEFER, FORWARD, REJECT
from tests.helpers import req
from tests.router_helpers import make_router


# ---- policy router ---------------------------------------------------------------------------
async def run_many(router, n, p=200, o=6):
    outs = await asyncio.gather(
        *[router.handle(req(id=i, p=p, o=o, conv=i), list(range(p)), o) for i in range(n)]
    )
    return outs


def test_router_serves_requests_with_a_local_policy_and_empties_the_shadow_state():
    router, _ = make_router(SEDLocal())
    outs = asyncio.run(run_many(router, 6))
    assert all(o.status == "done" and o.completion.n_tokens == 6 for o in outs)
    assert all(
        not s.queue and not s.active and s.kv_fullness() == 0 for s in router.cluster.servers
    )
    kinds = [e["e"] for e in router.events.events]
    assert kinds.count("arrive") == 6 and kinds.count("resolve") == 6 and "act" in kinds
    assert all(e["ttft"] > 0 for e in router.events.events if e["e"] == "resolve")


def test_router_with_a_global_policy_sends_to_the_server_it_picks():
    router, _ = make_router(SEDGlobal())
    outs = asyncio.run(run_many(router, 3))
    assert all(o.status == "done" and o.server in (0, 1) for o in outs)


def test_forward_defer_and_reject_paths_and_their_limits():
    class Script:
        def __init__(self, acts):
            self.acts = list(acts)

        def act_agent(self, i, obs, mask):
            return self.acts.pop(0) if self.acts else ACCEPT

    router, _ = make_router(Script([FORWARD, DEFER, ACCEPT]), reject_enabled=True)
    (out,) = asyncio.run(run_many(router, 1))
    assert out.status == "done" and out.actions == [FORWARD, DEFER, ACCEPT]
    assert out.req.hops == 1 and out.req.defers == 1
    assert any(e["e"] == "forward" for e in router.events.events)
    router, _ = make_router(Script([REJECT]), reject_enabled=True)
    (out,) = asyncio.run(run_many(router, 1))
    assert out.status == "dropped" and out.server is None
    router, _ = make_router(Script([FORWARD, FORWARD, FORWARD, FORWARD]), max_hops=1)
    (out,) = asyncio.run(run_many(router, 1))  # a masked action is replaced by a legal one
    assert out.status == "done" and out.req.hops == 1


def test_a_backend_failure_drops_the_request_without_crashing_the_router():
    router, mocks = make_router(AcceptAll())

    async def boom(body):
        raise RuntimeError("backend down")
        yield  # pragma: no cover

    for m in mocks.values():
        m.generate = boom
    (out,) = asyncio.run(run_many(router, 1))
    assert out.status == "error" and out.completion is None
    assert all(not s.queue and not s.active for s in router.cluster.servers)


def test_learned_policy_acts_like_the_simulator_policy_on_the_same_observations():
    import yaml

    from marl_lb.agents.dqn_agent import DQNAgent
    from marl_lb.config import ROOT
    from marl_lb.train.loop import agent_actions

    cfg = yaml.safe_load((ROOT / "configs" / "dqn.yaml").read_text())
    agents = [DQNAgent(cfg, 100 + i) for i in range(2)]
    pol, rng = LearnedPolicy(agents), np.random.default_rng(0)
    for _ in range(50):
        obs = {f"agent_{i}": rng.random(7).astype(np.float32) for i in range(2)}
        masks = {f"agent_{i}": rng.random(3) > 0.3 for i in range(2)}
        for m in masks.values():
            m[0] = True  # at least one legal action
        infos = {k: {"decide": True, "mask": masks[k]} for k in obs}
        sim = agent_actions(agents, obs, infos, 0.0)
        live = {k: pol.act_agent(int(k[-1]), obs[k], masks[k]) for k in obs}
        assert sim == live
