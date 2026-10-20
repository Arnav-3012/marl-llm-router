"""mean +- 95% CI against known values, and the Pareto frontier on small cases (M4.1, M4.3)."""

import math

import pytest

from marl_lb.eval.pareto import pareto_front
from marl_lb.eval.stats import aggregate, mean_ci


def test_mean_ci_matches_a_hand_computed_case():
    # values 1..5: mean 3, sample sd sqrt(2.5), sem sqrt(0.5), t(0.975, 4) = 2.7764451
    m, ci = mean_ci([1, 2, 3, 4, 5])
    assert m == 3.0 and ci == pytest.approx(math.sqrt(0.5) * 2.7764451, rel=1e-6)


def test_one_value_has_no_interval_and_empty_is_an_error():
    assert mean_ci([7.0])[0] == 7.0 and math.isnan(mean_ci([7.0])[1])
    with pytest.raises(ValueError):
        mean_ci([])


def test_identical_values_give_a_zero_width_interval():
    assert mean_ci([2, 2, 2])[1] == 0.0


def test_aggregate_drops_nan_and_counts_n():
    out = aggregate([{"g": 1.0}, {"g": 3.0}, {"g": float("nan")}], ["g", "missing"])
    assert out["g"]["mean"] == 2.0 and out["g"]["n"] == 2
    assert out["missing"] == {"mean": None, "ci": None, "n": 0}


def test_pareto_drops_dominated_points():
    pts = [(1, 5), (2, 3), (3, 4), (4, 1), (2, 6)]
    assert pareto_front(pts) == [0, 1, 3]  # (3,4) is beaten by (2,3); (2,6) by (1,5)


def test_pareto_ties_and_single_point():
    assert pareto_front([(1, 1), (1, 1)]) == [0, 1]
    assert pareto_front([(5, 5)]) == [0]
    assert pareto_front([(1, 2), (1, 3)]) == [0]  # same cost, worse latency is dominated
