"""Q-network and masked argmax. Tier A.

MLP 7 -> 64 -> 64 -> 3 with ReLU (ADR-002). Illegal actions are removed before any argmax by setting
their Q-value to a huge negative number, so they can never be chosen.
"""

from __future__ import annotations

import torch
from torch import nn

NEG_INF = -1e9


class QNetwork(nn.Module):
    def __init__(self, obs_dim: int = 7, hidden: tuple = (64, 64), n_actions: int = 3):
        super().__init__()
        layers, d = [], obs_dim
        for h in hidden:
            layers += [nn.Linear(d, h), nn.ReLU()]
            d = h
        layers.append(nn.Linear(d, n_actions))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


def masked_argmax(q: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """Best legal action per row. q: (B, A) floats; mask: (B, A) bools, True = legal."""
    return q.masked_fill(~mask, NEG_INF).argmax(dim=-1)
