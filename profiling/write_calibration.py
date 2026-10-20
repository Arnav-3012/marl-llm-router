"""Write profiling/calibration.json from a fit and plot fit vs measured (M0.5.5, M0.5.6). Tier B.

uv run python -m profiling.write_calibration --run results/profiling/<run> --option A|B|C

Reads fit_output.json (profiling/fit_calibration.py) and the raw CSVs, the ADR-015 interference
option, and
configs/classes.yaml (synthetic prices, KV allotment). Per class it writes a,
cached_token_cost_ratio, t0, k, the
interference slowdowns, kv_token_budget (allotment / KV bytes per token read from the GGUF file),
max_batch (the
profiled --parallel slots) and the price. Plots go to <run>/plots/. Values are copied from the fit,
never edited.
"""

from __future__ import annotations

import argparse
import json
import struct
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GGUF_TYPES = {
    0: "<B",
    1: "<b",
    2: "<H",
    3: "<h",
    4: "<I",
    5: "<i",
    6: "<f",
    7: "<?",
    10: "<Q",
    11: "<q",
    12: "<d",
}


def _read_value(f, t: int):
    if t in GGUF_TYPES:
        fmt = GGUF_TYPES[t]
        return struct.unpack(fmt, f.read(struct.calcsize(fmt)))[0]
    if t == 8:
        (n,) = struct.unpack("<Q", f.read(8))
        return f.read(n).decode("utf-8", "replace")
    if t == 9:
        (et,) = struct.unpack("<I", f.read(4))
        (n,) = struct.unpack("<Q", f.read(8))
        return [_read_value(f, et) for _ in range(n)]
    raise ValueError(f"unknown GGUF value type {t}")


def gguf_metadata(path: Path, wanted: set) -> dict:
    """Read selected key/value pairs from a GGUF header (no library needed)."""
    out: dict = {}
    with open(path, "rb") as f:
        if f.read(4) != b"GGUF":
            raise ValueError(f"{path.name}: not a GGUF file")
        _version, _n_tensors, n_kv = struct.unpack("<IQQ", f.read(20))
        for _ in range(n_kv):
            (kl,) = struct.unpack("<Q", f.read(8))
            key = f.read(kl).decode()
            (t,) = struct.unpack("<I", f.read(4))
            val = _read_value(f, t)
            if key in wanted or key.endswith(tuple(wanted)):
                out[key] = val
    return out


