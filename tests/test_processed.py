"""Normalisation constants and the train/held-out split (M0.3.1; ADR-016, ADR-017).

Synthetic frames and the Azure fixture only; never data/raw.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from marl_lb.data.processed import build_processed, fit_normalisation, normalise, time_split

AZURE_FIXTURE = Path(__file__).parent / "fixtures" / "azure_conv_sample.csv"
FEATURES = ["prompt_tokens", "output_tokens"]


def frame(arrival_s, prompt=None, output=None) -> pd.DataFrame:
    """Canonical-schema frame; tokens default to 1 so only the arrival times matter."""
    n = len(arrival_s)
    return pd.DataFrame(
        {
            "arrival_s": np.asarray(arrival_s, dtype="float64"),
            "prompt_tokens": np.ones(n, dtype="int64") if prompt is None else prompt,
            "output_tokens": np.ones(n, dtype="int64") if output is None else output,
        }
    )


def write_azure_csv(path: Path, rows: list[tuple[float, int, int]]) -> Path:
    """Azure-layout CSV: seconds after 2023-11-16 18:00:00, ContextTokens, GeneratedTokens."""
    lines = ["TIMESTAMP,ContextTokens,GeneratedTokens"]
    for t, p, o in rows:
        stamp = pd.Timestamp("2023-11-16 18:00:00") + pd.Timedelta(seconds=t)
        lines.append(f"{stamp.strftime('%Y-%m-%d %H:%M:%S.%f')},{p},{o}")
    path.write_text("\n".join(lines) + "\n")
    return path


# --- normalisation constants -------------------------------------------------------------------


def test_constants_are_the_99th_percentile_per_feature():
    # 101 values 1..101: the linear-interpolation 99th percentile is exactly the 100th value.
    train = frame(range(101), prompt=np.arange(1, 102), output=np.arange(1, 102) * 10)
    consts = fit_normalisation(train, FEATURES, percentile=99)
    assert consts == pytest.approx({"prompt_tokens": 100.0, "output_tokens": 1000.0})


def test_percentile_comes_from_the_argument_not_a_constant():
    train = frame(range(101), prompt=np.arange(1, 102))
    consts = fit_normalisation(train, ["prompt_tokens"], percentile=50)
    assert consts["prompt_tokens"] == pytest.approx(51.0)  # the median of 1..101


def test_constant_of_zero_raises_naming_the_feature():
    train = frame(range(5), output=np.zeros(5, dtype="int64"))
    with pytest.raises(ValueError, match="output_tokens"):
        fit_normalisation(train, FEATURES, percentile=99)


# --- clipping to [0, 1] ------------------------------------------------------------------------


def test_normalise_scales_by_constant_and_clips_to_unit_interval():
    df = frame(range(5), prompt=np.array([0, 50, 100, 150, 10_000]))
    out = normalise(df, {"prompt_tokens": 100.0})
    assert out["prompt_tokens"].tolist() == pytest.approx([0.0, 0.5, 1.0, 1.0, 1.0])
    assert out["prompt_tokens"].between(0.0, 1.0).all()


def test_normalise_returns_only_the_fitted_features_and_keeps_the_input():
    df = frame(range(3), prompt=np.array([10, 20, 30]))
    before = df.copy()
    out = normalise(df, {"prompt_tokens": 30.0})
    assert list(out.columns) == ["prompt_tokens"]
    pd.testing.assert_frame_equal(df, before)  # the input is not modified


# --- time-ordered split ------------------------------------------------------------------------


def test_split_cuts_at_the_fraction_of_the_duration_and_reports_both_sizes():
    df = frame(range(100))  # arrival 0..99, duration 99, cut 0.8 * 99 = 79.2
    split = time_split(df, train_fraction=0.8)
    assert split.cutoff_s == pytest.approx(79.2)
    assert (split.n_train, split.n_heldout) == (80, 20)
    assert (len(split.train), len(split.heldout)) == (80, 20)


def test_split_is_time_ordered_with_no_overlap_and_loses_nothing():
    rng = np.random.default_rng(0)
    arrival = np.sort(rng.exponential(0.2, size=500).cumsum())
    df = frame(arrival)
    df["row"] = np.arange(len(df))
    split = time_split(df, train_fraction=0.8)

    assert split.train["arrival_s"].max() < split.heldout["arrival_s"].min()
    assert set(split.train["row"]).isdisjoint(split.heldout["row"])
    assert split.n_train + split.n_heldout == len(df)
    # nothing is shuffled: each part keeps the original order
    assert split.train["arrival_s"].is_monotonic_increasing
    assert split.heldout["arrival_s"].is_monotonic_increasing


def test_requests_arriving_at_the_same_instant_stay_on_one_side_of_the_cut():
    df = frame([0.0, 5.0, 5.0, 5.0, 10.0])
    split = time_split(df, train_fraction=0.5)  # cut = 5.0: train < cut <= held-out
    assert split.train["arrival_s"].tolist() == [0.0]
    assert split.heldout["arrival_s"].tolist() == [5.0, 5.0, 5.0, 10.0]


def test_split_rejects_unsorted_input_and_bad_fractions():
    with pytest.raises(ValueError, match="time order"):
        time_split(frame([3.0, 1.0, 2.0]), train_fraction=0.8)
    for bad in (0.0, 1.0, -0.2, 1.5):
        with pytest.raises(ValueError, match="train_fraction"):
            time_split(frame(range(10)), train_fraction=bad)


def test_split_rejects_an_empty_part():
    # a single burst of identical timestamps cannot be cut in time
    with pytest.raises(ValueError, match="empty"):
        time_split(frame([7.0, 7.0, 7.0]), train_fraction=0.8)


# --- end to end: failure rows, train-only constants, files --------------------------------------


def test_failure_rows_are_excluded_from_both_parts(tmp_path):
    # The Azure fixture has 4 rows, one with GeneratedTokens == 0 (ADR-017).
    summary = build_processed(
        AZURE_FIXTURE, tmp_path, train_fraction=0.8, percentile=99, features=FEATURES
    )
    train = pd.read_csv(tmp_path / "train.csv")
    heldout = pd.read_csv(tmp_path / "heldout.csv")
    assert (train["output_tokens"] > 0).all() and (heldout["output_tokens"] > 0).all()
    assert len(train) + len(heldout) == 3
    assert summary["n_failures_dropped"] == 1


def test_constants_use_the_train_part_only(tmp_path):
    # 100 requests over 99 s; the last 20 (the held-out part) have a huge prompt.
    train_rows = [(float(i), 100, 10) for i in range(80)]
    heldout_rows = [(float(i), 9_999_999, 10) for i in range(80, 100)]
    raw = write_azure_csv(tmp_path / "trace.csv", train_rows + heldout_rows)
    summary = build_processed(
        raw, tmp_path / "out", train_fraction=0.8, percentile=99, features=FEATURES
    )
    # the huge held-out values must not pull the constant up: it is fitted on train only
    assert summary["constants"]["prompt_tokens"] == pytest.approx(100.0)
    assert (summary["n_train"], summary["n_heldout"]) == (80, 20)


def test_files_are_written_and_match_the_summary(tmp_path):
    rows = [(float(i), 100 + i, 10 + i) for i in range(50)]
    raw = write_azure_csv(tmp_path / "trace.csv", rows)
    out = tmp_path / "out"
    summary = build_processed(raw, out, train_fraction=0.8, percentile=99, features=FEATURES)

    norm = json.loads((out / "normalisation.json").read_text())
    assert norm["constants"] == pytest.approx(summary["constants"])
    assert norm["percentile"] == 99
    split = json.loads((out / "split.json").read_text())
    assert (split["n_train"], split["n_heldout"]) == (summary["n_train"], summary["n_heldout"])
    assert len(pd.read_csv(out / "train.csv")) == summary["n_train"]
    assert len(pd.read_csv(out / "heldout.csv")) == summary["n_heldout"]


def test_build_never_writes_next_to_the_raw_file(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    raw = write_azure_csv(raw_dir / "trace.csv", [(float(i), 10, 5) for i in range(20)])
    before = sorted(p.name for p in raw_dir.iterdir())
    build_processed(raw, tmp_path / "out", train_fraction=0.8, percentile=99, features=FEATURES)
    assert sorted(p.name for p in raw_dir.iterdir()) == before
