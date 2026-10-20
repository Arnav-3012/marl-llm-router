"""Independent Double-DQN training on simulator episodes. Tier A.

Every agent keeps its own network and replay buffer and learns only from its own finished
transitions (ADR-002, ADR-010). An episode is a window of the train stream (random start, seeded);
the cluster drains to the end. Transitions are pushed to the owning agent's buffer when their reward
(resolution) and s' (the agent's next decision) both exist.
"""

from __future__ import annotations

import time

import numpy as np
import torch

from marl_lb.agents.dqn_agent import DQNAgent, epsilon_at
from marl_lb.policies.heuristics import SEDLocal
from marl_lb.sim.cluster import Cluster, slice_stream
from marl_lb.sim.metrics import summarise
from marl_lb.utils.logging import CsvLogger


def make_agents(cfg: dict, n: int, seed: int, solo: int | None = None) -> list:
    """N independent learners; with solo=i only agent i learns (the others stay None = fixed
    policy).
    """
    return [DQNAgent(cfg, seed * 1000 + i) if solo in (None, i) else None for i in range(n)]


def agent_actions(agents: list, obs: dict, infos: dict, epsilon: float, fallback=None) -> dict:
    """Learners act epsilon-greedily on legal actions; agents that are None follow `fallback`."""
    out = {}
    for i, name in enumerate(obs):
        if not infos[name]["decide"]:
            out[name] = 0
        elif agents[i] is None:
            out[name] = int(fallback.act(obs[name], infos[name]["mask"]))
        else:
            out[name] = agents[i].act(obs[name], infos[name]["mask"], epsilon)
    return out


def run_learning_episode(
    cluster: Cluster,
    agents: list,
    stream: list,
    seed: int,
    epsilon: float,
    cfg: dict,
    learn=True,
    fallback=None,
):
    """Play one episode; learn online. Returns per-episode stats."""
    obs, infos = cluster.reset(stream, seed)
    n = len(agents)
    loss_sum, q_sum, n_updates = 0.0, 0.0, 0
    hist = np.zeros((n, 3), int)
    ret = np.zeros(n)
    ticks = 0
    while not cluster.finished:
        actions = agent_actions(agents, obs, infos, epsilon, fallback)
        for i, name in enumerate(cluster.agents):
            if infos[name]["decide"]:
                hist[i, actions[name]] += 1
        obs, _, _, _, infos = cluster.step(actions)
        for tr in cluster.pop_transitions():
            if agents[tr.agent] is not None:
                agents[tr.agent].remember(tr)
                ret[tr.agent] += tr.reward
        ticks += 1
        if learn and ticks % cfg["learn_every"] == 0:
            for ag in agents:
                if ag is not None and ag.ready():
                    for _ in range(cfg["updates_per_learn"]):
                        loss, q = ag.learn()
                        loss_sum, q_sum, n_updates = loss_sum + loss, q_sum + q, n_updates + 1
    m = summarise(cluster)
    return {
        "return_mean": float(ret[[i for i, a in enumerate(agents) if a is not None]].mean()),
        "td_loss": loss_sum / n_updates if n_updates else float("nan"),
        "mean_q": q_sum / n_updates if n_updates else float("nan"),
        "epsilon": epsilon,
        "act_accept": int(hist[:, 0].sum()),
        "act_forward": int(hist[:, 1].sum()),
        "act_defer": int(hist[:, 2].sum()),
        "goodput_rps": m["goodput_rps"],
        "sla_attainment": m["sla_attainment"],
        "drop_rate": m["drop_rate"],
        "ticks": ticks,
        "n_arrived": m["n_arrived"],
    }


def train(
    world, cfg: dict, seed: int, log_path=None, progress=None, solo: int | None = None
) -> list:
    """Train N independent DDQN agents on windows of the train stream.

    cfg: the dqn.yaml mapping plus train settings (episodes, window_s, rate_rps,
    epsilon_decay_episodes,
    learn_every, updates_per_learn). Returns the agents.
    """
    torch.set_num_threads(1)
    rng = np.random.default_rng(seed)
    reward_opts = {
        key: cfg[key] for key in ("cost_credit", "forward_cost", "defer_cost") if key in cfg
    }
    cluster = world.cluster(
        k=cfg.get("k", "full"),
        lambda_cost=cfg["lambda_cost"],
        beta_coop=cfg["beta_coop"],
        **reward_opts,
    )
    agents = make_agents(cfg, cluster.n, seed, solo)
    fallback = SEDLocal() if solo is not None else None
    # One train stream per training load; with several loads each episode draws one of them.
    rates = cfg.get("rates_rps") or [cfg["rate_rps"]]
    streams = [world.stream(r, seed, "train") for r in rates]
    log = CsvLogger(log_path) if log_path else None
    for ep in range(cfg["episodes"]):
        full = streams[int(rng.integers(len(streams)))] if len(streams) > 1 else streams[0]
        span = full[-1].arrival_s - cfg["window_s"]
        start = float(rng.uniform(0, max(span, 0.0)))
        window = slice_stream(full, start, cfg["window_s"])
        eps = epsilon_at(ep, cfg)
        t0 = time.time()
        stats = run_learning_episode(
            cluster, agents, window, seed * 100000 + ep, eps, cfg, fallback=fallback
        )
        stats["wall_s"] = time.time() - t0
        if log:
            log.log({"episode": ep, **stats})
        if progress:
            progress(ep, stats)
    return agents


def greedy_actions(agents: list, fallback=None):
    """actions function for run_episode: each learner acts greedily (epsilon = 0) on its legal
    actions.
    """

    def fn(obs, infos):
        return agent_actions(agents, obs, infos, 0.0, fallback)

    return fn
