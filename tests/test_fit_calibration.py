"""Fitting maths of profiling/fit_calibration.py on SYNTHETIC data with known parameters (M0.5.3).

Nothing here reads real profiling output: each test builds measurements from a known a, c, t0, k,
cache speedup or interference factor plus seeded noise, and checks the fit gets them back.
"""

import json

import numpy as np
import pandas as pd
import pytest
from profiling import fit_calibration as fc

RNG_SEED = 11
A, C = 0.0012, 0.05  # seconds per prompt token, fixed offset
T0, K = 0.010, 0.0015  # decode step: t0 + k * B
CACHE_SPEEDUP = 8.0  # a cached token costs a / 8
S_PREFILL, S_DECODE = 0.40, 0.25  # interference: slowdown = s * n_busy / (N - 1)
N_SERVERS = 4


def noisy(rng, values, rel=0.01):
    return values * (1 + rel * rng.standard_normal(len(values)))


def prefill_frame(a=A, c=C, quad=0.0, repeats=10, rel=0.01):
    rng = np.random.default_rng(RNG_SEED)
    p = np.repeat([100, 250, 500, 1000, 2000, 3000, 4000], repeats)
    return pd.DataFrame({"prompt_tokens": p, "repeat": np.tile(range(repeats), 7)}).assign(
        ttft_s=noisy(rng, a * p + c + quad * p.astype(float) ** 2, rel)
    )


def batch_frame(repeats=10, rel=0.01):
    rng = np.random.default_rng(RNG_SEED)
    rows = []
    for b in (1, 2, 4, 8):
        for rep in range(repeats):
            step = noisy(rng, np.array([T0 + K * b]), rel)[0]
            for i in range(b):  # bench_server repeats the run-level step time on every request row
                rows.append((b, 100, rep, i, step))
    return pd.DataFrame(
        rows,
        columns=["batch_size", "prompt_tokens", "repeat", "request", "step_time_all_active_s"],
    )


def cache_frame(repeats=10, rel=0.01):
    rng = np.random.default_rng(RNG_SEED)
    rows, new = [], 50
    for prefix in (250, 500, 1000, 2000):
        total = prefix + new
        cold = C + A * total
        warm = C + A * new + A * prefix / CACHE_SPEEDUP
        for cond, mean in (("cold", cold), ("warm", warm)):
            for rep in range(repeats):
                rows.append((prefix, new, total, cond, rep, noisy(rng, np.array([mean]), rel)[0]))
    return pd.DataFrame(
        rows,
        columns=["prefix_tokens", "new_tokens", "prompt_tokens", "condition", "repeat", "ttft_s"],
    )


def interference_frame(repeats=10, rel=0.01):
    rng = np.random.default_rng(RNG_SEED)
    rows = []
    for n in range(N_SERVERS):
        for probe, base, s in (("prefill", 1.2, S_PREFILL), ("decode", 0.02, S_DECODE)):
            mean = base * (1 + s * n / (N_SERVERS - 1))
            for rep in range(repeats):
                v = noisy(rng, np.array([mean]), rel)[0]
                rows.append(
                    (
                        n,
                        probe,
                        rep,
                        v if probe == "prefill" else np.nan,
                        v if probe == "decode" else np.nan,
                    )
                )
    return pd.DataFrame(rows, columns=["n_other_busy", "probe", "repeat", "ttft_s", "tpot_s"])


# --- prefill: a ---------------------------------------------------------------------------------


def test_prefill_fit_recovers_slope_and_offset():
    fit = fc.fit_prefill(prefill_frame())
    assert fit["a"] == pytest.approx(A, rel=0.02)
    assert fit["c"] == pytest.approx(C, rel=0.15)
    assert fit["r2"] > 0.99
    assert fit["a_se"] > 0  # parameter uncertainty is reported, not hidden


def test_prefill_residuals_have_one_entry_per_measurement_and_sum_to_about_zero():
    df = prefill_frame()
    fit = fc.fit_prefill(df)
    assert len(fit["residuals"]) == len(df)
    assert abs(np.sum(fit["residuals"])) < 1e-8  # OLS with an intercept


