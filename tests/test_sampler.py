"""Seeded stream sampler (M0.6): determinism, rate rescaling, think-time gaps, validity.

Fixtures only: the traces here are built in the test from a fixed numpy seed. The one place that
touches the repo's data folders is the no-mutation test, and it only lists them before and after.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from marl_lb.data import traces
from marl_lb.data.traces import (
    CANONICAL_COLUMNS,
    StreamRequest,
    load_sessions_config,
    sample_stream,
)

ROOT = Path(__file__).resolve().parents[1]

# Small think times so a few thousand simulated seconds hold many whole sessions. These values are
# test inputs, not project parameters (the real ones live in configs/sessions.yaml).
FAST_SESSIONS = {
    "single_turn_share": 0.3,
    "turns_per_session": {"p50": 2, "p90": 6, "p99": 12, "max": 20},
    "inter_turn_gap_s": {"min": 1, "p50": 10, "p90": 40, "p99": 100, "max": 200},
    "history_included_prob": 0.5,
}


def make_trace(n=4000, seed=7):
    """A bursty synthetic trace: a mix of short (burst) and long (lull) gaps, about 3 req/s."""
    rng = np.random.default_rng(seed)
    burst = rng.random(n) < 0.7
    gaps = np.where(burst, rng.exponential(0.05, n), rng.exponential(1.0, n))
    return pd.DataFrame(
        {
            "arrival_s": np.cumsum(gaps),
            "prompt_tokens": rng.integers(10, 2000, n),
            "output_tokens": rng.integers(1, 400, n),
            "session_id": pd.Series(pd.NA, index=range(n), dtype="string"),
            "source": "synthetic",
        }
    )[CANONICAL_COLUMNS]


TRACE = make_trace()


def stream(rate=5.0, seed=0, split="train", sessions=FAST_SESSIONS, trace=TRACE):
    return sample_stream(trace, rate, seed, split, train_fraction=0.8, sessions=sessions)


def arrivals(s):
    return np.array([r.arrival_s for r in s])


def mean_rate(s):
    a = arrivals(s)
    return (len(a) - 1) / (a[-1] - a[0])


def by_conversation(s):
    conv = {}
    for r in s:
        conv.setdefault(r.conversation_id, []).append(r)
    return conv


def test_same_seed_gives_identical_stream():
    assert stream(seed=3) == stream(seed=3)


def test_different_seeds_give_different_valid_streams():
    a, b = stream(seed=1), stream(seed=2)
    assert a != b
    assert [r.conversation_id for r in a] != [r.conversation_id for r in b]
    # Same trace rows either way: the seed only changes the session layer.
    assert [(r.arrival_s, r.prompt_tokens, r.output_tokens) for r in a] == [
        (r.arrival_s, r.prompt_tokens, r.output_tokens) for r in b
    ]


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_stream_is_valid(seed):
    s = stream(seed=seed)
    assert all(isinstance(r, StreamRequest) for r in s)
    assert np.all(np.diff(arrivals(s)) >= 0)  # time order
    assert s[0].arrival_s == 0.0  # re-zeroed
    for turns in by_conversation(s).values():
        assert [r.turn_index for r in turns] == list(range(len(turns)))  # 0, 1, 2 ... in order
        assert turns[0].history_included is False  # a first turn has no predecessor
        assert all(a.arrival_s <= b.arrival_s for a, b in zip(turns, turns[1:], strict=False))
    # Every trace row appears exactly once (nothing lost, nothing duplicated).
    part = TRACE[TRACE["arrival_s"] < TRACE["arrival_s"].iloc[0] + 0.8 * np.ptp(TRACE["arrival_s"])]
    got = sorted((r.prompt_tokens, r.output_tokens) for r in s)
    want = sorted(zip(part["prompt_tokens"], part["output_tokens"], strict=True))
    assert got == want


@pytest.mark.parametrize("rate", [0.5, 2.0, 5.0, 40.0])
def test_rescaling_hits_the_target_mean_rate(rate):
    assert mean_rate(stream(rate=rate)) == pytest.approx(rate, rel=1e-9)


def test_rescaling_keeps_the_relative_burst_structure():
    slow, fast = stream(rate=1.0), stream(rate=8.0)
    # Every gap shrinks by the same factor 8, so the shape (bursts and lulls) is unchanged.
    assert np.diff(arrivals(slow)) == pytest.approx(8.0 * np.diff(arrivals(fast)), rel=1e-9)


def test_think_time_gaps_are_not_compressed_by_rescaling():
    # Median realised gap between consecutive turns of a session, at two rates 8x apart. If the
    # gaps were rescaled with the rate they would differ by 8x; they must stay near the
    # configured median (10 s) at both rates.
    medians = []
    for rate in (1.0, 8.0):
        gaps = [
            b.arrival_s - a.arrival_s
            for turns in by_conversation(stream(rate=rate, seed=5)).values()
            for a, b in zip(turns, turns[1:], strict=False)
        ]
        assert len(gaps) > 100
        medians.append(np.median(gaps))
    assert medians[0] == pytest.approx(10.0, rel=0.35)
    assert medians[1] == pytest.approx(10.0, rel=0.35)
    assert medians[0] / medians[1] == pytest.approx(1.0, rel=0.35)


def test_session_plan_does_not_depend_on_the_arrival_rate():
    # The plan (turn count, target gaps, history flags) is a function of (seed, request index)
    # only: the arrival rate is not even an argument, so it cannot compress the gaps.
    a = traces.session_plan(seed=4, index=17, sessions=FAST_SESSIONS)
    b = traces.session_plan(seed=4, index=17, sessions=FAST_SESSIONS)
    assert a.n_turns == b.n_turns
    assert a.gaps_s.tolist() == b.gaps_s.tolist()
    assert len(a.gaps_s) == a.n_turns - 1 == len(a.history_included)


def test_quantile_functions_reproduce_the_configured_quantiles():
    cfg = load_sessions_config()
    u = np.linspace(0.0, 1.0, 200_001)
    turns = traces._turns_from_u(u, cfg)
    assert (turns == 1).mean() == pytest.approx(cfg["single_turn_share"], abs=1e-4)
    t = cfg["turns_per_session"]
    assert np.quantile(turns, 0.5) == t["p50"]
    assert np.quantile(turns, 0.9) == t["p90"]
    assert np.quantile(turns, 0.99) == t["p99"]
    assert turns.max() == t["max"]
    gaps = traces._gap_from_u(u, cfg)
    g = cfg["inter_turn_gap_s"]
    assert np.quantile(gaps, 0.5) == pytest.approx(g["p50"], rel=1e-3)
    assert np.quantile(gaps, 0.9) == pytest.approx(g["p90"], rel=1e-3)
    assert np.quantile(gaps, 0.99) == pytest.approx(g["p99"], rel=1e-3)
    assert gaps.min() == pytest.approx(g["min"]) and gaps.max() == pytest.approx(g["max"])


def test_default_sessions_come_from_the_config_file():
    s = sample_stream(TRACE, 5.0, 0, "train", train_fraction=0.8)
    assert len(s) > 0
    cfg = load_sessions_config()
    assert cfg["distribution_family"] == "piecewise_log_linear_quantile"


def test_train_and_heldout_are_disjoint_time_parts():
    train, held = stream(split="train"), stream(split="heldout")
    cut = TRACE["arrival_s"].iloc[0] + 0.8 * np.ptp(TRACE["arrival_s"])
    assert len(train) == int((TRACE["arrival_s"] < cut).sum())
    assert len(held) == int((TRACE["arrival_s"] >= cut).sum())
    assert len(train) + len(held) == len(TRACE)


def test_sampling_does_not_mutate_inputs_or_data_folders():
    def listing():
        return sorted(
            (str(p), p.stat().st_size, p.stat().st_mtime_ns)
            for d in ("data/raw", "data/processed")
            for p in (ROOT / d).rglob("*")
            if p.is_file()
        )

    before_files, before_df = listing(), TRACE.copy(deep=True)
    stream(seed=1)
    sample_stream(TRACE, 3.0, 2, "heldout", train_fraction=0.8)
    assert listing() == before_files
    pd.testing.assert_frame_equal(TRACE, before_df)


def test_realised_session_summary_counts_every_request():
    s = stream(seed=2)
    summary = traces.summarise_stream(s)
    assert summary["n_requests"] == len(s)
    assert summary["n_conversations"] == len(by_conversation(s))
    assert 0.0 <= summary["follow_up_share"] <= 1.0
    assert summary["follow_up_share"] == pytest.approx(1 - summary["n_conversations"] / len(s))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"rate": 0.0}, "arrival_rate_rps"),
        ({"rate": -1.0}, "arrival_rate_rps"),
        ({"split": "val"}, "split"),
    ],
)
def test_bad_arguments_raise(kwargs, message):
    with pytest.raises(ValueError, match=message):
        stream(**kwargs)


def test_failure_rows_are_refused():
    bad = TRACE.copy()
    bad.loc[10, "output_tokens"] = 0
    with pytest.raises(ValueError, match="failure"):
        stream(trace=bad)
