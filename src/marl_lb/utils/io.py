"""Run directories and small file helpers. Tier B."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import yaml

from marl_lb.config import ROOT


def make_run_dir(exp: str, seed: int, config: dict, root: Path | None = None) -> Path:
    """results/<exp>/<timestamp>_seed<k>/ with the resolved config copied in (CLAUDE.md)."""
    root = Path(root) if root else ROOT / "results"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    run = root / exp / f"{stamp}_seed{seed}"
    run.mkdir(parents=True, exist_ok=False)
    data = config.to_dict() if hasattr(config, "to_dict") else config
    (run / "config.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    return run


def save_json(path: Path, obj) -> None:
    Path(path).write_text(json.dumps(obj, indent=2))