def test_shape_check_flags_a_curve_and_passes_a_straight_line():
    straight = fc.fit_prefill(prefill_frame())
    curved = fc.fit_prefill(prefill_frame(a=0.0005, quad=2.0e-7))  # attention-like growth with P
    assert straight["shape"]["curved"] is False
    assert curved["shape"]["curved"] is True
    assert curved["shape"]["quad_coef"] > 0  # curving UP with prompt length


# --- prefill model the simulator uses: a*P + q*P^2 through the origin ----------------------------


def test_prefill_model_recovers_a_and_q_from_curved_data_with_no_offset():
    fit = fc.fit_prefill_model(prefill_frame(a=0.0008, c=0.0, quad=2.0e-7))
    assert fit["a"] == pytest.approx(0.0008, rel=0.03)
    assert fit["q"] == pytest.approx(2.0e-7, rel=0.05)
    assert fit["max_rel_err"] < 0.05 and not fit["q_clipped_to_zero"]


def test_prefill_model_clips_a_negative_q_to_zero_and_refits_a():
    fit = fc.fit_prefill_model(prefill_frame(a=0.001, c=0.0, quad=-1.0e-8))
    assert fit["q"] == 0.0 and fit["q_clipped_to_zero"]
    assert fit["a"] == pytest.approx(0.001, rel=0.1)


def test_prefill_model_weights_relative_error_so_short_prompts_count():
    # A line with a big fixed offset: an unweighted fit would be decided by the long prompts.
    fit = fc.fit_prefill_model(prefill_frame(a=0.001, c=0.2))
    short = next(r for r in fit["by_prompt_tokens"] if r["prompt_tokens"] == 250)
    assert abs(short["rel_err"]) < 0.5  # not wildly off at 250 tokens
    assert len(fit["residuals"]) == len(fit["x"]) == 70


# --- decode: t0 and k ---------------------------------------------------------------------------


def test_decode_fit_recovers_t0_and_k():
    fit = fc.fit_decode(batch_frame())
    assert fit["t0"] == pytest.approx(T0, rel=0.05)
    assert fit["k"] == pytest.approx(K, rel=0.05)
    assert fit["r2"] > 0.98


def test_decode_fit_counts_each_run_once_not_once_per_request():
    fit = fc.fit_decode(batch_frame(repeats=10))
    assert fit["n_runs"] == 4 * 10  # 4 batch sizes x 10 repeats, not 10 * (1 + 2 + 4 + 8)


def test_decode_fit_drops_runs_with_no_all_active_window():
    df = batch_frame()
    df.loc[df["batch_size"] == 8, "step_time_all_active_s"] = np.nan
    fit = fc.fit_decode(df)
    assert fit["n_runs"] == 3 * 10
    assert fit["t0"] == pytest.approx(T0, rel=0.10)


# --- prefix cache -------------------------------------------------------------------------------


def test_cache_fit_recovers_the_per_token_speedup():
    pre = fc.fit_prefill(prefill_frame())
    fit = fc.fit_cache(cache_frame(), a=A, c=C)
    assert fit["cache_speedup"] == pytest.approx(CACHE_SPEEDUP, rel=0.25)
    assert fit["cached_token_cost_ratio"] == pytest.approx(1 / CACHE_SPEEDUP, rel=0.25)
    assert pre["a"] == pytest.approx(A, rel=0.02)  # same a feeds the cache fit in the real pipeline


def test_cache_fit_inverts_the_quadratic_prefill_model():
    # warm TTFT = a*E + q*E^2 with E = new + r*prefix and r = 1/8; q > 0 must not bias r.
    a, q, r = 0.001, 2.0e-7, 1 / CACHE_SPEEDUP
    rows = [
        (pre, 50, pre + 50, "warm", i, a * (50 + r * pre) + q * (50 + r * pre) ** 2)
        for pre in (250, 500, 1000, 2000)
        for i in range(3)
    ] + [(250, 50, 300, "cold", 0, 0.3)]
    df = pd.DataFrame(
        rows,
        columns=["prefix_tokens", "new_tokens", "prompt_tokens", "condition", "repeat", "ttft_s"],
    )
    fit = fc.fit_cache(df, a=a, c=0.0, q=q)
    assert fit["cached_token_cost_ratio"] == pytest.approx(r, rel=1e-6)


