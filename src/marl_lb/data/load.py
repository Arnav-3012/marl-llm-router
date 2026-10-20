"""rho <-> arrival rate (ADR-011). Tier B.

rho = lambda_arr / lambda_sat, where lambda_sat is measured (scripts/saturation_sweep.py) and stored
in
results/saturation/lambda_sat_flat.json. This module only converts; it never invents a lambda_sat.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from marl_lb.config import ROOT

DEFAULT_PATH = ROOT / "results" / "saturation" / "lambda_sat_flat.json"


def default_path() -> Path:
    """results/<MARL_SAT_DIR or saturation>/lambda_sat_flat.json: another cluster layout has its own
    saturation rate (ADR-035), selected by the environment so that no script needs a flag.
    """
    return ROOT / "results" / os.environ.get("MARL_SAT_DIR", "saturation") / "lambda_sat_flat.json"


def load_lambda_sat(path: Path | None = None, key: str = "cache_on") -> float:
    data = json.loads(Path(path or default_path()).read_text())
    return float(data[key]["lambda_sat_rps"])


def rho_to_rate(rho: float, lambda_sat: float) -> float:
    """Arrival rate in req/s that gives load rho."""
    if rho <= 0:
        raise ValueError("rho must be positive")
    return rho * lambda_sat


def rate_to_rho(rate_rps: float, lambda_sat: float) -> float:
    return rate_rps / lambda_sat
