"""Trace loaders: schema, parsing, nulls, failures, validation. Fixtures only, never data/raw."""

from pathlib import Path

import pandas as pd
import pytest

from marl_lb.data.traces import CANONICAL_COLUMNS, load_azure_2023, load_burstgpt, sample_stream

FIXTURES = Path(__file__).parent / "fixtures"
AZURE = FIXTURES / "azure_conv_sample.csv"
BG1 = FIXTURES / "burstgpt_1_sample.csv"
BG3 = FIXTURES / "burstgpt_3_sample.csv"

ALL_FIXTURES = [(load_azure_2023, AZURE), (load_burstgpt, BG1), (load_burstgpt, BG3)]
ALL_IDS = ["azure", "burstgpt_1", "burstgpt_3"]


def write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text)
    return path


@pytest.mark.parametrize(("loader", "path"), ALL_FIXTURES, ids=ALL_IDS)
def test_schema_and_dtypes(loader, path):
    df = loader(path)
    assert list(df.columns[: len(CANONICAL_COLUMNS)]) == CANONICAL_COLUMNS
    assert df["arrival_s"].dtype == "float64"
    assert df["prompt_tokens"].dtype == "int64"
    assert df["output_tokens"].dtype == "int64"
    assert df["session_id"].dtype == "string"
    assert (df["source"] == path.stem).all()


def test_azure_parses_fractional_seconds():
    df = load_azure_2023(AZURE)
    # 7-digit and 2-digit fractions in the same column: row 3 is ".68" vs the first row's
    # ".6805900", so 2.0 - 0.00059 = 1.99941
    assert df["arrival_s"].tolist() == pytest.approx([0.0, 0.5, 1.99941, 60.0], abs=1e-6)
    assert df["prompt_tokens"].tolist() == [374, 396, 1234, 50]
    assert df["output_tokens"].tolist() == [44, 0, 12, 7]
    assert list(df.columns) == CANONICAL_COLUMNS  # Azure has no extra columns


def test_burstgpt_shifts_first_row_to_zero():
    assert load_burstgpt(BG1)["arrival_s"].tolist() == pytest.approx([0.0, 40.0, 113.0])
    assert load_burstgpt(BG3)["arrival_s"].tolist() == pytest.approx([0.0, 2.5, 5.0, 10.0])


def test_burstgpt_keeps_extra_columns():
    df1, df3 = load_burstgpt(BG1), load_burstgpt(BG3)
    assert list(df1.columns[len(CANONICAL_COLUMNS) :]) == ["Model", "Log Type"]
    assert list(df3.columns[len(CANONICAL_COLUMNS) :]) == ["Model", "Log Type", "Elapsed time"]
    assert df1["Model"].tolist() == ["ChatGPT", "ChatGPT", "GPT-4"]
    assert df3["Elapsed time"].tolist() == pytest.approx([0.5, 1.25, 2.0, 0.1])
    assert "Total tokens" not in df3.columns


def test_session_id_null_for_azure_and_burstgpt_without_column():
    assert load_azure_2023(AZURE)["session_id"].isna().all()
    assert load_burstgpt(BG1)["session_id"].isna().all()


def test_session_id_empty_cell_is_null_and_value_kept():
    s = load_burstgpt(BG3)["session_id"]
    assert s.isna().tolist() == [True, False, False, True]
    assert s.dropna().tolist() == ["c7f2a1", "c7f2a1"]


@pytest.mark.parametrize(("loader", "path"), ALL_FIXTURES, ids=ALL_IDS)
def test_failures_counted_and_kept_by_default(loader, path):
    df = loader(path)
    assert df.attrs["n_failures"] == 1
    assert (df["output_tokens"] == 0).sum() == 1
    assert len(df) == (4 if path != BG1 else 3)


@pytest.mark.parametrize(("loader", "path"), ALL_FIXTURES, ids=ALL_IDS)
def test_drop_failures_removes_rows_but_still_reports_count(loader, path):
    kept = loader(path)
    dropped = loader(path, drop_failures=True)
    assert len(dropped) == len(kept) - 1
    assert (dropped["output_tokens"] > 0).all()
    assert dropped.attrs["n_failures"] == 1
    assert dropped.index.tolist() == list(range(len(dropped)))


def test_drop_failures_does_not_reshift_arrival_s():
    # The failure is row 2 of the Azure fixture; arrival_s stays relative to the file's first row.
    df = load_azure_2023(AZURE, drop_failures=True)
    assert df["arrival_s"].tolist() == pytest.approx([0.0, 1.99941, 60.0], abs=1e-6)


@pytest.mark.parametrize(
    ("loader", "text", "column"),
    [
        (load_azure_2023, "TIMESTAMP,ContextTokens\n2023-11-16 18:15:46.6,10\n", "GeneratedTokens"),
        (load_burstgpt, "Timestamp,Request tokens\n5,10\n", "Response tokens"),
    ],
    ids=["azure", "burstgpt"],
)
def test_missing_column_raises_naming_file_and_column(tmp_path, loader, text, column):
    path = write(tmp_path, "bad_columns.csv", text)
    with pytest.raises(ValueError, match=rf"bad_columns\.csv.*{column}"):
        loader(path)


@pytest.mark.parametrize(
    ("loader", "text"),
    [
        (
            load_azure_2023,
            "TIMESTAMP,ContextTokens,GeneratedTokens\n"
            "2023-11-16 18:15:47.0,10,1\n2023-11-16 18:15:46.0,10,1\n",
        ),
        (load_burstgpt, "Timestamp,Request tokens,Response tokens\n10,10,1\n5,10,1\n"),
    ],
    ids=["azure", "burstgpt"],
)
def test_decreasing_timestamp_raises(tmp_path, loader, text):
    path = write(tmp_path, "unsorted.csv", text)
    with pytest.raises(ValueError, match=r"unsorted\.csv.*decrease"):
        loader(path)


def test_negative_tokens_raise(tmp_path):
    path = write(tmp_path, "neg.csv", "Timestamp,Request tokens,Response tokens\n1,-5,3\n")
    with pytest.raises(ValueError, match=r"neg\.csv.*negative.*prompt_tokens"):
        load_burstgpt(path)


def test_loader_never_writes_next_to_input(tmp_path):
    path = write(tmp_path, "t.csv", "Timestamp,Request tokens,Response tokens\n1,5,3\n")
    before = sorted(p.name for p in tmp_path.iterdir())
    load_burstgpt(path)
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_sample_stream_is_a_stub_until_m0_6():
    with pytest.raises(NotImplementedError):
        sample_stream(pd.DataFrame(), arrival_rate_rps=1.0, seed=0, split="train")
