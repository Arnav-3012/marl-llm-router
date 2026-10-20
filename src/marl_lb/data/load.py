"""rho <-> arrival rate (ADR-011). Tier B.

rho = lambda_arr / lambda_sat, where lambda_sat is measured (scripts/saturation_sweep.py) and stored
in
results/saturation/lambda_sat_flat.json. This module only converts; it never invents a lambda_sat.
"""

from __future__ import annotations

import json
from pathlib import Path

from marl_lb.config import ROOT

DEFAULT_PATH = ROOT / "results" / "saturation" / "lambda_sat_flat.json"


def load_lambda_sat(path: Path = DEFAULT_PATH, key: str = "cache_on") -> float:
    data = json.loads(Path(path).read_text())
    return float(data[key]["lambda_sat_rps"])


def rho_to_rate(rho: float, lambda_sat: float) -> float:
    """Arrival rate in req/s that gives load rho."""
    if rho <= 0:
        raise ValueError("rho must be positive")
    return rho * lambda_sat


def rate_to_rho(rate_rps: float, lambda_sat: float) -> float:
    return rate_rps / lambda_sat
