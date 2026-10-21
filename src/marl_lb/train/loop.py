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
import yaml

from marl_lb.agents.dqn_agent import DQNAgent, epsilon_at
from marl_lb.config import ROOT
from marl_lb.data.traces import sample_stream
from marl_lb.policies.heuristics import SEDLocal
from marl_lb.sim.cluster import Cluster, slice_stream
from marl_lb.sim.metrics import summarise
from marl_lb.utils.logging import CsvLogger


def make_agents(cfg: dict, n: int, seed: int, solo: int | None = None) -> list:
    """N independent learners; with solo=i only agent i learns (the others stay None = fixed
    policy).
    """
    return [DQNAgent(cfg, seed * 1000 + i) if solo in (None, i) else None for i in range(n)]


def load_code_trace():
    """The Azure code 2023 trace (failure rows dropped), path from configs/data.yaml (ADR-034)."""
    import yaml

    from marl_lb.data.traces import load_azure_2023

    data = yaml.safe_load((ROOT / "configs" / "data.yaml").read_text())
    name = next(s["filename"] for s in data["sources"] if s["name"] == "azure_code_2023")
    return load_azure_2023(ROOT / "data" / "raw" / name, drop_failures=True)


def load_agents(experiment: str, seed: int, n: int) -> tuple:
    """Agents of the newest results/<experiment>/*_seed<seed>/ run, and that run's config."""
    runs = sorted((ROOT / "results" / experiment).glob(f"*_seed{seed}"))
    runs = [r for r in runs if (r / "agents.pt").exists()]
    if not runs:
        raise FileNotFoundError(f"no agents.pt for seed {seed} in results/{experiment}")
    run = runs[-1]
    cfg = yaml.safe_load((run / "config.yaml").read_text())
    states = torch.load(run / "agents.pt", map_location="cpu")
    agents = []
    for i in range(n):
        agent = DQNAgent(cfg, seed * 1000 + i)
        agent.load_state_dict(states[i])
        agents.append(agent)
    return agents, cfg


def widen_output(state: dict, n_actions: int) -> dict:
    """Copy a Q-network state dict into one with more outputs (ADR-029 fine-tuning). The old
    outputs are kept; each new output starts as the MEAN of the old ones, so it is never the
    argmax at the start (a mean never exceeds the maximum) and training decides if it is better.
    """
    out = {name: w.clone() for name, w in state.items()}
    last = max(int(k.split(".")[1]) for k in state if k.endswith(".weight"))
    for kind in ("weight", "bias"):
        key = f"net.{last}.{kind}"
        old = state[key]
        extra = old.mean(dim=0, keepdim=True).expand(n_actions - old.shape[0], *old.shape[1:])
        out[key] = torch.cat([old, extra.clone()], dim=0)
    return out


def warm_start(agents: list, experiment: str, seed: int) -> None:
    """Load the weights of results/<experiment>/*_seed<seed>/agents.pt into the agents, widening
    the output layer if the new agents have more actions (optimizer and replay start fresh).
    """
    runs = [r for r in sorted((ROOT / "results" / experiment).glob(f"*_seed{seed}"))
            if (r / "agents.pt").exists()]  # fmt: skip
    if not runs:
        raise FileNotFoundError(f"no agents.pt for seed {seed} in results/{experiment}")
    saved = torch.load(runs[-1] / "agents.pt", map_location="cpu")
    for i, ag in enumerate(agents):
        if ag is None:
            continue
        n_new = ag.q.net[-1].out_features
        state = {part: widen_output(saved[i][part], n_new) for part in ("q", "target")}
        ag.load_state_dict(state)


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
    hist = np.zeros((n, cluster.n_actions), int)
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
        "act_reject": int(hist[:, 3].sum()) if hist.shape[1] > 3 else 0,
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
        key: cfg[key]
        for key in ("cost_credit", "forward_cost", "defer_cost", "reject_enabled")
        if key in cfg
    }
    cluster = world.cluster(
        k=cfg.get("k", "full"),
        lambda_cost=cfg["lambda_cost"],
        beta_coop=cfg["beta_coop"],
        **reward_opts,
    )
    agents = make_agents(cfg, cluster.n, seed, solo)
    if cfg.get("init_from"):  # fine-tune saved agents (ADR-029) instead of training from scratch
        warm_start(agents, cfg["init_from"], seed)
    fallback = SEDLocal() if solo is not None else None
    # One train stream per training load; with several loads each episode draws one of them.
    rates = cfg.get("rates_rps") or [cfg["rate_rps"]]
    streams = [world.stream(r, seed, "train") for r in rates]
    if cfg.get("mix_code"):  # ADR-034: also windows of the code trace's TRAIN part, same rates
        code = load_code_trace()
        streams += [
            sample_stream(code, r, seed, "train", train_fraction=world.train_fraction)
            for r in rates
        ]
    log = CsvLogger(log_path) if log_path else None
    for ep in range(cfg["episodes"]):
        full = streams[int(rng.integers(len(streams)))] if len(streams) > 1 else streams[0]
        span = full[-1].arrival_s - cfg["window_s"]
        start = float(rng.uniform(0, max(span, 0.0)))
        window = slice_stream(full, start, cfg["window_s"])
        if cfg.get("load_scales"):  # ADR-038: a different server slowdown each episode
            cluster.load_scale = float(rng.choice(cfg["load_scales"]))
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