def kv_bytes_per_token(path: Path) -> int:
    """K and V, f16, all layers: 2 * layers * kv_heads * head_dim * 2 bytes."""
    meta = gguf_metadata(
        path,
        {".block_count", ".attention.head_count_kv", ".attention.head_count", ".embedding_length"},
    )
    get = lambda suffix: next(v for k, v in meta.items() if k.endswith(suffix))  # noqa: E731
    layers, kv_heads, heads, emb = (
        get(".block_count"),
        get(".attention.head_count_kv"),
        get(".attention.head_count"),
        get(".embedding_length"),
    )
    return int(2 * layers * kv_heads * (emb // heads) * 2)


def build(fit: dict, option: str, classes_cfg: dict, prof_cfg: dict, kv_bytes: dict) -> dict:
    """Assemble calibration.json from the fit. option: ADR-015 A (linear in busy neighbours), B
    (fixed), C (none).
    """
    out = {"interference_model": option, "classes": {}, "notes": []}
    for cls, f in fit["classes"].items():
        inter = f["interference"]
        if option == "A":
            s_pf, s_dec = inter["prefill"]["s"], inter["decode"]["s"]
        elif option == "B":
            s_pf, s_dec = (
                inter["prefill"]["fixed_multiplier_slowdown"],
                inter["decode"]["fixed_multiplier_slowdown"],
            )
        else:
            s_pf = s_dec = 0.0
        # The simulator prices prefill as a*E + q*E^2 through the origin (fit_prefill_model); fits
        # made before that model existed fall back to the straight line's slope and q = 0.
        pm = f.get("prefill_model") or {"a": f["prefill"]["a"], "q": 0.0}
        t0, r = f["decode"]["t0"], f["cache"]["cached_token_cost_ratio"]
        if t0 < 0:
            out["notes"].append(
                f"{cls}: fitted t0 = {t0:.5f} s is negative; clipped to 0 (k carries the step time)"
            )
            t0 = 0.0
        if r < 0:
            out["notes"].append(
                f"{cls}: fitted cached-token cost ratio {r:.4f} is negative; clipped to 0"
            )
            r = 0.0
        out["classes"][cls] = {
            "a": pm["a"],
            "prefill_quad": pm["q"],
            "cached_token_cost_ratio": min(r, 1.0),
            "t0": t0,
            "k": f["decode"]["k"],
            "s_prefill": max(s_pf, 0.0),
            "s_decode": max(s_dec, 0.0),
            "kv_token_budget": int(classes_cfg["kv_allotment_bytes"] // kv_bytes[cls]),
            "kv_bytes_per_token": kv_bytes[cls],
            "max_batch": prof_cfg["parallel_slots"],
            "price_per_busy_second": classes_cfg["price_per_busy_second"][cls],
            "fit_r2": {"prefill": pm.get("r2", f["prefill"]["r2"]), "decode": f["decode"]["r2"]},
            "fit_prefill_max_rel_err": pm.get("max_rel_err_of_means"),
        }
    out["source"] = {
        "fit": fit["run_dir"],
        "written": datetime.now().isoformat(timespec="seconds"),
        "n_servers": fit["n_servers"],
    }
    return out


def plots(run: Path, fit: dict) -> list:
    out_dir = run / "plots"
    out_dir.mkdir(exist_ok=True)
    written = []
    for cls in fit["classes"]:
        fig, ax = plt.subplots(2, 3, figsize=(15, 8))
        pre = pd.read_csv(run / f"prefill_{cls}.csv")
        f = fit["classes"][cls]
        p = np.linspace(pre["prompt_tokens"].min(), pre["prompt_tokens"].max(), 50)
        ax[0, 0].scatter(pre["prompt_tokens"], pre["ttft_s"], s=14, alpha=0.6)
        m = f.get("prefill_model") or {"a": f["prefill"]["a"], "q": 0.0, "r2": f["prefill"]["r2"]}
        ax[0, 0].plot(p, f["prefill"]["a"] * p + f["prefill"]["c"], "k--", lw=1, label="line + c")
        ax[0, 0].plot(p, m["a"] * p + m["q"] * p**2, "r-", label="a*P + q*P^2 (simulator)")
        ax[0, 0].legend()
        ax[0, 0].set(
            title=f"{cls}: TTFT vs prompt (model R2 {m['r2']:.3f})",
            xlabel="prompt tokens",
            ylabel="TTFT (s)",
        )
        pt = pre["prompt_tokens"]
        resid = (pre["ttft_s"] - (m["a"] * pt + m["q"] * pt**2)) / pre["ttft_s"]
        ax[1, 0].scatter(pt, 100 * resid, s=14, alpha=0.6)
        ax[1, 0].axhline(0, color="k", lw=0.8)
        ax[1, 0].set(
            title="prefill model: relative residuals",
            xlabel="prompt tokens",
            ylabel="residual (% of measured)",
        )
        bat = (
            pd.read_csv(run / f"batch_{cls}.csv")
            .groupby(["batch_size", "prompt_tokens", "repeat"], as_index=False)[
                "step_time_all_active_s"
            ]
            .first()
        )
        b = np.array([1, 2, 4, 8])
        ax[0, 1].scatter(bat["batch_size"], bat["step_time_all_active_s"], s=14, alpha=0.6)
        ax[0, 1].plot(b, f["decode"]["t0"] + f["decode"]["k"] * b, "r-")
        ax[0, 1].set(
            title=f"decode step vs batch (R2 {f['decode']['r2']:.3f})",
            xlabel="batch size",
            ylabel="step time (s)",
        )
        ax[1, 1].scatter(
            bat["batch_size"],
            bat["step_time_all_active_s"]
            - (f["decode"]["t0"] + f["decode"]["k"] * bat["batch_size"]),
            s=14,
            alpha=0.6,
        )
        ax[1, 1].axhline(0, color="k", lw=0.8)
        ax[1, 1].set(title="decode residuals", xlabel="batch size", ylabel="residual (s)")
        cache = pd.read_csv(run / f"cache_{cls}.csv")
        for cond, c in (("cold", "tab:blue"), ("warm", "tab:orange")):
            sub = (
                cache[cache.condition == cond]
                .groupby("prefix_tokens")["ttft_s"]
                .agg(["mean", "std"])
            )
            ax[0, 2].errorbar(
                sub.index, sub["mean"], yerr=sub["std"], label=cond, color=c, marker="o"
            )
        ax[0, 2].set(
            title=f"prefix cache: speedup {f['cache']['cache_speedup']:.1f}x",
            xlabel="cached prefix tokens",
            ylabel="TTFT (s)",
        )
        ax[0, 2].legend()
        for probe, c in (("prefill", "tab:green"), ("decode", "tab:red")):
            lv = f["interference"][probe]["by_level"]
            ax[1, 2].errorbar(
                [r["n_other_busy"] for r in lv],
                [100 * r["slowdown"] for r in lv],
                yerr=[100 * (r["slowdown_se"] or 0) for r in lv],
                label=probe,
                color=c,
                marker="o",
            )
        ax[1, 2].set(
            title="interference: slowdown vs busy neighbours",
            xlabel="other servers busy",
            ylabel="slowdown (%)",
        )
        ax[1, 2].legend()
        fig.tight_layout()
        path = out_dir / f"fit_{cls}.png"
        fig.savefig(path, dpi=110)
        plt.close(fig)
        written.append(path)
    return written


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument(
        "--option", choices=["A", "B", "C"], required=True, help="ADR-015 interference model"
    )
    ap.add_argument("--out", type=Path, default=ROOT / "profiling" / "calibration.json")
    a = ap.parse_args()
    fit = json.loads((a.run / "fit_output.json").read_text())
    prof = yaml.safe_load((ROOT / "configs" / "profiling.yaml").read_text())
    classes_cfg = yaml.safe_load((ROOT / "configs" / "classes.yaml").read_text())
    kv = {cls: kv_bytes_per_token(ROOT / prof["servers"][cls]["model"]) for cls in fit["classes"]}
    cal = build(fit, a.option, classes_cfg, prof, kv)
    a.out.write_text(json.dumps(cal, indent=2))
    for p in plots(a.run, fit):
        print("plot", p)
    print(json.dumps(cal, indent=2))
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
