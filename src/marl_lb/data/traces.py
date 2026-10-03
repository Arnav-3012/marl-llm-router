"""Load Azure LLM Inference 2023 and BurstGPT traces; normalise and sample streams. Tier B.

Both loaders return one canonical schema (CANONICAL_COLUMNS) followed by the source's extra columns.
They only read the file they are given; nothing is written.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

CANONICAL_COLUMNS = ["arrival_s", "prompt_tokens", "output_tokens", "session_id", "source"]

_AZURE_REQUIRED = {"TIMESTAMP": "string", "ContextTokens": "int64", "GeneratedTokens": "int64"}
_BURSTGPT_REQUIRED = {
    "Timestamp": "float64",
    "Request tokens": "int64",
    "Response tokens": "int64",
}
# Optional columns are read only when the file has them (BurstGPT_1 has neither of the first two).
_BURSTGPT_OPTIONAL = {
    "Session ID": "string",
    "Elapsed time": "float64",
    "Model": "category",
    "Log Type": "category",
}
_BURSTGPT_EXTRAS = ["Model", "Log Type", "Elapsed time"]


def _read_csv(path: Path, required: dict[str, str], optional: dict[str, str]) -> pd.DataFrame:
    """Read only the needed columns with explicit dtypes; ValueError names the file."""
    try:
        header = pd.read_csv(path, nrows=0).columns
    except ValueError as e:  # e.g. empty file
        raise ValueError(f"{path.name}: cannot read header ({e})") from e
    missing = [c for c in required if c not in header]
    if missing:
        raise ValueError(f"{path.name}: missing required column(s) {missing}; found {list(header)}")
    dtypes = {c: d for c, d in {**required, **optional}.items() if c in header}
    try:
        df = pd.read_csv(path, usecols=list(dtypes), dtype=dtypes)
    except ValueError as e:  # bad dtype, e.g. a non-integer token count
        raise ValueError(f"{path.name}: cannot parse columns ({e})") from e
    if df.empty:
        raise ValueError(f"{path.name}: no data rows")
    return df


def _finalise(df: pd.DataFrame, name: str, drop_failures: bool) -> pd.DataFrame:
    """Validate, count failure rows (output_tokens == 0), optionally drop them."""
    if df["arrival_s"].isna().any():
        raise ValueError(f"{name}: missing or unparseable timestamp")
    if not df["arrival_s"].is_monotonic_increasing:  # pandas: True when non-decreasing
        raise ValueError(f"{name}: timestamps decrease; the file is not in time order")
    for col in ("prompt_tokens", "output_tokens"):
        if (df[col] < 0).any():
            raise ValueError(f"{name}: negative values in {col}")
    n_failures = int((df["output_tokens"] == 0).sum())  # counted before any dropping
    if drop_failures:
        df = df.loc[df["output_tokens"] > 0].reset_index(drop=True)
    df.attrs["n_failures"] = n_failures
    return df


def load_azure_2023(path: Path, drop_failures: bool = False) -> pd.DataFrame:
    """Azure LLM Inference 2023 CSV -> canonical schema.

    arrival_s is seconds from the file's first request, taken before any row is dropped.
    session_id is always null (Azure has no conversation id, ADR-009).
    """
    path = Path(path)
    raw = _read_csv(path, _AZURE_REQUIRED, {})
    try:
        # "ISO8601" accepts both "...46.68" and the 7-digit "...46.6805900" forms in the file.
        ts = pd.to_datetime(raw["TIMESTAMP"], format="ISO8601")
    except ValueError as e:
        raise ValueError(f"{path.name}: cannot parse TIMESTAMP ({e})") from e
    df = pd.DataFrame(
        {
            "arrival_s": (ts - ts.iloc[0]).dt.total_seconds(),
            "prompt_tokens": raw["ContextTokens"],
            "output_tokens": raw["GeneratedTokens"],
            "session_id": pd.Series(pd.NA, index=raw.index, dtype="string"),
            "source": path.stem,
        }
    )
    return _finalise(df, path.name, drop_failures)


def load_burstgpt(path: Path, drop_failures: bool = False) -> pd.DataFrame:
    """BurstGPT CSV (v1 or v2 layout) -> canonical schema, then Model, Log Type, Elapsed time.

    Timestamp is already in seconds; it is shifted so the first row is 0. An empty Session ID
    cell, or a file with no Session ID column, gives a null session_id. "Total tokens" is
    dropped (it is Request + Response tokens). Model and Log Type are read as category to
    keep BurstGPT_3 (about 5.3M rows) small.
    """
    path = Path(path)
    raw = _read_csv(path, _BURSTGPT_REQUIRED, _BURSTGPT_OPTIONAL)
    session = raw["Session ID"] if "Session ID" in raw else pd.Series(pd.NA, index=raw.index)
    df = pd.DataFrame(
        {
            "arrival_s": raw["Timestamp"] - raw["Timestamp"].iloc[0],
            "prompt_tokens": raw["Request tokens"],
            "output_tokens": raw["Response tokens"],
            "session_id": session.astype("string"),
            "source": path.stem,
        }
    )
    for col in _BURSTGPT_EXTRAS:
        if col in raw:
            df[col] = raw[col]
    return _finalise(df, path.name, drop_failures)


def sample_stream(trace: pd.DataFrame, arrival_rate_rps: float, seed: int, split: str) -> list:
    """Seeded stream of Request records at arrival_rate_rps req/s; split is "train" | "heldout".

    The rho -> rate conversion lives in data/load.py (ADR-011, M1.28), not here.
    Implemented in M0.6.
    """
    raise NotImplementedError("sample_stream is implemented in M0.6")
