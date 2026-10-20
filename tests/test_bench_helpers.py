"""Pure helpers of profiling/bench_server.py: no server is started."""

import math

import numpy as np
import pytest
from profiling.bench_server import (
    DEFAULT_CONFIG,
    all_active_step_time,
    load_config,
    make_prompt,
    neighbour_order,
    ttft_and_tpot,
)


def test_ttft_and_tpot_from_token_times():
    ttft, tpot = ttft_and_tpot(10.0, [10.5, 10.6, 10.8, 11.0])
    assert ttft == pytest.approx(0.5)
    assert tpot == pytest.approx((11.0 - 10.5) / 3)


def test_tpot_is_nan_for_a_single_token():
    ttft, tpot = ttft_and_tpot(0.0, [0.25])
    assert ttft == 0.25 and math.isnan(tpot)


def test_step_time_uses_only_the_window_where_every_request_decodes():
    # Request A starts decoding at t=0 and ends at t=2.0; request B starts at t=1.0 and ends at 3.0,
    # both at 0.1 s per token. Everything outside [1.0, 2.0] is not "all active".
    a = [i * 0.1 for i in range(21)]
    b = [1.0 + i * 0.1 for i in range(21)]
    assert all_active_step_time([a, b], min_tokens=5) == pytest.approx(0.1)


def test_step_time_is_nan_when_the_window_is_too_short():
    a = [0.0, 0.1, 0.2]
    b = [0.19, 0.29, 0.39]
    assert math.isnan(all_active_step_time([a, b], min_tokens=8))


def test_prompt_has_the_exact_length_and_is_seeded():
    pool = np.arange(100, 200)
    one = make_prompt(np.random.default_rng(1), pool, 37)
    two = make_prompt(np.random.default_rng(1), pool, 37)
    assert len(one) == 37 and one == two and set(one) <= set(pool.tolist())


def test_neighbour_order_puts_the_same_class_sibling_first():
    ports = {"fast": [1, 3], "slow": [2, 4]}
    assert neighbour_order(1, ports, "fast") == [3, 2, 4]
    assert neighbour_order(2, ports, "slow") == [4, 1, 3]


def test_config_loads_and_smoke_shrinks_the_grids():
    full, smoke = load_config(DEFAULT_CONFIG, False), load_config(DEFAULT_CONFIG, True)
    assert full["repeats"] >= 10  # Guide H1
    assert smoke["repeats"] < full["repeats"]
    assert max(full["batch_sizes"]) <= full["parallel_slots"]  # every batch fits in the slots
    assert full["interference_levels"] == list(
        range(sum(len(s["ports"]) for s in full["servers"].values()))
    )
