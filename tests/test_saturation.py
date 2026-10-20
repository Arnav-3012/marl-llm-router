"""lambda_sat search logic on synthetic sweeps, one per criterion (M1.27), plus a non-monotone
sweep.
"""

import pytest

from marl_lb.eval.saturation import find_lambda_sat, is_saturated

GRID = [1, 2, 4, 8, 16, 32]


def sweep(true_sat, kind):
    """A synthetic world that is fine below true_sat and breaks one criterion at and above it."""

    def evaluate(rate):
        bad = rate >= true_sat
        return {
            "completion_ratio": 0.80 if bad and kind == "completion" else 0.99,
            "drop_rate": 0.05 if bad and kind == "drop" else 0.0,
            "backlog_ratio": 2.5 if bad and kind == "backlog" else 1.0,
        }

    return evaluate


@pytest.mark.parametrize("kind", ["completion", "drop", "backlog"])
def test_each_criterion_alone_recovers_the_true_saturation_rate(kind):
    out = find_lambda_sat(sweep(10.0, kind), GRID, refine_steps=8)
    assert out["lambda_sat_rps"] == pytest.approx(10.0, abs=0.1)
    assert out["monotone"]["ok"]


def test_everything_passing_gives_no_lambda_sat():
    out = find_lambda_sat(sweep(1e9, "drop"), GRID)
    assert out["lambda_sat_rps"] is None


def test_saturated_from_the_first_grid_point_returns_that_point():
    assert find_lambda_sat(sweep(0.5, "drop"), GRID)["lambda_sat_rps"] == 1


def test_a_non_monotone_sweep_is_flagged():
    def evaluate(rate):
        # completion ratio recovers at rate 8 although it fell at 4: not monotone
        cr = {1: 0.99, 2: 0.99, 4: 0.90, 8: 0.99, 16: 0.5, 32: 0.4}[rate]
        return {"completion_ratio": cr, "drop_rate": 0.0, "backlog_ratio": 1.0}

    out = find_lambda_sat(evaluate, GRID, refine_steps=0)
    assert not out["monotone"]["ok"] and out["monotone"]["violations"][0][0] == "completion_ratio"


def test_thresholds_are_adjustable():
    agg = {"completion_ratio": 0.97, "drop_rate": 0.0, "backlog_ratio": 1.0}
    assert not is_saturated(agg)
    assert is_saturated(agg, {"completion_min": 0.98})
