"""Fixed-size replay buffer of ADR-010 transitions. Tier A."""

from __future__ import annotations

import numpy as np
import torch


class ReplayBuffer:
    def __init__(self, capacity: int, obs_dim: int = 7, n_actions: int = 3):
        self.capacity, self.size, self.pos = capacity, 0, 0
        self.obs = np.zeros((capacity, obs_dim), np.float32)
        self.next_obs = np.zeros((capacity, obs_dim), np.float32)
        self.mask = np.zeros((capacity, n_actions), bool)
        self.next_mask = np.zeros((capacity, n_actions), bool)
        self.action = np.zeros(capacity, np.int64)
        self.reward = np.zeros(capacity, np.float32)

    def __len__(self) -> int:
        return self.size

    def add(self, obs, mask, action, reward, next_obs, next_mask) -> None:
        i = self.pos
        self.obs[i], self.mask[i], self.action[i], self.reward[i] = obs, mask, action, reward
        self.next_obs[i], self.next_mask[i] = next_obs, next_mask
        self.pos = (i + 1) % self.capacity  # overwrite the oldest once full
        self.size = min(self.size + 1, self.capacity)

    def sample(self, batch_size: int, rng: np.random.Generator) -> dict:
        idx = rng.integers(0, self.size, size=batch_size)
        return {
            "obs": torch.from_numpy(self.obs[idx]),
            "next_obs": torch.from_numpy(self.next_obs[idx]),
            "mask": torch.from_numpy(self.mask[idx]),
            "next_mask": torch.from_numpy(self.next_mask[idx]),
            "action": torch.from_numpy(self.action[idx]),
            "reward": torch.from_numpy(self.reward[idx]),
        }
