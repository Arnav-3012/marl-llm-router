"""Seeding: one call makes python, numpy and torch reproducible. Tier B."""

from __future__ import annotations

import random

import numpy as np


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    try:  # torch is only needed once agents exist; keep this module importable without it
        import torch

        torch.manual_seed(seed)
    except ImportError:  # pragma: no cover
        pass
