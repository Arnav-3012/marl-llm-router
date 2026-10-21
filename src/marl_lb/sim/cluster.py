"""The simulated cluster: N servers, N routing agents, ticks, masks, rewards, drops. Tier A.

PettingZoo ParallelEnv shape: reset(stream) -> (obs, infos); step(actions) -> (obs, rewards,
terminations, truncations, infos), all keyed by "agent_i". Rules, in the order they are applied
(ADR-013, ADR-010, ADR-014):

* Time is discrete: tick t covers [t*dt, (t+1)*dt). Requests that arrived before the start of a tick
are
  handed to a uniformly random entry agent (seeded) at that start.
* Each agent decides on at most one request per tick: the oldest it holds. Idle agents get a zero
  observation and an all-False mask. A deferred request goes to the back of the agent's line.
* Actions: 0 Accept (the request joins the agent's own server), 1 Forward (to the visible neighbour
with the
  least expected wait + estimated service time; masked when k=0 or at the hop limit), 2 Defer
  (masked at
  the defer limit). If no action is legal the request is dropped. With reject_enabled (ADR-029) a
  fourth action, 3 Reject, is always legal: it drops the request on purpose (reward r_drop, as any
  drop), so shedding load is a decision the agent learns instead of a silent drop.
* Rewards are credited at resolution with the decision-time state. A transition (obs, mask, action,
  tick, reward, next_obs, next_mask) is complete when the request has resolved AND the agent has
  made
  its next decision (s' = that next observation, one gamma per decision). Finished transitions are
  collected with pop_transitions().
* The episode ends when all arrivals are in and the cluster is empty (a drain), or after max_drain_s
past the
  last arrival, when the remaining requests count as dropped. That is truncation, not termination.

mode="global" bypasses the agents: a GlobalPolicy.assign(cluster, request) picks the server at
arrival
(ADR-012). It defines lambda_sat and is the information-advantaged reference.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np

from marl_lb.sim.request import Request
from marl_lb.sim.server import Server

ACCEPT, FORWARD, DEFER, REJECT = 0, 1, 2, 3
OBS_DIM = 7
EPS = 1e-9


@dataclass
class SimParams:
    """Everything the cluster needs from configs/sim.yaml, as a typed record (no magic numbers in
    code).
    """

    layout: list  # class name of each server, in agent order
    dt: float
    max_hops: int
    max_defers: int
    max_queue: int
    prefix_cache_fraction: float
    ttft_target: float
    tpot_target: float
    est_output_tokens: float
    prompt_norm: (
        float  # normalisation constant for prompt tokens (data/processed/normalisation.json)
    )
    wait_scale_s: float  # an expected wait of this many seconds maps to observation value 1
    max_drain_s: float
    k: object = "full"  # neighbour visibility radius: 0 | 1 | "full"
    interference_model: str = (
        "A"  # ADR-015: A linear in busy neighbours, B fixed multiplier, C none
    )
    prefix_hit_enabled: bool = True
    r_met: float = 10.0
    r_missed: float = -10.0
    r_drop: float = -5.0
    lambda_cost: float = 0.0
    cost_scale: float = 1.0  # cost enters the reward as lambda * C / cost_scale (a unit, ADR-022)
    cost_credit: str = (
        "serving"  # "serving": only the Accept that served the request pays (ADR-014);
    )
    # "shared": every agent that acted on it pays, like R_SLA (ADR-027)
    beta_coop: float = 0.0
    breach_window_ticks: int = 100
    w_kv: float = 0.0
    kv_threshold: float = 0.8
    forward_cost: float = 0.0
    defer_cost: float = 0.0
    reject_enabled: bool = False  # ADR-029: adds the always-legal Reject action (3 -> 4 actions)
    # ADR-032: {"server": i, "factor": f, "at_fraction": x} slows server i by f from fraction x of
    # the arrival window on (None: no degradation)
    degrade: dict | None = None

    @classmethod
    def from_config(cls, sim: dict, layout: list, est_output_tokens: float, prompt_norm: float):
        """Build from the nested configs/sim.yaml mapping."""
        rw, ob = sim["reward"], sim["observation"]
        return cls(
            layout=layout, dt=sim["dt"], max_hops=sim["max_hops"], max_defers=sim["max_defers"],
            max_queue=sim["max_queue"], prefix_cache_fraction=sim["prefix_cache_fraction"],
            ttft_target=sim["sla"]["ttft_target"], tpot_target=sim["sla"]["tpot_target"],
            est_output_tokens=est_output_tokens, prompt_norm=prompt_norm,
            wait_scale_s=sim["wait_scale_s"], max_drain_s=sim["max_drain_s"], k=ob["k"],
            prefix_hit_enabled=ob["prefix_hit_enabled"], r_met=rw["r_sla_met"],
            r_missed=rw["r_sla_missed"], r_drop=rw["r_drop"], lambda_cost=rw["lambda_cost"],
            cost_scale=rw.get("cost_scale", 1.0), cost_credit=rw.get("cost_credit", "serving"),
            beta_coop=rw["beta_coop"], breach_window_ticks=rw["breach_window_ticks"],
            w_kv=rw["w_kv"], kv_threshold=rw["kv_threshold"], forward_cost=rw["forward_cost"],
            defer_cost=rw["defer_cost"], reject_enabled=sim.get("reject_enabled", False),
        )  # fmt: skip


@dataclass(slots=True)
class Decision:
    """One agent decision waiting for its reward (at resolution) and its next observation."""

    agent: int
    req_id: int
    obs: np.ndarray
    mask: np.ndarray
    action: int
    tick: int
    reward: float = 0.0
    final: bool = False  # the request has resolved, reward complete
    next_obs: np.ndarray | None = None
    next_mask: np.ndarray | None = None
    serving: bool = False  # the Accept that put the request on a server (pays cost and KV term)
    emitted: bool = False


@dataclass(slots=True)
class Transition:
    """ADR-010 transition record."""

    agent: int
    obs: np.ndarray
    mask: np.ndarray
    action: int
    tick: int
    reward: float
    next_obs: np.ndarray
    next_mask: np.ndarray
    truncated: bool = False


def slice_stream(stream: list, start_s: float, length_s: float) -> list:
    """Requests with arrival in [start_s, start_s + length_s), re-zeroed to start at 0 (training
    windows).
    """
    from dataclasses import replace

    return [
        replace(s, arrival_s=s.arrival_s - start_s)
        for s in stream
        if start_s <= s.arrival_s < start_s + length_s
    ]


@dataclass
class _Run:
    """Per-episode state, rebuilt by reset()."""

    requests: list = field(default_factory=list)
    next_idx: int = 0
    tick: int = 0
    t: float = 0.0
    held: list = field(default_factory=list)
    deciding: dict = field(default_factory=dict)
    cur_obs: dict = field(default_factory=dict)
    cur_mask: dict = field(default_factory=dict)
    last_decision: list = field(default_factory=list)
    done_transitions: list = field(default_factory=list)
    resolved: list = field(default_factory=list)
    breaches: deque = field(default_factory=deque)
    in_system: int = 0
    l_integral: float = 0.0
    arrival_end: float = 0.0
    finished: bool = False
    decisions_made: int = 0
    discarded_end: int = 0
    drops_unacted: int = 0
    rejected: int = 0  # requests dropped by an explicit Reject action (ADR-029)
    drops_by_holder: list = field(default_factory=list)
    events: list = field(default_factory=list)


def neighbour_ids(k, n: int, i: int) -> list:
    """Servers agent i can see: none (k=0), all others (k="full") or a ring radius (ADR-013)."""
    if k == 0:
        return []
    if k == "full":
        return [j for j in range(n) if j != i]
    ring = {(i + d) % n for d in range(1, int(k) + 1)} | {(i - d) % n for d in range(1, int(k) + 1)}
    return sorted(ring - {i})


def legal_mask(p: SimParams, servers: list, i: int, nb: list, req) -> np.ndarray:
    """Which of Accept / Forward / Defer (/ Reject) agent i may choose for `req` (ADR-013)."""
    legal = [
        servers[i].can_accept(req),
        bool(nb) and req.hops < p.max_hops,
        req.defers < p.max_defers,
    ]
    if p.reject_enabled:
        legal.append(True)  # Reject is always available (ADR-029)
    return np.array(legal, dtype=bool)


def observation_vector(
    p: SimParams, servers: list, i: int, nb: list, req, now: float
) -> np.ndarray:
    """The 7-float observation of agent i for `req` at time `now`. Used by the simulator and by the
    live router, so both build it with the same code.
    """
    s = servers[i]
    wait = s.expected_wait()
    slack_s = req.ttft_target - (now - req.arrival) - wait - s.prefill_seconds(req)
    nb_wait = (
        np.mean([min(servers[j].expected_wait() / p.wait_scale_s, 1.0) for j in nb]) if nb else 0.0
    )
    hit = s.cache.hit_tokens(req) / req.prompt_tokens if p.prefix_hit_enabled else 0.0
    return np.array(
        [
            min(wait / p.wait_scale_s, 1.0),
            s.kv_fullness(),
            min(req.prompt_tokens / p.prompt_norm, 1.0),
            float(np.clip(slack_s / req.ttft_target, 0.0, 1.0)),
            req.hops / p.max_hops,
            nb_wait,
            hit,
        ],
        dtype=np.float32,
    )


def forward_target(servers: list, nb: list, req) -> int:
    """Visible neighbour minimising expected wait + estimated service time; ties to the lowest
    index (ADR-013).
    """
    open_ = [j for j in nb if servers[j].can_accept(req)] or nb
    return min(
        open_, key=lambda j: (servers[j].expected_wait() + servers[j].est_service_seconds(req), j)
    )


class Cluster:
    def __init__(self, params: SimParams, classes: dict, mode: str = "agents",
                 global_policy=None, record_events: bool = False):  # fmt: skip
        if mode not in ("agents", "global"):
            raise ValueError("mode must be 'agents' or 'global'")
        if mode == "global" and global_policy is None:
            raise ValueError("mode='global' needs a global_policy")
        self.p, self.classes, self.mode = params, classes, mode
        self.global_policy, self.record = global_policy, record_events
        self.n = len(params.layout)
        self.n_actions = 4 if params.reject_enabled else 3
        self.agents = [f"agent_{i}" for i in range(self.n)]
        self.possible_agents = list(self.agents)
        self.servers: list[Server] = []
        self.load_scale = 1.0  # ADR-038: multiplier of the calibrated load terms, set per episode
        self.run = _Run()

    # ---- neighbourhood --------------------------------------------------------------------------
    def neighbours(self, i: int) -> list:
        return neighbour_ids(self.p.k, self.n, i)

    # ---- episode --------------------------------------------------------------------------------
    def reset(self, stream: list, seed: int = 0):
        self.rng = np.random.default_rng(seed)
        sim = {"max_queue": self.p.max_queue, "prefix_cache_fraction": self.p.prefix_cache_fraction}
        self.servers = [
            Server(i, name, self.classes[name], sim, self.p.est_output_tokens)
            for i, name in enumerate(self.p.layout)
        ]
        if self.load_scale != 1.0:
            for srv in self.servers:
                srv.set_load_scale(self.load_scale)
        r = self.run = _Run()
        r.requests = [
            Request.from_stream(i, s, self.p.ttft_target, self.p.tpot_target)
            for i, s in enumerate(stream)
        ]
        r.held = [deque() for _ in range(self.n)]
        r.last_decision = [None] * self.n
        r.drops_by_holder = [0] * self.n
        r.arrival_end = stream[-1].arrival_s if stream else 0.0
        self._begin_tick()
        return self._observe()

    @property
    def finished(self) -> bool:
        return self.run.finished

    def _begin_tick(self) -> None:
        """Hand over requests that have arrived, then decide who needs to decide."""
        r = self.run
        while r.next_idx < len(r.requests) and r.requests[r.next_idx].arrival <= r.t + EPS:
            req = r.requests[r.next_idx]
            r.next_idx += 1
            r.in_system += 1
            if self.mode == "agents":
                entry = int(self.rng.integers(self.n))
                req.holder, req.status = entry, "held"
                r.held[entry].append(req)
                self._log(
                    "arrive", req=req.id, entry=entry, p=req.prompt_tokens, o=req.output_tokens
                )
            else:
                self._assign_global(req)
        r.deciding.clear()
        if self.mode == "agents":
            for i in range(self.n):
                while r.held[i]:
                    req = r.held[i][0]
                    mask = self._mask(i, req)
                    if mask.any():
                        r.deciding[i] = req
                        break
                    r.held[i].popleft()  # no legal action: drop (counts against this holder)
                    req.last_holder = i
                    self._drop(req)
        self._maybe_finish()

    def _assign_global(self, req) -> None:
        j = self.global_policy.assign(self, req)
        if j is None or not self.servers[j].can_accept(req):
            self._drop(req)
            return
        self.servers[j].enqueue(req, self.run.t)
        self._log("arrive", req=req.id, entry=j, p=req.prompt_tokens, o=req.output_tokens)

    # ---- observation and masks ------------------------------------------------------------------
    def _mask(self, i: int, req) -> np.ndarray:
        return legal_mask(self.p, self.servers, i, self.neighbours(i), req)

    def _wait_norm(self, seconds: float) -> float:
        return min(seconds / self.p.wait_scale_s, 1.0)

    def _obs_vector(self, i: int, req) -> np.ndarray:
        return observation_vector(self.p, self.servers, i, self.neighbours(i), req, self.run.t)

    def _observe(self):
        """Observations for all agents; links each deciding agent's previous decision to this s'."""
        r = self.run
        obs, infos = {}, {}
        r.cur_obs.clear()
        r.cur_mask.clear()
        for i, name in enumerate(self.agents):
            if i in r.deciding:
                req = r.deciding[i]
                o, m = self._obs_vector(i, req), self._mask(i, req)
                r.cur_obs[i], r.cur_mask[i] = o, m
                prev = r.last_decision[i]
                if prev is not None and prev.next_obs is None:
                    prev.next_obs, prev.next_mask = o, m
                    self._emit(prev)
                obs[name] = o
                infos[name] = {"mask": m, "decide": True, "req_id": req.id}
            else:
                obs[name] = np.zeros(OBS_DIM, dtype=np.float32)
                infos[name] = {
                    "mask": np.zeros(self.n_actions, dtype=bool),
                    "decide": False,
                    "req_id": None,
                }
        return obs, infos

    # ---- stepping -------------------------------------------------------------------------------
    def step(self, actions: dict):
        r = self.run
        if r.finished:
            raise RuntimeError("episode finished; call reset()")
        emitted_before = len(r.done_transitions)
        for i, req in r.deciding.items():
            a = int(actions[self.agents[i]])
            if not r.cur_mask[i][a]:
                raise ValueError(f"agent_{i}: action {a} is masked")
            self._apply(i, req, a)
        self._advance_servers()
        r.tick += 1
        r.t = r.tick * self.p.dt
        self._begin_tick()
        obs, infos = self._observe()
        rewards = {name: 0.0 for name in self.agents}
        for tr in r.done_transitions[emitted_before:]:
            rewards[self.agents[tr.agent]] += tr.reward
        done = r.finished
        return (
            obs, rewards,
            {name: False for name in self.agents},
            {name: done for name in self.agents},
            infos,
        )  # fmt: skip

    def _apply(self, i: int, req, a: int) -> None:
        r = self.run
        rec = Decision(i, req.id, r.cur_obs[i], r.cur_mask[i], a, r.tick)
        rec.reward = -self.p.beta_coop * self._breach_rate()
        r.decisions_made += 1
        req.decisions.append(rec)
        r.last_decision[i] = rec
        req.last_holder = i
        r.held[i].popleft()
        if a == ACCEPT:
            rec.serving = True
            self.servers[i].enqueue(req, r.t)
        elif a == FORWARD:
            j = self._forward_target(i, req)
            rec.reward -= self.p.forward_cost
            req.hops += 1
            req.holder = j
            r.held[j].append(req)
            self._log("forward", req=req.id, src=i, dst=j)
        elif a == REJECT:
            r.rejected += 1
            self._log("act", agent=i, req=req.id, action=a)
            self._drop(req)  # credits r_drop to every decision on this request, this one included
            return
        else:
            rec.reward -= self.p.defer_cost
            req.defers += 1
            r.held[i].append(req)
        self._log("act", agent=i, req=req.id, action=a)

    def _forward_target(self, i: int, req) -> int:
        return forward_target(self.servers, self.neighbours(i), req)

    def _advance_servers(self) -> None:
        r, dt = self.run, self.p.dt
        d = self.p.degrade
        if d and r.t >= d["at_fraction"] * r.arrival_end:
            self.servers[d["server"]].slowdown = d["factor"]
        busy = [s.is_busy() for s in self.servers]
        n_busy = sum(busy)
        n_active = sum(len(s.active) for s in self.servers)
        for s, b in zip(self.servers, busy, strict=True):
            n_other = n_busy - int(b)
            # ADR-015: A scales with the number of busy neighbours; B is one fixed multiplier
            # whenever any is busy
            # (the calibration stores that multiplier as s); C has no interference term (s = 0).
            n_eff = {"A": n_other, "B": (self.n - 1) if n_other > 0 else 0, "C": 0}[
                self.p.interference_model
            ]
            # ADR-037 load terms (no effect when every g is 0): requests running on the other
            # servers of the same class (shared GPU) and of the other class
            a_same = sum(
                len(o.active) for o in self.servers if o is not s and o.class_name == s.class_name
            )
            a_diff = n_active - len(s.active) - a_same
            for req in s.advance(r.t, r.t + dt, n_eff, self.n, a_same, a_diff):
                self._resolve(req)
            s.end_of_tick(self.p.kv_threshold)
        r.l_integral += r.in_system * dt
        self._log(
            "servers",
            queue=[len(s.queue) for s in self.servers],
            active=[len(s.active) for s in self.servers],
            kv=[round(s.kv_fullness(), 3) for s in self.servers],
        )

    # ---- resolution and credit ------------------------------------------------------------------
    def _breach_rate(self) -> float:
        """Share of requests that resolved in the last W ticks and breached the SLA (or were
        dropped).
        """
        b = self.run.breaches
        while b and b[0][0] < self.run.tick - self.p.breach_window_ticks:
            b.popleft()
        return sum(x for _, x in b) / len(b) if b else 0.0

    def _credit(self, req, outcome: float, breached: bool) -> None:
        r = self.run
        r.breaches.append((r.tick, float(breached)))
        r.in_system -= 1
        r.resolved.append(req)
        for rec in req.decisions:
            rec.reward += outcome
            rec.final = True
        # ttft and cost ride on the event so the replay page computes its tiles from the log alone.
        cost = None if req.server is None else self.servers[req.server].price * req.attributed_s
        self._log(
            "resolve",
            req=req.id,
            status=req.status,
            ok=not breached,
            server=req.server,
            ttft=req.ttft,
            cost=cost,
        )

    def _resolve(self, req) -> None:
        ok = req.sla_met()
        cost = self.servers[req.server].price * req.attributed_s
        kv_frac = req.hot_ticks / req.resident_ticks if req.resident_ticks else 0.0
        cost_term = self.p.lambda_cost * cost / self.p.cost_scale
        for rec in req.decisions:
            if self.p.cost_credit == "shared":
                rec.reward -= cost_term  # no agent can avoid the cost by passing the request on
                if rec.serving:
                    rec.reward -= self.p.w_kv * kv_frac
            elif rec.serving:
                rec.reward -= cost_term + self.p.w_kv * kv_frac
        self._credit(req, self.p.r_met if ok else self.p.r_missed, not ok)
        self._emit_all(req)

    def _drop(self, req) -> None:
        r = self.run
        req.status, req.t_done = "dropped", r.t
        holder = req.last_holder if req.last_holder is not None else req.holder
        if holder is not None:
            r.drops_by_holder[holder] += 1
        if not req.decisions:
            r.drops_unacted += 1
        self._credit(req, self.p.r_drop, True)
        self._emit_all(req)

    def _emit(self, rec: Decision) -> None:
        if rec.final and rec.next_obs is not None and not rec.emitted:
            rec.emitted = True
            self.run.done_transitions.append(
                Transition(
                    rec.agent,
                    rec.obs,
                    rec.mask,
                    rec.action,
                    rec.tick,
                    rec.reward,
                    rec.next_obs,
                    rec.next_mask,
                )  # fmt: skip
            )

    def _emit_all(self, req) -> None:
        for rec in req.decisions:
            self._emit(rec)

    def pop_transitions(self) -> list:
        out, self.run.done_transitions = self.run.done_transitions, []
        return out

    # ---- end of episode -------------------------------------------------------------------------
    def _maybe_finish(self) -> None:
        r = self.run
        all_in = r.next_idx >= len(r.requests)
        if all_in and r.in_system == 0:
            r.finished = True
        elif r.t > r.arrival_end + self.p.max_drain_s:  # drain horizon: the rest counts as dropped
            for req in r.requests[: r.next_idx]:
                if req.status not in ("done", "dropped"):
                    for s in self.servers:
                        if req in s.active:
                            s.active.remove(req)
                            s.kv.release(req.id)
                        elif req in s.queue:
                            s.queue.remove(req)
                    self._drop(req)
            for q in r.held:
                q.clear()
            r.deciding.clear()
            r.finished = True
        if r.finished:
            r.discarded_end = sum(
                1 for rec in r.last_decision if rec is not None and not rec.emitted
            )

    # ---- logging --------------------------------------------------------------------------------
    def _log(self, kind: str, **kw) -> None:
        if self.record:
            self.run.events.append(
                {"tick": self.run.tick, "t": round(self.run.t, 4), "e": kind, **kw}
            )
