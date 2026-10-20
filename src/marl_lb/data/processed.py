"""Normalisation constants and the time-ordered train/held-out split. Tier A.

Pipeline (ADR-016, ADR-017): Azure conv 2023 -> drop failure rows -> split by time (first
train_fraction of the DURATION = train, the rest = held-out) -> fit one scale per feature on the
TRAIN part only -> write the split and the constants to data/processed/.

Why the constants use train only: the held-out part stands in for traffic the agent has never
seen. If its largest requests set the scale, information from the test traffic would leak into
the training setup. The constants are then applied unchanged to both parts.

Run it with `uv run python -m marl_lb.data.processed`; every setting comes from the `processed`
block of configs/data.yaml, none is hard-coded here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from marl_lb.data.traces import load_azure_2023

ROOT = Path(__file__).resolve().parents[3]
DATA_CONFIG = ROOT / "configs" / "data.yaml"


@dataclass(frozen=True)
class TimeSplit:
    """Result of time_split: two disjoint, time-ordered parts and the cut that separates them."""

    train: pd.DataFrame
    heldout: pd.DataFrame
    cutoff_s: float  # train: arrival_s < cutoff_s; held-out: arrival_s >= cutoff_s

    @property
    def n_train(self) -> int:
        return len(self.train)

    @property
    def n_heldout(self) -> int:
        return len(self.heldout)


def time_split(df: pd.DataFrame, train_fraction: float) -> TimeSplit:
    """Cut a time-sorted trace at train_fraction of its duration. Nothing is shuffled.

    The cut is a time threshold, not a row count, so the parts are disjoint by construction
    and requests with the same arrival time always land on the same side. Splitting by duration
    (not by count) is the rule used for the M0.3 numbers in ADR-016. arrival_s is kept as in the
    input (seconds from the file's first request); the held-out part is NOT re-zeroed.
    """
    if not 0.0 < train_fraction < 1.0:
        raise ValueError(f"train_fraction must be strictly between 0 and 1, got {train_fraction}")
    t = df["arrival_s"]
    if t.empty:
        raise ValueError("cannot split an empty trace")
    if not t.is_monotonic_increasing:  # pandas: True when non-decreasing
        raise ValueError("arrival_s is not in time order; sort the trace before splitting")

    cutoff_s = float(t.min() + train_fraction * (t.max() - t.min()))
    in_train = t < cutoff_s
    train = df.loc[in_train].reset_index(drop=True)
    heldout = df.loc[~in_train].reset_index(drop=True)
    for name, part in (("train", train), ("held-out", heldout)):
        if part.empty:
            raise ValueError(f"the {name} part is empty (cut at {cutoff_s:.3f} s)")
    return TimeSplit(train=train, heldout=heldout, cutoff_s=cutoff_s)


def fit_normalisation(
    train: pd.DataFrame, features: list[str], percentile: float
) -> dict[str, float]:
    """One scale per feature: its `percentile`-th percentile over the rows given (use TRAIN only).

    np.percentile with its default linear interpolation between ranks. A feature whose scale is
    not positive cannot be divided by, so that is an error rather than a silent NaN.
    """
    if not 0.0 < percentile <= 100.0:
        raise ValueError(f"percentile must be in (0, 100], got {percentile}")
    constants = {}
    for feature in features:
        if feature not in train:
            raise ValueError(f"feature {feature!r} is not a column of the trace")
        value = float(np.percentile(train[feature].to_numpy(), percentile))
        if not value > 0.0:
            raise ValueError(f"normalisation constant for {feature!r} is {value}; need > 0")
        constants[feature] = value
    return constants


def normalise(df: pd.DataFrame, constants: dict[str, float]) -> pd.DataFrame:
    """value / constant, clipped to [0, 1]: anything above the percentile counts as 1.

    Returns a new frame with only the fitted features (float64); df is not modified.
    """
    scaled = df[list(constants)].astype("float64") / pd.Series(constants, dtype="float64")
    return scaled.clip(lower=0.0, upper=1.0)


def build_processed(
    raw_path: Path,
    out_dir: Path,
    *,
    train_fraction: float,
    percentile: float,
    features: list[str],
) -> dict:
    """Azure trace -> failure rows dropped -> time split -> constants from train -> files.

    Writes train.csv, heldout.csv (canonical schema), normalisation.json (constants, fitted on
    train) and split.json (cut and sizes) into out_dir; raw_path is only read. Returns the same
    facts as a dict.
    """
    raw_path, out_dir = Path(raw_path), Path(out_dir)
    trace = load_azure_2023(raw_path, drop_failures=True)  # ADR-017
    n_failures_dropped = trace.attrs["n_failures"]

    split = time_split(trace, train_fraction)
    constants = fit_normalisation(split.train, features, percentile)  # train part only

    out_dir.mkdir(parents=True, exist_ok=True)
    split.train.to_csv(out_dir / "train.csv", index=False)
    split.heldout.to_csv(out_dir / "heldout.csv", index=False)
    norm = {
        "source": raw_path.stem,
        "percentile": percentile,
        "fitted_on": "train",
        "n_fit_rows": split.n_train,
        "constants": constants,
    }
    summary = {
        "source": raw_path.stem,
        "train_fraction": train_fraction,
        "cutoff_s": split.cutoff_s,
        "n_train": split.n_train,
        "n_heldout": split.n_heldout,
        "n_failures_dropped": n_failures_dropped,
        "constants": constants,
    }
    (out_dir / "normalisation.json").write_text(json.dumps(norm, indent=2) + "\n")
    split_info = {k: v for k, v in summary.items() if k != "constants"}
    (out_dir / "split.json").write_text(json.dumps(split_info, indent=2) + "\n")
    return summary


def main() -> None:
    cfg = yaml.safe_load(DATA_CONFIG.read_text())
    proc = cfg["processed"]
    summary = build_processed(
        ROOT / cfg["raw_dir"] / proc["source_file"],
        ROOT / proc["out_dir"],
        train_fraction=proc["train_fraction"],
        percentile=proc["percentile"],
        features=proc["features"],
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
