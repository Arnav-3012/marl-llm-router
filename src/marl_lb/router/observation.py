"""Live server state and the live observation. Tier A.

ShadowServer is the router's own bookkeeping of one backend, built on the simulator's Server so that
everything a decision uses (expected wait, KV fullness, prefill estimate, prefix-cache hit, whether
Accept is legal) is computed by the same code as in the simulator. Only the time evolution differs:
the real server does the work and the router just records what it sees (dispatch, first token, each
token, completion). live_observation then calls the simulator's own observation_vector, so the same
state gives the same 7 floats (tests/test_observation.py).
"""

from __future__ import annotations

import numpy as np

from marl_lb.sim.cluster import SimParams, legal_mask, neighbour_ids, observation_vector
from marl_lb.sim.server import Server


class ShadowServer(Server):
    """One backend as the router sees it.

    `queue`: dispatched, no token yet. `active`: streaming.
    """

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self._pf0: dict[int, float] = {}  # request id -> prefill estimate at dispatch
        self._held: set[int] = set()  # request ids holding KV in the shadow
        self._last: float | None = None
        self.adapt = False  # ADR-039: learn live_dec / live_pf from what the backend actually does
        self._tok_last: dict[int, float] = {}

    def _tick_busy(self, now: float) -> None:
        """Busy seconds = wall time with at least one request present (same meaning as the sim)."""
        if self._last is not None and self.n_present() > 0:
            self.busy_seconds += max(now - self._last, 0.0)
        self._last = now

    def dispatch(self, req, now: float) -> None:
        self._tick_busy(now)
        self.enqueue(req, now)
        self._pf0[req.id] = req.pf_left

    def refresh(self, now: float) -> None:
        """Prefill work left of the requests that have not produced a token yet."""
        for r in self.queue:
            r.pf_left = max(self._pf0[r.id] - (now - r.t_enqueue), 0.0)

    def first_token(self, req, now: float) -> int:
        """Move to active; returns how many requests were active (including this one)."""
        self._tick_busy(now)
        if req in self.queue:
            self.queue.remove(req)
        req.pf_left, req.status, req.t_first = 0.0, "active", now
        tokens = req.prompt_tokens + req.output_tokens
        if self.kv.can_admit(tokens):
            self.kv.admit(req.id, tokens)
            self._held.add(req.id)
        self.active.append(req)
        self._tok_last[req.id] = now
        return len(self.active)

    def token(self, req, now: float | None = None) -> None:
        req.dec_left = max(req.dec_left - 1, 0)
        if self.adapt and now is not None:
            last = self._tok_last.get(req.id)
            if last is not None:  # gap between two tokens of one request = one decode step
                nominal = self.t0 + self.k * max(len(self.active), 1)
                self._learn("live_dec", (now - last) / nominal, 0.05, 0.7, 12.0)
            self._tok_last[req.id] = now

    def _learn(self, attr: str, ratio: float, alpha: float, lo: float, hi: float) -> None:
        """Move a speed factor towards the measured ratio (exponential average, clipped)."""
        ratio = min(max(ratio, lo), hi)
        setattr(self, attr, (1 - alpha) * getattr(self, attr) + alpha * ratio)

    def finish(self, req, now: float, prompt_ms: float | None = None) -> None:
        self._tick_busy(now)
        nominal_pf = self._pf0.get(req.id, 0.0)
        if self.adapt and prompt_ms and nominal_pf > 0.1:  # the backend's own prompt time
            self._learn("live_pf", prompt_ms / 1000.0 / nominal_pf, 0.2, 0.7, 12.0)
        self._tok_last.pop(req.id, None)
        if req in self.active:
            self.active.remove(req)
        if req in self.queue:
            self.queue.remove(req)
        if req.id in self._held:
            self.kv.release(req.id)
            self._held.discard(req.id)
        self._pf0.pop(req.id, None)
        req.status, req.t_done = "done", now
        self.cache.insert(req)
        self.completed += 1

    def abort(self, req, now: float) -> None:
        """A request that failed on the backend: forget it without caching anything."""
        self._tick_busy(now)
        for line in (self.active, self.queue):
            if req in line:
                line.remove(req)
        if req.id in self._held:
            self.kv.release(req.id)
            self._held.discard(req.id)
        self._pf0.pop(req.id, None)


class LiveCluster:
    """What decisions look at: the shadow servers and the simulator's parameters."""

    def __init__(
        self, params: SimParams, classes: dict, est_output_tokens: float, adapt: bool = False
    ):
        self.p = params
        self.n = len(params.layout)
        sim = {"max_queue": params.max_queue, "prefix_cache_fraction": params.prefix_cache_fraction}
        self.servers = [
            ShadowServer(i, name, classes[name], sim, est_output_tokens)
            for i, name in enumerate(params.layout)
        ]
        for srv in self.servers:
            srv.adapt = adapt  # ADR-039: measure real speeds and correct the wait estimates

    def neighbours(self, i: int) -> list:
        return neighbour_ids(self.p.k, self.n, i)

    def refresh(self, now: float) -> None:
        for s in self.servers:
            s.refresh(now)

    def observation(self, i: int, req, now: float) -> np.ndarray:
        return observation_vector(self.p, self.servers, i, self.neighbours(i), req, now)

    def mask(self, i: int, req) -> np.ndarray:
        return legal_mask(self.p, self.servers, i, self.neighbours(i), req)
