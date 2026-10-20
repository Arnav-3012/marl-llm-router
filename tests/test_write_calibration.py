"""calibration.json assembly from a fit, and the GGUF header reader (synthetic file, no model
needed).
"""

import struct

import pytest
from profiling.write_calibration import build, gguf_metadata, kv_bytes_per_token


def gguf_file(path, kv: dict):
    """A minimal GGUF header with u32 key/values: magic, version 3, 0 tensors, n kv pairs."""
    with open(path, "wb") as f:
        f.write(b"GGUF" + struct.pack("<IQQ", 3, 0, len(kv)))
        for k, v in kv.items():
            f.write(
                struct.pack("<Q", len(k)) + k.encode() + struct.pack("<I", 4) + struct.pack("<I", v)
            )


def test_gguf_reader_and_kv_bytes_per_token(tmp_path):
    p = tmp_path / "m.gguf"
    gguf_file(
        p,
        {
            "qwen2.block_count": 36,
            "qwen2.attention.head_count": 16,
            "qwen2.attention.head_count_kv": 2,
            "qwen2.embedding_length": 2048,
        },
    )
    assert gguf_metadata(p, {".block_count"})["qwen2.block_count"] == 36
    assert kv_bytes_per_token(p) == 2 * 36 * 2 * 128 * 2  # K and V, f16: 36,864 bytes per token


def fit_for(t0=0.01, r=0.05):
    cls = {
        "prefill": {"a": 0.001, "c": 0.0, "r2": 0.99},
        "prefill_model": {"a": 0.0012, "q": 3.0e-8, "r2": 0.995, "max_rel_err_of_means": 0.08},
        "decode": {"t0": t0, "k": 0.002, "r2": 0.98},
        "cache": {"cached_token_cost_ratio": r},
        "interference": {
            "prefill": {"s": 0.4, "fixed_multiplier_slowdown": 0.3},
            "decode": {"s": 0.2, "fixed_multiplier_slowdown": 0.15},
        },
    }
    return {"run_dir": "x", "n_servers": 4, "classes": {"fast_expensive": cls}}


CFG = {"kv_allotment_bytes": 1_000_000, "price_per_busy_second": {"fast_expensive": 4.0}}


@pytest.mark.parametrize(
    ("opt", "s_pf", "s_dec"), [("A", 0.4, 0.2), ("B", 0.3, 0.15), ("C", 0.0, 0.0)]
)
def test_interference_option_selects_which_slowdown_is_written(opt, s_pf, s_dec):
    out = build(fit_for(), opt, CFG, {"parallel_slots": 8}, {"fast_expensive": 40_000})
    c = out["classes"]["fast_expensive"]
    assert out["interference_model"] == opt and (c["s_prefill"], c["s_decode"]) == (s_pf, s_dec)
    assert c["kv_token_budget"] == 25 and c["max_batch"] == 8 and c["price_per_busy_second"] == 4.0


def test_negative_fitted_values_are_clipped_and_noted():
    out = build(
        fit_for(t0=-0.001, r=-0.02), "A", CFG, {"parallel_slots": 8}, {"fast_expensive": 40_000}
    )
    c = out["classes"]["fast_expensive"]
    assert c["t0"] == 0.0 and c["cached_token_cost_ratio"] == 0.0 and len(out["notes"]) == 2


def test_prefill_model_a_and_q_are_written_and_old_fits_fall_back_to_the_line():
    out = build(fit_for(), "A", CFG, {"parallel_slots": 8}, {"fast_expensive": 40_000})
    c = out["classes"]["fast_expensive"]
    assert c["a"] == 0.0012 and c["prefill_quad"] == 3.0e-8
    assert c["fit_prefill_max_rel_err"] == 0.08
    old = fit_for()
    del old["classes"]["fast_expensive"]["prefill_model"]
    c = build(old, "A", CFG, {"parallel_slots": 8}, {"fast_expensive": 40_000})["classes"][
        "fast_expensive"
    ]
    assert c["a"] == 0.001 and c["prefill_quad"] == 0.0
