"""Load Azure LLM Inference 2023 and BurstGPT traces; normalise and sample streams. Tier B.

Both loaders return one canonical schema (CANONICAL_COLUMNS) followed by the source's extra columns.
They only read the file they are given; nothing is written.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[3]
DATA_CONFIG = ROOT / "configs" / "data.yaml"
SESSIONS_CONFIG = ROOT / "configs" / "sessions.yaml"

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


# --------------------------------------------------------------------------------------------
# Seeded stream sampler (M0.6)
#
# What it does: takes the train or held-out part of the processed Azure conv trace, rescales the
# arrival times so the mean rate is the requested req/s, and layers synthetic conversations over
# the requests (ADR-009, Option B). What the seed changes: ONLY the conversation layer. Arrival
# times and token counts are the trace's own, so every seed sees the same traffic and differs in
# which requests belong to the same conversation (the part the prefix cache cares about).
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class StreamRequest:
    """One request of a sampled stream. M1.2 maps this to sim.request.Request.

    conversation_id and turn_index come from the synthetic session layer (turn_index 0 = first
    turn). history_included says that this turn re-sends the previous turn's prompt and answer, so
    up to prompt(previous) + output(previous) tokens of its prompt can be a cache hit (the cache
    in M1.6 takes the minimum with this turn's own prompt length). It is False for first turns.
    """

    arrival_s: float
    prompt_tokens: int
    output_tokens: int
    conversation_id: int
    turn_index: int
    history_included: bool


@dataclass(frozen=True)
class SessionPlan:
    """What one conversation will look like, drawn before any request is matched to it."""

    n_turns: int
    gaps_s: np.ndarray  # n_turns - 1 target think times, in simulated seconds
    history_included: np.ndarray  # n_turns - 1 flags, for turns 2, 3, ...


def load_sessions_config(path: Path = SESSIONS_CONFIG) -> dict:
    """configs/sessions.yaml as a dict (ADR-009 parameters; no value is hard-coded in code)."""
    return yaml.safe_load(Path(path).read_text())


def _turns_from_u(u: np.ndarray, sessions: dict) -> np.ndarray:
    """Inverse-CDF draw of turns per session from uniform numbers u in [0, 1].

    T = 1 with probability single_turn_share. Above that, log(T) is linear in u between the
    anchors (single_turn_share, 1), (0.5, p50), (0.9, p90), (0.99, p99), (1.0, max), and the
    result is rounded UP to an integer, so the configured p50/p90/p99 are reproduced exactly.
    """
    q = sessions["turns_per_session"]
    p1 = float(sessions["single_turn_share"])
    probs = [p1, 0.5, 0.9, 0.99, 1.0]
    values = [1.0, q["p50"], q["p90"], q["p99"], q["max"]]
    # exp(log(9)) is 9.000000000000002 and ceil would give 10: round that noise off first.
    t = np.ceil(np.round(np.exp(np.interp(u, probs, np.log(values))), 9))
    return np.where(u < p1, 1, t).astype(np.int64)


def _gap_from_u(u: np.ndarray, sessions: dict) -> np.ndarray:
    """Inverse-CDF draw of inter-turn gaps (seconds) from uniform numbers u in [0, 1].

    log(gap) is linear in u between the anchors (0, min), (0.5, p50), (0.9, p90), (0.99, p99),
    (1.0, max). Heavy right tail by construction (p99 is 600 times p50 in the config).
    """
    g = sessions["inter_turn_gap_s"]
    probs = [0.0, 0.5, 0.9, 0.99, 1.0]
    values = [g["min"], g["p50"], g["p90"], g["p99"], g["max"]]
    return np.exp(np.interp(u, probs, np.log(values)))


def session_plan(seed: int, index: int, sessions: dict) -> SessionPlan:
    """The conversation that starts at trace row `index`, as a function of (seed, index) only.

    The arrival rate is deliberately not an argument: think times are user behaviour in simulated
    seconds and are NOT compressed when arrival rates are rescaled (ADR-009). One generator per
    (seed, index) means the plan for a given row is the same at every rate.
    """
    rng = np.random.default_rng([seed, index])
    n_turns = int(_turns_from_u(rng.random(1), sessions)[0])
    gaps = _gap_from_u(rng.random(n_turns - 1), sessions)
    history = rng.random(n_turns - 1) < float(sessions["history_included_prob"])
    return SessionPlan(n_turns, gaps, history)


def _nearest_free_after(t: np.ndarray, free: np.ndarray, after: int, target: float) -> int | None:
    """Index j > `after` of an unused request whose arrival is closest to `target`, or None."""
    lo = max(after + 1, int(np.searchsorted(t, target, side="left")))
    fwd = lo
    while fwd < len(t) and not free[fwd]:
        fwd += 1
    back = lo - 1
    while back > after and not free[back]:
        back -= 1
    fwd = fwd if fwd < len(t) else None
    back = back if back > after else None
    if fwd is None or back is None:
        return fwd if back is None else back
    return back if target - t[back] <= t[fwd] - target else fwd  # tie -> the earlier request


def sample_stream(
    trace: pd.DataFrame,
    arrival_rate_rps: float,
    seed: int,
    split: str,
    *,
    train_fraction: float | None = None,
    sessions: dict | None = None,
) -> list[StreamRequest]:
    """Seeded stream at `arrival_rate_rps` req/s from the train or held-out part of `trace`.

    trace: the canonical Azure conv DataFrame after dropping failure rows (ADR-017). split picks
    the time-ordered part with processed.time_split (train_fraction defaults to the `processed`
    block of configs/data.yaml). sessions defaults to configs/sessions.yaml.

    Steps:
    1. Rescale time: shift so the first arrival is 0, then multiply every gap by one factor so that
       (n - 1) / (last - first) equals arrival_rate_rps. One factor keeps the relative burst
       structure (a burst stays a burst, a lull stays a lull); only the clock speed changes.
    2. Sessions (ADR-009): walk the requests in time order. A request not yet in a conversation
       starts one; its plan (turn count, think-time gaps, history flags) is drawn from
       session_plan(seed, row). Each later turn is the unused request, after the previous turn,
       whose arrival is nearest to previous arrival + think time. A turn whose target time falls
       after the stream ends is dropped, so conversations are cut by the window (ADR-009
       Consequences); summarise_stream() reports how much that costs.
    Same arguments give an identical list. The inputs are never modified.
    """
    if arrival_rate_rps <= 0:
        raise ValueError(f"arrival_rate_rps must be positive, got {arrival_rate_rps}")
    if split not in ("train", "heldout"):
        raise ValueError(f"split must be 'train' or 'heldout', got {split!r}")
    if (trace["output_tokens"] <= 0).any():
        raise ValueError(
            "trace contains failure rows (output_tokens == 0); drop them first (ADR-017)"
        )
    if train_fraction is None:
        train_fraction = yaml.safe_load(DATA_CONFIG.read_text())["processed"]["train_fraction"]
    if sessions is None:
        sessions = load_sessions_config()

    # Imported here because processed.py imports this module (a top-level import would be circular).
    from marl_lb.data.processed import time_split

    part = getattr(time_split(trace, train_fraction), split)
    n = len(part)
    if n < 2:
        raise ValueError(f"the {split} part has {n} request(s); need at least 2 to set a rate")
    t_raw = part["arrival_s"].to_numpy(dtype="float64")
    span = t_raw[-1] - t_raw[0]
    if span <= 0:
        raise ValueError(f"the {split} part has zero duration; cannot rescale to a rate")
    # (n - 1) gaps over `span` seconds is the native mean rate; scale so it becomes the target.
    t = (t_raw - t_raw[0]) * ((n - 1) / span / arrival_rate_rps)
    prompt = part["prompt_tokens"].to_numpy(dtype="int64")
    output = part["output_tokens"].to_numpy(dtype="int64")

    conv_id = np.full(n, -1, dtype="int64")
    turn = np.zeros(n, dtype="int64")
    history = np.zeros(n, dtype=bool)
    free = np.ones(n, dtype=bool)  # not yet part of any conversation
    next_conv = 0
    for i in range(n):
        if not free[i]:
            continue
        free[i] = False
        conv_id[i] = next_conv
        plan = session_plan(seed, i, sessions)
        prev = i
        for k in range(plan.n_turns - 1):
            target = t[prev] + plan.gaps_s[k]  # think time in simulated seconds, never rescaled
            if target > t[-1]:
                break  # the conversation continues after the stream ends
            j = _nearest_free_after(t, free, prev, target)
            if j is None:
                break
            free[j] = False
            conv_id[j], turn[j], history[j] = next_conv, k + 1, plan.history_included[k]
            prev = j
        next_conv += 1

    return [
        StreamRequest(
            float(t[i]),
            int(prompt[i]),
            int(output[i]),
            int(conv_id[i]),
            int(turn[i]),
            bool(history[i]),
        )
        for i in range(n)
    ]


def summarise_stream(stream: list[StreamRequest]) -> dict:
    """Realised session structure of a stream: how many requests are follow-up turns, and so on."""
    n_conv = len({r.conversation_id for r in stream})
    sizes = pd.Series([r.conversation_id for r in stream]).value_counts()
    return {
        "n_requests": len(stream),
        "n_conversations": n_conv,
        "follow_up_share": 1 - n_conv / len(stream),  # requests that are turn 2 or later
        "single_turn_conversation_share": float((sizes == 1).mean()),
        "max_turns": int(sizes.max()),
    }
