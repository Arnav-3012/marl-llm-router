"""Double DQN agent: masked epsilon-greedy acting and the DDQN update. Tier A.

One agent per server (independent learners, ADR-002). The update, for a sampled transition
(s, a, r, s', mask'):

    a*  = argmax over LEGAL actions of Q_online(s')        the online net CHOOSES the next action
    y   = r + gamma * Q_target(s')[a*]                    the target net EVALUATES it
    loss = Huber(Q_online(s)[a], y)

Choosing with one net and evaluating with another is Double DQN: it removes the upward bias that
max over a single noisy net introduces. There is no terminal flag: an episode end is truncation, so
the target always bootstraps (ADR-010). gamma applies once per decision, not per tick.
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn.functional as F

from marl_lb.agents.networks import QNetwork, masked_argmax
from marl_lb.agents.replay_buffer import ReplayBuffer


class DQNAgent:
    def __init__(self, cfg: dict, seed: int):
        torch.manual_seed(seed)
        self.cfg = cfg
        hidden = tuple(cfg["network"]["hidden"])
        self.q = QNetwork(cfg["network"]["obs_dim"], hidden, cfg["network"]["n_actions"])
        self.target = QNetwork(cfg["network"]["obs_dim"], hidden, cfg["network"]["n_actions"])
        self.target.load_state_dict(self.q.state_dict())
        self.opt = torch.optim.Adam(self.q.parameters(), lr=cfg["lr"])
        self.buffer = ReplayBuffer(
            cfg["replay"]["capacity"], cfg["network"]["obs_dim"], cfg["network"]["n_actions"]
        )
        self.rng = np.random.default_rng(seed)
        self.learn_steps = 0

    def act(self, obs: np.ndarray, mask: np.ndarray, epsilon: float = 0.0) -> int:
        """Masked epsilon-greedy: with probability epsilon a random LEGAL action, else the best
        legal
        one.
        """
        if self.rng.random() < epsilon:
            return int(self.rng.choice(np.flatnonzero(mask)))
        with torch.no_grad():
            q = self.q(torch.from_numpy(obs)[None])
            return int(masked_argmax(q, torch.from_numpy(mask)[None])[0])

    def remember(self, tr) -> None:
        """Store a finished Transition (reward scaled so Q-values stay near 1)."""
        self.buffer.add(
            tr.obs,
            tr.mask,
            tr.action,
            tr.reward * self.cfg["reward_scale"],
            tr.next_obs,
            tr.next_mask,
        )

    def ready(self) -> bool:
        return len(self.buffer) >= max(self.cfg["replay"]["warmup"], self.cfg["batch_size"])

    def learn(self) -> tuple[float, float]:
        """One DDQN gradient step on a replay minibatch. Returns (loss, mean Q of the taken
        actions).
        """
        b = self.buffer.sample(self.cfg["batch_size"], self.rng)
        q_taken = self.q(b["obs"]).gather(1, b["action"][:, None]).squeeze(1)
        with torch.no_grad():
            best = masked_argmax(self.q(b["next_obs"]), b["next_mask"])  # online net chooses
            q_next = (
                self.target(b["next_obs"]).gather(1, best[:, None]).squeeze(1)
            )  # target net evaluates
            y = b["reward"] + self.cfg["gamma"] * q_next
        loss = F.smooth_l1_loss(q_taken, y)  # Huber
        self.opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.q.parameters(), self.cfg["grad_clip"])
        self.opt.step()
        self.learn_steps += 1
        if self.learn_steps % self.cfg["target_update"] == 0:
            self.target.load_state_dict(self.q.state_dict())
        return float(loss.item()), float(q_taken.mean().item())

    def state_dict(self) -> dict:
        return {"q": self.q.state_dict(), "target": self.target.state_dict()}

    def load_state_dict(self, state: dict) -> None:
        self.q.load_state_dict(state["q"])
        self.target.load_state_dict(state["target"])


def epsilon_at(episode: int, cfg: dict) -> float:
    """Linear decay from start to end over decay_episodes, then flat."""
    e = cfg["epsilon"]
    frac = min(episode / max(cfg["epsilon_decay_episodes"], 1), 1.0)
    return e["start"] + frac * (e["end"] - e["start"])
