"""One simulated llama-server: queue, batch, service time, KV and prefix cache. Tier A.

Service time of a request (docs/context.md, with the fitted cache ratio and ADR-015 interference):

    E = (P - hit) + r * hit                                  hit = prompt tokens found in the prefix
    cache
    prefill seconds = a * E + q * E^2                        q = 0 gives the plain linear model
    decode step     = (t0 + k * B)                           B = requests decoding together
    both multiplied by (1 + s * n_other_busy / (N - 1))      s differs for prefill and decode
    (ADR-015, A)

The server is a small fluid machine. Within a time window it (1) admits queued requests while a
batch
slot and KV tokens are free, (2) prefills one request at a time (decode of the others waits, like a
prompt batch in llama.cpp), (3) otherwise runs decode steps for everybody in the batch. Time
advances
exactly, not tick by tick: advance(t_start, t_end) returns the requests that finished inside it.

Cost bookkeeping (ADR-014): every second the server works is attributed to the requests it worked
for:
prefill time to its request, a decode stretch split equally over the B requests in the batch. So the
attributed seconds of all requests add up to busy_seconds.
"""

from __future__ import annotations

from collections import deque

from marl_lb.sim.kv_cache import KVCache
from marl_lb.sim.prefix_cache import PrefixCache

EPS = 1e-12


class Server:
    def __init__(self, index: int, class_name: str, cls: dict, sim: dict, est_output_tokens: float):
        self.index, self.class_name = index, class_name
        self.a, self.r = cls["a"], cls["cached_token_cost_ratio"]
        self.q = cls.get("prefill_quad", 0.0)  # attention cost: TTFT curves up with prompt length
        self.t0, self.k = cls["t0"], cls["k"]
        self.s_prefill, self.s_decode = cls["s_prefill"], cls["s_decode"]
        self.price = cls["price_per_busy_second"]
        self.max_batch = cls["max_batch"]
        self.max_queue = sim["max_queue"]
        self.kv = KVCache(cls["kv_token_budget"])
        self.cache = PrefixCache(int(sim["prefix_cache_fraction"] * cls["kv_token_budget"]))
        self.est_output_tokens = est_output_tokens
        self.queue: deque = deque()
        self.active: list = []
        self.partial = 0.0  # seconds already spent on the decode step in progress
        self.busy_seconds = 0.0
        self.completed = 0

    # ---- what the router can know -------------------------------------------------------------
    def n_present(self) -> int:
        return len(self.queue) + len(self.active)

    def is_busy(self) -> bool:
        return self.n_present() > 0

    def can_accept(self, req) -> bool:
        """Accept is legal: room in the waiting line and the request can ever fit the KV budget."""
        return (
            len(self.queue) < self.max_queue
            and req.prompt_tokens + req.output_tokens <= self.kv.budget
        )

    def kv_fullness(self) -> float:
        return self.kv.fullness()

    def _prefill_cost(self, req, hit: int) -> float:
        """Prefill seconds for `req` when `hit` of its prompt tokens are already cached here."""
        effective = (
            req.prompt_tokens - hit
        ) + self.r * hit  # a cached token costs r of a fresh one
        return self.a * effective + self.q * effective**2

    def prefill_seconds(self, req) -> float:
        return self._prefill_cost(req, self.cache.hit_tokens(req))

    def _per_token(self, extra: int = 0) -> float:
        """Server seconds per decoded token when the present requests (+extra) share steps."""
        b = max(1, min(self.max_batch, self.n_present() + extra))
        return (self.t0 + self.k * b) / b

    def expected_wait(self) -> float:
        """Seconds of work ahead of a new request: remaining prefill plus expected remaining decode.

        Uses only what a router could know: prompt sizes, tokens generated so far, and the mean
        output length (output length of a request is unknown in advance).
        """
        per_tok = self._per_token()
        work = 0.0
        for r in self.active:
            generated = r.output_tokens - r.dec_left
            work += r.pf_left + max(self.est_output_tokens - generated, 0.0) * per_tok
        for r in self.queue:
            work += r.pf_left + self.est_output_tokens * per_tok
        return work

    def est_service_seconds(self, req) -> float:
        """Estimated service time of `req` here: its prefill plus the expected decode (SED,
        ADR-013).
        """
        return self.prefill_seconds(req) + self.est_output_tokens * self._per_token(extra=1)

    # ---- taking work ----------------------------------------------------------------------------
    def enqueue(self, req, now: float) -> None:
        hit = self.cache.hit_tokens(req, touch=True)
        req.cached_tokens = hit
        req.pf_left = self._prefill_cost(req, hit)
        req.dec_left = req.output_tokens
        req.server, req.status, req.t_enqueue = self.index, "queued", now
        self.queue.append(req)

    def _admit(self) -> None:
        while self.queue and len(self.active) < self.max_batch:
            head = self.queue[0]
            tokens = head.prompt_tokens + head.output_tokens
            if not self.kv.can_admit(tokens):
                break  # first-come-first-served: a big head request blocks the line
            self.queue.popleft()
            self.kv.admit(head.id, tokens)
            head.status = "active"
            self.active.append(head)
            self.partial = 0.0  # the batch changed, so the half-done step is not carried over

    def _account(self, seconds: float, reqs: list) -> None:
        self.busy_seconds += seconds
        share = seconds / len(reqs)
        for r in reqs:
            r.attributed_s += share

    # ---- time -----------------------------------------------------------------------------------
    def advance(self, t_start: float, t_end: float, n_other_busy: int, n_servers: int) -> list:
        """Run the server from t_start to t_end; return the requests that finished."""
        scale = n_other_busy / max(n_servers - 1, 1)
        mult_pf, mult_dec = 1.0 + self.s_prefill * scale, 1.0 + self.s_decode * scale
        done: list = []
        t = t_start
        while t < t_end - EPS:
            self._admit()
            if not self.active:
                break
            pf = next((r for r in self.active if r.pf_left > 0), None)
            if pf is not None:  # prefill one request; decode of the others waits
                need = pf.pf_left * mult_pf
                seg = min(need, t_end - t)
                self._account(seg, [pf])
                pf.pf_left = 0.0 if seg >= need - EPS else pf.pf_left - seg / mult_pf
                t += seg
                self.partial = 0.0
                continue
            batch = self.active
            b = len(batch)
            step = (self.t0 + self.k * b) * mult_dec
            need_first = max(step - self.partial, 0.0)  # rest of the step in progress
            if t_end - t < need_first - EPS:  # not even this step finishes inside the window
                self._account(t_end - t, batch)
                self.partial += t_end - t
                t = t_end
                break
            fit = 1 + int((t_end - t - need_first) / step + EPS)  # whole steps that fit
            n = min(
                fit, min(r.dec_left for r in batch)
            )  # batch composition stays fixed for n steps
            seg = need_first + (n - 1) * step
            for r in batch:
                if r.t_first is None:
                    r.t_first = t + need_first  # first token = end of the first decode step
            self._account(seg, batch)
            t += seg
            self.partial = 0.0
            for r in batch:
                r.dec_left -= n
            for r in [r for r in batch if r.dec_left == 0]:
                r.t_done, r.status = t, "done"
                self.active.remove(r)
                self.kv.release(r.id)
                self.cache.insert(r)
                self.completed += 1
                done.append(r)
        return done

    def end_of_tick(self, kv_threshold: float) -> None:
        """Per-request residency counters for the KV reward term (ADR-014)."""
        hot = self.kv.fullness() > kv_threshold
        for r in self.active:
            r.resident_ticks += 1
            r.hot_ticks += int(hot)
