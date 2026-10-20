"""Baseline routing policies, local and global forms (ADR-012). Tier A.

Local policies are LocalPolicy.act(obs[7], mask[3]) -> action and may use ONLY the 7 observation
features (so they have the same information as the learned agents). Global policies are
GlobalPolicy.assign(cluster, request) -> server index and see the whole cluster
(information-advantaged
references, and they define lambda_sat, ADR-011).

Observation layout (sim/cluster.py): 0 own expected wait, 1 own KV fullness, 2 prompt size, 3 slack,
4 hop count, 5 neighbour mean wait (0 if k=0), 6 prefix-hit fraction.
"""

from __future__ import annotations

import numpy as np

ACCEPT, FORWARD, DEFER = 0, 1, 2


# ---- local forms ---------------------------------------------------------------------------------
class AcceptAll:
    """Random routing: the entry rule already picks a uniformly random server (ADR-013)."""

    name = "random"

    def act(self, obs, mask):
        return ACCEPT if mask[ACCEPT] else int(np.flatnonzero(mask)[0])


class SEDLocal:
    """Approximation of SED with local information: Accept iff own wait <= neighbour mean wait.

    With k=0 the neighbour mean is 0 but Forward is masked, so it always Accepts (= entry-rule
    routing).
    """

    name = "sed_local"

    def act(self, obs, mask):
        if mask[FORWARD] and obs[0] > obs[5] or not mask[ACCEPT]:
            return FORWARD if mask[FORWARD] else int(np.flatnonzero(mask)[0])
        return ACCEPT


class CacheAwareLocal:
    """Score = overlap - w * load. Own score uses the prefix-hit feature; the neighbour has unknown
    overlap (0).

    Accept iff own_hit - w * own_wait >= 0 - w * neighbour_mean_wait.
    """

    name = "cache_aware_local"

    def __init__(self, w: float):
        self.w = w

    def act(self, obs, mask):
        own = obs[6] - self.w * obs[0]
        other = -self.w * obs[5]
        if mask[FORWARD] and own < other or not mask[ACCEPT]:
            return FORWARD if mask[FORWARD] else int(np.flatnonzero(mask)[0])
        return ACCEPT


# ---- global forms --------------------------------------------------------------------------------
def _open_servers(cluster, req) -> list:
    return [s for s in cluster.servers if s.can_accept(req)]


class RandomGlobal:
    name = "random_global"

    def __init__(self, seed: int = 0):
        self.rng = np.random.default_rng(seed)

    def assign(self, cluster, req):
        open_ = _open_servers(cluster, req)
        return open_[int(self.rng.integers(len(open_)))].index if open_ else None


class RoundRobin:
    name = "round_robin"

    def __init__(self):
        self.next = 0

    def assign(self, cluster, req):
        for off in range(cluster.n):
            j = (self.next + off) % cluster.n
            if cluster.servers[j].can_accept(req):
                self.next = (j + 1) % cluster.n
                return j
        return None


class JSQ:
    """Join the shortest queue: fewest requests present (ties to the lowest index)."""

    name = "jsq_global"

    def assign(self, cluster, req):
        open_ = _open_servers(cluster, req)
        return min(open_, key=lambda s: (s.n_present(), s.index)).index if open_ else None


class Po2:
    """Power of two choices: sample two servers, take the one with fewer requests present."""

    name = "po2_global"

    def __init__(self, seed: int = 0):
        self.rng = np.random.default_rng(seed)

    def assign(self, cluster, req):
        open_ = _open_servers(cluster, req)
        if not open_:
            return None
        pick = [
            open_[i] for i in self.rng.choice(len(open_), size=min(2, len(open_)), replace=False)
        ]
        return min(pick, key=lambda s: (s.n_present(), s.index)).index


class SEDGlobal:
    """Shortest expected delay: minimise expected wait + this request's service time there."""

    name = "sed_global"

    def assign(self, cluster, req):
        open_ = _open_servers(cluster, req)
        if not open_:
            return None
        return min(
            open_, key=lambda s: (s.expected_wait() + s.est_service_seconds(req), s.index)
        ).index


class CacheAwareGlobal:
    """Maximise prefix overlap fraction - w * expected wait (normalised like the observation)."""

    name = "cache_aware_global"

    def __init__(self, w: float, wait_scale_s: float):
        self.w, self.scale = w, wait_scale_s

    def assign(self, cluster, req):
        open_ = _open_servers(cluster, req)
        if not open_:
            return None

        def score(s):
            overlap = s.cache.hit_tokens(req) / req.prompt_tokens
            return (-(overlap - self.w * min(s.expected_wait() / self.scale, 1.0)), s.index)

        return min(open_, key=score).index


class RouteToFast:
    """Class-aware local rule: an agent on a slow server Forwards every request to a fast neighbour,
    an agent on a fast server Accepts. Uses only the three local actions (no global view), but it
    is GIVEN which server class each agent sits on, which SED-local never sees; the learned agents
    can discover the class implicitly because each has its own network. A reference for what local
    actions can achieve (ADR-027), not a like-for-like information baseline.
    """

    name = "route_to_fast"

    def __init__(self, layout: list):
        self.slow = [not c.startswith("fast") for c in layout]

    def act_agent(self, i: int, obs, mask) -> int:
        order = (FORWARD, ACCEPT, DEFER) if self.slow[i] else (ACCEPT, DEFER, FORWARD)
        return next(a for a in order if mask[a])
