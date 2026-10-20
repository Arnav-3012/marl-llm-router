"""Fit a, t0, k, cache speedup and interference from the raw profiling CSVs. Tier A.

Input: a run directory written by profiling/bench_server.py (prefill_<class>.csv, batch_<class>.csv,
cache_<class>.csv, interference_<class>.csv, optional joint_<class>.csv). Output: fit_output.json
and
fit_residuals.csv in the same directory. It does NOT write profiling/calibration.json: that is
M0.5.5, after ADR-015 says which interference model the simulator uses.

The simulator's service time is  T = a * (P - P_cached) + sum_i t_step(B_i),  t_step(B) = t0 + k * B
(docs/context.md). Each unknown has its own experiment (Deep-Dive Guide H1) and its own
least-squares
line, so every fit below is "straight line through the measurements" plus an honest look at how
well a straight line describes them (Guide H2/H6):

  prefill       TTFT = a * P + c                  one request alone, 1 output token
                (c = fixed offset: HTTP, scheduling, the decode step that makes the first token)
  decode        step = t0 + k * B                 B concurrent requests, all decoding together
  cache         warm TTFT = c + a*(new) + r*a*P_cached   a cached token costs r*a;  speedup = 1/r
  interference  value(n) = value(0) * (1 + s * n/(N-1))   n = other servers busy (ADR-015 option A)

Run:  uv run python -m profiling.fit_calibration --run results/profiling/<run dir>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_FILES = [
    "prefill",
    "batch",
    "cache",
    "interference",
]  # required per class; joint is optional

# Verdict thresholds (diagnostics only; they never change a fitted value).
R2_WARN = 0.90  # Guide H2: R^2 well below ~0.9 means a straight line is the wrong model
CURVE_T = 3.0  # |t| of the quadratic term above which a curve is called significant
CURVE_SHARE = 0.05  # ... and it must move TTFT at the largest P by more than this share of the line
MODEL_ERR_WARN = 0.15  # prefill model: max relative gap at any prompt length that earns a warning
DECODE_DEV_WARN = 0.10  # max relative gap between a batch size's mean step time and the line


# --------------------------------------------------------------------------------------------
# Least squares with uncertainty (Guide H6: normal equations, standard errors from sigma^2 (X'X)^-1)
# --------------------------------------------------------------------------------------------


def _ols(x: np.ndarray, y: np.ndarray) -> dict:
    """Solve min ||y - X theta||^2. Returns theta, standard errors, fitted, residuals, R^2."""
    n, p = x.shape
    theta, *_ = np.linalg.lstsq(x, y, rcond=None)
    fitted = x @ theta
    resid = y - fitted
    rss = float(resid @ resid)
    dof = max(n - p, 1)
    cov = (rss / dof) * np.linalg.inv(x.T @ x)  # sigma^2 (X'X)^-1
    tss = float(((y - y.mean()) ** 2).sum())
    return {
        "theta": theta,
        "se": np.sqrt(np.diag(cov)),
        "fitted": fitted,
        "resid": resid,
        "r2": 1.0 - rss / tss if tss > 0 else 1.0,
        "dof": dof,
    }


def _residual_summary(observed: np.ndarray, resid: np.ndarray) -> dict:
    return {
        "rmse": float(np.sqrt(np.mean(resid**2))),
        "mean_abs": float(np.mean(np.abs(resid))),
        "max_abs": float(np.max(np.abs(resid))),
        "max_rel": float(np.max(np.abs(resid) / np.abs(observed))),
        "mean_rel": float(np.mean(np.abs(resid) / np.abs(observed))),
    }


def _require(df: pd.DataFrame, columns: list[str], what: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{what}: missing column(s) {missing}; found {list(df.columns)}")


# --------------------------------------------------------------------------------------------
# Prefill: a
# --------------------------------------------------------------------------------------------


def fit_prefill(df: pd.DataFrame) -> dict:
    """TTFT = a * P + c. Also checks the shape: does TTFT curve up with P (attention is ~P^2)?"""
    _require(df, ["prompt_tokens", "ttft_s"], "prefill")
    p = df["prompt_tokens"].to_numpy(float)
    y = df["ttft_s"].to_numpy(float)
    fit = _ols(np.column_stack([p, np.ones_like(p)]), y)
    a, c = fit["theta"]

    # Shape check: add a P^2 term. If it is significant AND big enough to matter, the line is the
    # wrong shape (residuals would be negative in the middle and positive at both ends).
    quad = _ols(np.column_stack([p**2, p, np.ones_like(p)]), y)
    q_coef, q_se = quad["theta"][0], quad["se"][0]
    t_stat = float(q_coef / q_se) if q_se > 0 else 0.0
    line_at_max = abs(a) * p.max()
    share = float(abs(q_coef) * p.max() ** 2 / line_at_max) if line_at_max > 0 else 0.0
    curved = bool(abs(t_stat) > CURVE_T and share > CURVE_SHARE)

    by_p = (
        df.groupby("prompt_tokens")["ttft_s"]
        .agg(n="count", mean="mean", std="std")
        .reset_index()
        .to_dict("records")
    )  # spread per prompt length: shows noise growing with P (heteroscedasticity)
    return {
        "a": float(a),
        "c": float(c),
        "a_se": float(fit["se"][0]),
        "c_se": float(fit["se"][1]),
        "r2": float(fit["r2"]),
        "n": len(df),
        "residual_summary": _residual_summary(y, fit["resid"]),
        "shape": {
            "curved": curved,
            "quad_coef": float(q_coef),
            "quad_t": t_stat,
            "quad_share_of_line_at_max_P": share,
            "r2_with_quadratic": float(quad["r2"]),
        },
        "by_prompt_tokens": by_p,
        "fitted": fit["fitted"].tolist(),
        "residuals": fit["resid"].tolist(),
        "x": p.tolist(),
        "observed": y.tolist(),
    }


def fit_prefill_model(df: pd.DataFrame) -> dict:
    """The prefill model the SIMULATOR uses: TTFT = a * P + q * P^2, through the origin.

    Why not the straight line above: on real data the line has a negative offset (physically
    meaningless) because TTFT curves up with P (attention). The simulator has no per-request offset,
    so the model is fitted without one. The fit minimises RELATIVE error (weights 1/TTFT), because
    most requests are short and an unweighted fit is decided by the few 4000-token points. If the
    fitted q is negative (curving down is not attention) q is set to 0 and a is refitted.
    """
    _require(df, ["prompt_tokens", "ttft_s"], "prefill")
    p = df["prompt_tokens"].to_numpy(float)
    y = df["ttft_s"].to_numpy(float)
    w = 1.0 / y

    def solve(columns: list) -> tuple:
        x = np.column_stack(columns) * w[:, None]
        theta, *_ = np.linalg.lstsq(x, np.ones_like(y), rcond=None)
        resid = np.ones_like(y) - x @ theta
        dof = max(len(y) - len(theta), 1)
        cov = (resid @ resid) / dof * np.linalg.inv(x.T @ x)
        return theta, np.sqrt(np.diag(cov))

    theta, se = solve([p, p**2])
    q_clipped = bool(theta[1] < 0)
    if q_clipped:
        theta, se = solve([p])
        theta, se = np.array([theta[0], 0.0]), np.array([se[0], 0.0])
    a, q = float(theta[0]), float(theta[1])
    fitted = a * p + q * p**2
    rel = (y - fitted) / y
    ss_tot = float(((y - y.mean()) ** 2).sum())
    by_p = [
        {
            "prompt_tokens": int(pt),
            "mean": float(g.mean()),
            "model_ttft": float(a * pt + q * pt**2),  # not "fitted": _json_safe drops that key
            "rel_err": float((a * pt + q * pt**2) / g.mean() - 1.0),
        }
        for pt, g in df.groupby("prompt_tokens")["ttft_s"]
    ]
    return {
        "a": a,
        "q": q,
        "a_se": float(se[0]),
        "q_se": float(se[1]),
        "q_clipped_to_zero": q_clipped,
        "r2": 1.0 - float(((y - fitted) ** 2).sum()) / ss_tot if ss_tot > 0 else 1.0,
        "rel_rmse": float(np.sqrt(np.mean(rel**2))),
        "max_rel_err": float(np.max(np.abs(rel))),
        "max_rel_err_of_means": max(abs(r["rel_err"]) for r in by_p),
        "by_prompt_tokens": by_p,
        "fitted": fitted.tolist(),
        "residuals": (y - fitted).tolist(),
        "x": p.tolist(),
        "observed": y.tolist(),
    }


# --------------------------------------------------------------------------------------------
# Decode: t0 and k
# --------------------------------------------------------------------------------------------


def fit_decode(df: pd.DataFrame) -> dict:
    """step = t0 + k * B from the all-active step time of each batched run.

    bench_server writes the run-level step time on every request row of the run, so rows are
    collapsed to one value per (batch size, prompt length, repeat) before fitting; otherwise a
    batch of 8 would count 8 times.
    """
    _require(
        df, ["batch_size", "prompt_tokens", "repeat", "step_time_all_active_s"], "decode (batch)"
    )
    runs = (
        df.groupby(["batch_size", "prompt_tokens", "repeat"], as_index=False)[
            "step_time_all_active_s"
        ]
        .first()
        .dropna(subset=["step_time_all_active_s"])  # runs with no window where all requests decode
    )
    b = runs["batch_size"].to_numpy(float)
    y = runs["step_time_all_active_s"].to_numpy(float)
    fit = _ols(np.column_stack([np.ones_like(b), b]), y)
    t0, k = fit["theta"]
    means = runs.groupby("batch_size")["step_time_all_active_s"].agg(["count", "mean", "std"])
    line = t0 + k * means.index.to_numpy(float)
    dev = np.abs(means["mean"].to_numpy() - line) / means["mean"].to_numpy()
    return {
        "t0": float(t0),
        "k": float(k),
        "t0_se": float(fit["se"][0]),
        "k_se": float(fit["se"][1]),
        "r2": float(fit["r2"]),
        "n_runs": len(runs),
        "residual_summary": _residual_summary(y, fit["resid"]),
        "max_rel_dev_of_batch_means_from_line": float(dev.max()),
        "by_batch_size": means.reset_index().to_dict("records"),
        "fitted": fit["fitted"].tolist(),
        "residuals": fit["resid"].tolist(),
        "x": b.tolist(),
        "observed": y.tolist(),
    }


# --------------------------------------------------------------------------------------------
# Prefix cache: speedup
# --------------------------------------------------------------------------------------------


def fit_cache(df: pd.DataFrame, a: float, c: float, q: float = 0.0) -> dict:
    """Cost of a cached prompt token relative to a fresh one: r, and speedup = 1/r.

    Warm request = shared prefix (P_cached tokens, already in the server's cache) + `new` fresh
    tokens. The prefill model prices it as  warm TTFT = c + a*E + q*E^2  with effective tokens
    E = new + r*P_cached. Inverting the model on each warm TTFT gives that request's E, and r is the
    slope of (E - new) against P_cached, through the origin (q = 0, c from a line fit reduces to
    the old linear form). r = 1 means the cache saved nothing; r near 0 means cached tokens are
    almost free (speedup large, and then poorly determined: the output carries the standard error
    so that is visible).
    """
    _require(df, ["prefix_tokens", "new_tokens", "condition", "ttft_s"], "cache")
    warm = df[df["condition"] == "warm"]
    cold = df[df["condition"] == "cold"]
    if warm.empty or cold.empty:
        raise ValueError("cache: need both 'cold' and 'warm' rows")
    prefix = warm["prefix_tokens"].to_numpy(float)
    new = warm["new_tokens"].to_numpy(float)
    work = np.maximum(warm["ttft_s"].to_numpy(float) - c, 0.0)  # seconds of prefill work
    effective = (np.sqrt(a * a + 4 * q * work) - a) / (2 * q) if q > 0 else work / a
    x, y = prefix, effective - new
    r = float(x @ y / (x @ x))
    resid = y - r * x
    r_se = float(np.sqrt((resid @ resid) / max(len(y) - 1, 1) / (x @ x)))
    predicted = c + a * (new + r * prefix) + q * (new + r * prefix) ** 2
    seconds_resid = warm["ttft_s"].to_numpy(float) - predicted
    by_prefix = (
        df.pivot_table(index="prefix_tokens", columns="condition", values="ttft_s", aggfunc="mean")
        .assign(cold_over_warm=lambda t: t["cold"] / t["warm"])
        .reset_index()
        .to_dict("records")
    )  # model-free view: how many times faster the warm request's first token is
    return {
        "cached_token_cost_ratio": r,
        "cached_token_cost_ratio_se": r_se,
        "cache_speedup": float(1.0 / r) if r > 0 else float("inf"),
        "n_warm": len(warm),
        "residual_summary": _residual_summary(warm["ttft_s"].to_numpy(float), seconds_resid),
        "by_prefix_tokens": by_prefix,
        "warm_cache_hit_tokens_mean": (
            float(warm["srv_cache_n"].mean()) if "srv_cache_n" in warm.columns else None
        ),
    }


# --------------------------------------------------------------------------------------------
# Interference (ADR-015)
# --------------------------------------------------------------------------------------------


def _fit_interference_one(values: pd.DataFrame, n_servers: int) -> dict:
    """values has columns n_other_busy, value. Fits slowdown(n) = s * n / (N - 1)."""
    base = values.loc[values["n_other_busy"] == 0, "value"]
    if base.empty:
        raise ValueError("interference: needs rows with n_other_busy == 0 (the idle baseline)")
    base_mean = float(base.mean())
    g = values.groupby("n_other_busy")["value"].agg(["count", "mean", "std"]).reset_index()
    g["slowdown"] = g["mean"] / base_mean - 1.0
    base_se = float(base.std(ddof=1) / np.sqrt(len(base))) if len(base) > 1 else 0.0
    se_n = g["std"].fillna(0.0) / np.sqrt(g["count"])
    g["slowdown_se"] = np.sqrt((se_n / base_mean) ** 2 + (g["mean"] * base_se / base_mean**2) ** 2)

    # Option A: through the origin on x = n/(N-1), one point per measurement.
    x = values["n_other_busy"].to_numpy(float) / (n_servers - 1)
    y = values["value"].to_numpy(float) / base_mean - 1.0
    s = float(x @ y / (x @ x)) if (x @ x) > 0 else 0.0
    resid = y - s * x
    s_se = float(np.sqrt((resid @ resid) / max(len(y) - 1, 1) / (x @ x))) if (x @ x) > 0 else 0.0
    gx = g["n_other_busy"].to_numpy(float) / (n_servers - 1)
    gy = g["slowdown"].to_numpy(float)
    ss_tot = float(((gy - gy.mean()) ** 2).sum())
    linear_r2 = 1.0 - float(((gy - s * gx) ** 2).sum()) / ss_tot if ss_tot > 0 else 1.0
    busy = g[g["n_other_busy"] > 0]
    return {
        "baseline_mean": base_mean,
        "s": s,
        "s_se": s_se,
        "linear_r2": linear_r2,
        # Option B view: one multiplier whenever any other server is busy.
        "fixed_multiplier_slowdown": float(busy["slowdown"].mean()) if len(busy) else 0.0,
        "by_level": g.rename(columns={"count": "n", "std": "std_value"}).to_dict("records"),
    }


def fit_interference(df: pd.DataFrame, n_servers: int) -> dict:
    """Prefill (probe TTFT) and decode (probe TPOT) slowdown against busy neighbours."""
    _require(df, ["n_other_busy", "probe", "ttft_s", "tpot_s"], "interference")
    out = {}
    for probe, column in (("prefill", "ttft_s"), ("decode", "tpot_s")):
        sub = df[df["probe"] == probe]
        values = sub[["n_other_busy", column]].rename(columns={column: "value"}).dropna()
        out[probe] = _fit_interference_one(values, n_servers)
    out["n_servers"] = n_servers
    return out


# --------------------------------------------------------------------------------------------
# Whole run
# --------------------------------------------------------------------------------------------


def _read(run: Path, name: str, cls: str, required: bool = True) -> pd.DataFrame | None:
    path = run / f"{name}_{cls}.csv"
    if not path.exists():
        if required:
            raise FileNotFoundError(f"missing profiling file {path.name} in {run}")
        return None
    return pd.read_csv(path)


def verdicts(cls: str, fits: dict) -> list[str]:
    """Plain-language statements about whether a fit looks wrong. Diagnostics only."""
    out = []
    pre, dec = fits["prefill"], fits["decode"]
    if pre["shape"]["curved"]:
        direction = "UP" if pre["shape"]["quad_coef"] > 0 else "DOWN"
        out.append(
            f"{cls}: TTFT curves {direction} with prompt length (quadratic term t = "
            f"{pre['shape']['quad_t']:.1f}, "
            f"{100 * pre['shape']['quad_share_of_line_at_max_P']:.0f}% "
            f"of the linear term at the largest P): the straight line a*P + c is the wrong shape; "
            f"the simulator uses a*P + q*P^2 instead (max error of the per-length means "
            f"{100 * fits['prefill_model']['max_rel_err_of_means']:.0f}%)."
        )
    if fits["prefill_model"]["max_rel_err_of_means"] > MODEL_ERR_WARN:
        out.append(
            f"{cls}: even a*P + q*P^2 is off by "
            f"{100 * fits['prefill_model']['max_rel_err_of_means']:.0f}% at some prompt length."
        )
    if pre["r2"] < R2_WARN:
        out.append(
            f"{cls}: prefill R^2 = {pre['r2']:.3f} < {R2_WARN}: a straight line fits poorly."
        )
    if dec["r2"] < R2_WARN:
        out.append(f"{cls}: decode R^2 = {dec['r2']:.3f} < {R2_WARN}: a straight line fits poorly.")
    if dec["max_rel_dev_of_batch_means_from_line"] > DECODE_DEV_WARN:
        out.append(
            f"{cls}: mean step time at some batch size is "
            f"{100 * dec['max_rel_dev_of_batch_means_from_line']:.0f}% off the t0 + k*B line."
        )
    if dec["k"] <= 0:
        out.append(f"{cls}: k = {dec['k']:.2e} is not positive: batching did not slow a step.")
    for probe in ("prefill", "decode"):
        if fits["interference"][probe]["linear_r2"] < R2_WARN:
            out.append(
                f"{cls}: {probe} slowdown is not linear in the number of busy neighbours "
                f"(R^2 = {fits['interference'][probe]['linear_r2']:.2f}); ADR-015 option A "
                f"does not describe it well."
            )
    if not out:
        out.append(f"{cls}: no fit looks wrong in shape by these diagnostics.")
    return out


def _residual_rows(cls: str, name: str, fit: dict) -> list[dict]:
    return [
        {"server_class": cls, "fit": name, "x": x, "observed": o, "fitted": f, "residual": r}
        for x, o, f, r in zip(
            fit["x"], fit["observed"], fit["fitted"], fit["residuals"], strict=True
        )
    ]


def _json_safe(obj):
    """NaN and +-inf are not valid JSON: write them as null."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items() if k not in ("x", "observed", "fitted")}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, float) and not np.isfinite(obj):
        return None
    return obj


def fit_run(run: Path, n_servers: int | None = None) -> dict:
    """Fit every server class found in `run`, write fit_output.json and fit_residuals.csv."""
    run = Path(run)
    if n_servers is None:
        cfg_path = run / "config_resolved.yaml"
        cfg = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
        n_servers = sum(len(s["ports"]) for s in cfg.get("servers", {}).values()) or 4
    classes = sorted(p.stem.removeprefix("prefill_") for p in run.glob("prefill_*.csv"))
    if not classes:
        raise FileNotFoundError(f"no prefill_<class>.csv in {run}")

    result: dict = {"run_dir": str(run), "n_servers": n_servers, "classes": {}, "verdicts": []}
    residual_rows: list[dict] = []
    for cls in classes:
        data = {name: _read(run, name, cls) for name in EXPERIMENT_FILES}
        prefill = fit_prefill(data["prefill"])
        model = fit_prefill_model(data["prefill"])
        decode = fit_decode(data["batch"])
        cache = fit_cache(data["cache"], a=model["a"], c=0.0, q=model["q"])
        interference = fit_interference(data["interference"], n_servers)
        fits = {
            "prefill": prefill,
            "prefill_model": model,
            "decode": decode,
            "cache": cache,
            "interference": interference,
            # c should be about one decode step (the step that makes the first token): t0 + k.
            "offset_check": {
                "prefill_offset_c": prefill["c"],
                "t0_plus_k": decode["t0"] + decode["k"],
            },
        }
        result["classes"][cls] = fits
        result["verdicts"] += verdicts(cls, fits)
        residual_rows += (
            _residual_rows(cls, "prefill_line", prefill)
            + _residual_rows(cls, "prefill_model", model)
            + _residual_rows(cls, "decode", decode)
        )

    (run / "fit_output.json").write_text(json.dumps(_json_safe(result), indent=2))
    pd.DataFrame(residual_rows).to_csv(run / "fit_residuals.csv", index=False)
    return result


def latest_run(root: Path = ROOT / "results" / "profiling") -> Path:
    runs = sorted(p for p in root.glob("*_seed*") if not p.name.endswith("_smoke"))
    if not runs:
        raise FileNotFoundError(f"no profiling runs in {root}")
    return runs[-1]


def print_summary(result: dict) -> None:
    for cls, f in result["classes"].items():
        p, d, c, i = f["prefill"], f["decode"], f["cache"], f["interference"]
        print(f"\n== {cls}")
        print(
            f"prefill   a = {p['a']:.3e} +- {p['a_se']:.1e} s/token  c = {p['c']:.4f} s  "
            f"R2 = {p['r2']:.4f}  n = {p['n']}"
        )
        m = f["prefill_model"]
        print(
            f"prefill*  a = {m['a']:.3e} +- {m['a_se']:.1e}  q = {m['q']:.3e} +- {m['q_se']:.1e}  "
            f"(simulator model, through origin)  rel rmse = {m['rel_rmse']:.3f}  "
            f"max |rel err| of per-length means = {m['max_rel_err_of_means']:.3f}"
        )
        print(
            f"decode    t0 = {d['t0']:.4f} +- {d['t0_se']:.4f} s  k = {d['k']:.4f} +- "
            f"{d['k_se']:.4f} s  R2 = {d['r2']:.4f}  runs = {d['n_runs']}"
        )
        print(
            f"cache     r = {c['cached_token_cost_ratio']:.3f} +- "
            f"{c['cached_token_cost_ratio_se']:.3f}  speedup = {c['cache_speedup']:.2f}x"
        )
        for probe in ("prefill", "decode"):
            q = i[probe]
            levels = ", ".join(
                f"{r['n_other_busy']}: {100 * r['slowdown']:+.1f}%" for r in q["by_level"]
            )
            print(
                f"interf.   {probe:8s} s = {q['s']:.3f} +- {q['s_se']:.3f}  "
                f"linear R2 = {q['linear_r2']:.2f}  slowdown by n: {levels}"
            )
        ps, ds = p["residual_summary"], d["residual_summary"]
        print(
            f"residuals prefill rmse = {ps['rmse']:.4f} s (max rel {ps['max_rel']:.2f}); "
            f"decode rmse = {ds['rmse']:.5f} s (max rel {ds['max_rel']:.2f})"
        )
    print("\nVerdicts:")
    for v in result["verdicts"]:
        print(" -", v)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", type=Path, default=None, help="run directory (default: latest)")
    ap.add_argument("--n-servers", type=int, default=None)
    args = ap.parse_args()
    run = args.run or latest_run()
    print(f"run: {run}")
    print_summary(fit_run(run, args.n_servers))


if __name__ == "__main__":
    main()
