"""Route live requests with a policy: observe, mask, act, then accept/forward/defer/reject. Tier A.

The decision loop is the simulator's (ADR-013): a request enters at a uniformly random agent; each
decision sees that agent's observation and legal mask; Forward goes to the visible neighbour with
the least expected wait plus service time and counts a hop; Defer waits one decision tick; Reject
drops.
Local policies (heuristics, learned agents) act per agent; global policies pick the server at
arrival. A request is streamed from the backend while the shadow state is updated from what the
router sees, so the next observation reflects it.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import numpy as np

from marl_lb.router.observation import LiveCluster
from marl_lb.router.server_client import Completion, LlamaClient
from marl_lb.sim.cluster import ACCEPT, DEFER, FORWARD, REJECT, forward_target


@dataclass
class Outcome:
    req: object
    status: str  # done | dropped | error
    server: int | None
    completion: Completion | None
    actions: list
    cost: float | None = None


class LearnedPolicy:
    """Saved per-agent weights acting greedily (epsilon = 0) on live observations (Sh.L5)."""

    name = "ddqn_agents"

    def __init__(self, agents: list):
        self.agents = agents

    def act_agent(self, i: int, obs, mask) -> int:
        return int(self.agents[i].act(obs, mask, 0.0))


def is_global(policy) -> bool:
    return hasattr(policy, "assign")


class PolicyRouter:
    def __init__(
        self,
        backends: list,
        cluster: LiveCluster,
        policy,
        client: LlamaClient,
        clock,
        events,
        seed: int = 0,
        decision_dt: float = 0.1,
    ):
        self.backends, self.cluster, self.policy = backends, cluster, policy
        self.client, self.clock, self.events = client, clock, events
        self.rng = np.random.default_rng(seed)
        self.dt, self.t0 = decision_dt, clock()
        self.resolved: list = []

    def now(self) -> float:
        return self.clock() - self.t0

    def _decide(self, i: int, req, now: float) -> tuple[int, int | None]:
        """(action, server for a global policy); a local policy acts on its own observation."""
        c = self.cluster
        if is_global(self.policy):
            j = self.policy.assign(c, req)
            return (ACCEPT if j is not None else REJECT), j
        mask = c.mask(i, req)
        if not mask.any():
            return REJECT, None
        obs = c.observation(i, req, now)
        if hasattr(self.policy, "act_agent"):
            a = int(self.policy.act_agent(i, obs, mask))
        else:
            a = int(self.policy.act(obs, mask))
        if not mask[a]:  # a policy must respect the mask; fall back rather than fail a request
            a = int(np.flatnonzero(mask)[0])
        return a, None

    async def handle(
        self, req, prompt, n_predict: int, cache_prompt: bool = True, ignore_eos: bool = False
    ) -> Outcome:
        c = self.cluster
        now = self.now()
        req.arrival = now
        holder = int(self.rng.integers(c.n))
        req.holder = holder
        self.events.emit(
            "arrive", t=now, req=req.id, entry=holder, p=req.prompt_tokens, o=req.output_tokens
        )
        actions: list = []
        while True:
            now = self.now()
            c.refresh(now)
            a, target = self._decide(holder, req, now)
            actions.append(a)
            self.events.emit("act", t=now, agent=holder, req=req.id, action=a)
            if a == REJECT:
                return self._drop(req, now, actions)
            if a == ACCEPT:
                return await self._serve(
                    req,
                    target if target is not None else holder,
                    prompt,
                    n_predict,
                    cache_prompt,
                    actions,
                    ignore_eos,
                )
            if a == FORWARD:
                dst = forward_target(c.servers, c.neighbours(holder), req)
                req.hops += 1
                self.events.emit("forward", t=now, req=req.id, src=holder, dst=dst)
                holder, req.holder = dst, dst
            elif a == DEFER:
                req.defers += 1
            await asyncio.sleep(self.dt)  # one decision tick before the next decision

    def _drop(self, req, now: float, actions: list, status: str = "dropped") -> Outcome:
        req.status, req.t_done = "dropped", now
        self.resolved.append(req)
        self.events.emit(
            "resolve",
            t=now,
            req=req.id,
            status="dropped",
            ok=False,
            server=None,
            ttft=None,
            cost=None,
        )
        return Outcome(req, status, None, None, actions)

    async def _serve(
        self, req, j: int, prompt, n_predict, cache_prompt, actions, ignore_eos=False
    ) -> Outcome:
        sh, t0 = self.cluster.servers[j], self.t0
        req.output_tokens = (
            n_predict  # the budget sent to the backend, as the simulator's output length
        )
        conc = {"n": 1}
        sh.dispatch(req, self.now())

        def first(t: float) -> None:
            conc["n"] = sh.first_token(req, t - t0)

        try:
            comp = await self.client.complete(
                self.backends[j].url,
                prompt,
                n_predict,
                cache_prompt,
                on_first=first,
                on_token=lambda n, t: sh.token(req, t - t0),
                ignore_eos=ignore_eos,
            )
        except Exception:  # noqa: BLE001 - a backend failure must not take the router down
            sh.abort(req, self.now())
            return self._drop(req, self.now(), actions, status="error")
        req.output_tokens = comp.n_tokens
        req.t_first = comp.t_first - t0
        sh.finish(req, comp.t_done - t0, comp.timings.get("prompt_ms"))
        req.attributed_s = (comp.t_done - t0 - req.t_enqueue) / max(conc["n"], 1)
        cost = sh.price * req.attributed_s
        self.resolved.append(req)
        self.events.emit(
            "resolve",
            t=req.t_done,
            req=req.id,
            status="done",
            ok=req.sla_met(),
            server=j,
            ttft=req.ttft,
            cost=cost,
            n_tokens=comp.n_tokens,
            t_first=req.t_first,
            # the server's own timings: prompt and decode time, for calibration under load
            srv_prompt_ms=comp.timings.get("prompt_ms"),
            srv_prompt_n=comp.timings.get("prompt_n"),
            srv_predicted_ms=comp.timings.get("predicted_ms"),
        )
        return Outcome(req, "done", j, comp, actions, cost)
