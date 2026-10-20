"""Run metrics: goodput, latency percentiles, outcomes, cost, fairness, Little's law. Tier A.

All inputs come from a finished Cluster episode. Definitions (docs/context.md Metrics):

* goodput      = requests that finished AND met both SLA targets, divided by the arrival window
                 (seconds from the first to the last arrival). Requests that finish during the drain
                 count.
* sla_attainment = SLA-met requests / arrived requests; breach_rate = 1 - attainment (late and
dropped).
* TTFT / TPOT / E2E percentiles are over completed requests only (a dropped request has none).
* cost_per_request = sum over servers of price_i * busy_seconds_i, divided by completed requests
(ADR-014).
* utilisation_i = busy_seconds_i / episode seconds; Jain's index over per-server utilisation.
* Little's law: L = time-average number of requests in the system, lambda = arrived / episode
seconds,
  W = mean time in system of the resolved requests; L should be close to lambda * W.
"""

from __future__ import annotations

import numpy as np


def percentile(values, q: float) -> float:
    return float(np.percentile(values, q)) if len(values) else float("nan")


def jain_index(x) -> float:
    """(sum x)^2 / (n * sum x^2): 1 when all equal, 1/n when one server does everything."""
    x = np.asarray(x, dtype=float)
    denom = len(x) * float((x**2).sum())
    return float(x.sum() ** 2 / denom) if denom > 0 else 1.0


def class_balance(utilisation, layout) -> dict:
    """Balance that fits servers of different speed (ADR-030), from the per-server utilisation of a
    finished run. util_fast / util_slow: mean utilisation of the servers whose class starts with
    "fast" / not; jain_fast: Jain's index over the fast servers only (do the equal servers share
    the work evenly?). The index over ALL servers calls a cluster with every server saturated
    "balanced", so it is kept as a reported metric but not read as a quality of routing.
    """
    u = np.asarray(utilisation, dtype=float)
    fast = np.array([str(c).startswith("fast") for c in layout])
    return {
        "util_fast": float(u[fast].mean()) if fast.any() else float("nan"),
        "util_slow": float(u[~fast].mean()) if (~fast).any() else float("nan"),
        "jain_fast": jain_index(u[fast]) if fast.sum() > 1 else float("nan"),
    }


def summarise(cluster) -> dict:
    """Metrics of the episode a Cluster has just played."""
    run, servers = cluster.run, cluster.servers
    reqs = run.resolved
    done = [r for r in reqs if r.status == "done"]
    n_arrived, n_done, n_dropped = len(reqs), len(done), len(reqs) - len(done)
    met = [r for r in done if r.sla_met()]
    window = max(run.arrival_end - (run.requests[0].arrival if run.requests else 0.0), 1e-9)
    episode_s = max(run.tick * cluster.p.dt, 1e-9)
    ttft = [r.ttft for r in done]
    tpot = [r.tpot for r in done if r.output_tokens > 1]
    e2e = [r.e2e for r in done]
    busy = [s.busy_seconds for s in servers]
    cost = sum(s.price * s.busy_seconds for s in servers)
    prompt_total = sum(r.prompt_tokens for r in done)
    in_system_time = sum((r.t_done if r.t_done is not None else run.t) - r.arrival for r in reqs)
    return {
        "n_arrived": n_arrived,
        "n_completed": n_done,
        "n_dropped": n_dropped,
        "n_sla_met": len(met),
        "goodput_rps": len(met) / window,
        "throughput_rps": n_done / window,
        "sla_attainment": len(met) / n_arrived if n_arrived else float("nan"),
        "breach_rate": 1 - len(met) / n_arrived if n_arrived else float("nan"),
        "drop_rate": n_dropped / n_arrived if n_arrived else float("nan"),
        "ttft_p50": percentile(ttft, 50),
        "ttft_p95": percentile(ttft, 95),
        "ttft_p99": percentile(ttft, 99),
        "tpot_p50": percentile(tpot, 50),
        "tpot_p95": percentile(tpot, 95),
        "e2e_p50": percentile(e2e, 50),
        "e2e_p95": percentile(e2e, 95),
        "cost_per_request": cost / n_done if n_done else float("nan"),
        "cache_hit_rate": sum(r.cached_tokens for r in done) / prompt_total
        if prompt_total
        else 0.0,
        "utilisation": [b / episode_s for b in busy],
        "jain_utilisation": jain_index([b / episode_s for b in busy]),
        "completed_per_server": [s.completed for s in servers],
        "completed_by_class": {
            c: sum(1 for r in done if cluster.p.layout[r.server] == c)
            for c in sorted(set(cluster.p.layout))
        },
        "little_L": run.l_integral / episode_s,
        "little_lambda_W": (n_arrived / episode_s) * (in_system_time / n_arrived)
        if n_arrived
        else float("nan"),
        "episode_s": episode_s,
        "arrival_window_s": window,
        "decisions": run.decisions_made,
        "discarded_end_transitions": run.discarded_end,
        "drops_unacted": run.drops_unacted,
        "n_rejected": run.rejected,
        "drops_by_holder": list(run.drops_by_holder),
    }