def test_cache_fit_reports_when_the_cache_did_nothing():
    df = cache_frame()
    cold = df[df.condition == "cold"]
    warm = cold.assign(condition="warm")  # warm TTFT == cold TTFT: no speedup at all
    fit = fc.fit_cache(pd.concat([cold, warm]), a=A, c=C)
    assert fit["cache_speedup"] == pytest.approx(1.0, rel=0.1)


# --- interference -------------------------------------------------------------------------------


def test_interference_fit_recovers_the_slowdown_per_busy_neighbour():
    fit = fc.fit_interference(interference_frame(), n_servers=N_SERVERS)
    assert fit["prefill"]["s"] == pytest.approx(S_PREFILL, rel=0.10)
    assert fit["decode"]["s"] == pytest.approx(S_DECODE, rel=0.10)


def test_interference_table_has_every_level_with_slowdown_relative_to_zero_busy():
    fit = fc.fit_interference(interference_frame(), n_servers=N_SERVERS)
    table = fit["prefill"]["by_level"]
    assert [row["n_other_busy"] for row in table] == [0, 1, 2, 3]
    assert table[0]["slowdown"] == pytest.approx(0.0, abs=1e-12)
    assert table[3]["slowdown"] == pytest.approx(S_PREFILL, rel=0.05)
    assert fit["prefill"]["linear_r2"] > 0.95  # option A (linear in n) describes the data


def test_interference_fit_needs_the_idle_baseline():
    df = interference_frame()
    df = df[df.n_other_busy > 0]
    with pytest.raises(ValueError, match="n_other_busy == 0"):
        fc.fit_interference(df, n_servers=N_SERVERS)


# --- whole run: CSVs in, fits out ---------------------------------------------------------------


def write_run(tmp_path):
    for cls in ("fast_expensive", "slow_cheap"):
        for name, df in (
            ("prefill", prefill_frame()),
            ("batch", batch_frame()),
            ("cache", cache_frame()),
            ("interference", interference_frame()),
        ):
            df.insert(0, "server_class", cls)
            df.to_csv(tmp_path / f"{name}_{cls}.csv", index=False)
    return tmp_path


def test_fit_run_fits_both_classes_and_writes_output_but_no_calibration_json(tmp_path):
    run = write_run(tmp_path)
    result = fc.fit_run(run, n_servers=N_SERVERS)
    assert set(result["classes"]) == {"fast_expensive", "slow_cheap"}
    for fits in result["classes"].values():
        assert fits["prefill"]["a"] == pytest.approx(A, rel=0.02)
        assert fits["prefill_model"]["a"] > 0 and fits["prefill_model"]["q"] >= 0
        assert fits["decode"]["k"] == pytest.approx(K, rel=0.05)
        assert fits["cache"]["cache_speedup"] > 1
        assert fits["interference"]["prefill"]["s"] > 0
    out = json.loads((run / "fit_output.json").read_text())
    assert out["classes"]["slow_cheap"]["prefill"]["a"] == pytest.approx(A, rel=0.02)
    assert not (run / "calibration.json").exists()  # M0.5.5 writes it, after ADR-015
    assert (run / "fit_residuals.csv").exists()


def test_fit_run_names_the_missing_file(tmp_path):
    write_run(tmp_path)
    (tmp_path / "cache_slow_cheap.csv").unlink()
    with pytest.raises(FileNotFoundError, match="cache_slow_cheap.csv"):
        fc.fit_run(tmp_path, n_servers=N_SERVERS)


def test_fit_is_deterministic():
    one = fc.fit_prefill(prefill_frame())
    two = fc.fit_prefill(prefill_frame())
    assert one["a"] == two["a"] and one["c"] == two["c"]
