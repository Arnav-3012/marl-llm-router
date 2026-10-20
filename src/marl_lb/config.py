"""Load YAML configs into attribute-access objects. Tier B.

`Config` wraps a nested dict so code can write cfg.sla.ttft_target instead of
cfg["sla"]["ttft_target"]. It stays a plain mapping underneath (to_dict() gives the dict back),
so it can be dumped into a run directory unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


class Config(Mapping):
    def __init__(self, data: dict):
        self._data = data

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __getattr__(self, name: str):
        try:
            value = self._data[name]
        except KeyError:
            raise AttributeError(name) from None
        return Config(value) if isinstance(value, dict) else value

    def to_dict(self) -> dict:
        return self._data


def load_config(path: Path | str) -> Config:
    """Read one YAML file. A missing file or a non-mapping top level raises ValueError."""
    path = Path(path)
    if not path.exists():
        raise ValueError(f"config file not found: {path}")
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: top level must be a mapping")
    return Config(data)
