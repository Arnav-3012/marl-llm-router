"""Config, utils and metrics helpers."""

import pytest

from marl_lb.config import load_config
from marl_lb.sim.metrics import jain_index, percentile
from marl_lb.utils.io import make_run_dir
from marl_lb.utils.logging import CsvLogger
from marl_lb.utils.seeding import seed_everything


def test_config_attribute_access_and_errors(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("a: 1\nb:\n  c: 2\n")
    cfg = load_config(p)
    assert cfg.a == 1 and cfg.b.c == 2 and cfg["b"]["c"] == 2
    with pytest.raises(AttributeError):
        _ = cfg.missing
    with pytest.raises(ValueError):
        load_config(tmp_path / "none.yaml")


def test_run_dir_copies_the_config(tmp_path):
    run = make_run_dir("exp", 3, {"x": 1}, root=tmp_path)
    assert run.name.endswith("_seed3") and (run / "config.yaml").read_text().strip() == "x: 1"


def test_csv_logger_writes_header_once(tmp_path):
    log = CsvLogger(tmp_path / "l.csv")
    log.log({"a": 1, "b": 2})
    log.log({"a": 3, "b": 4})
    assert (tmp_path / "l.csv").read_text().splitlines() == ["a,b", "1,2", "3,4"]


def test_seed_everything_is_repeatable():
    import random

    seed_everything(5)
    a = random.random()
    seed_everything(5)
    assert a == random.random()


def test_jain_index_and_percentile():
    assert jain_index([1, 1, 1, 1]) == pytest.approx(1.0)
    assert jain_index([1, 0, 0, 0]) == pytest.approx(0.25)
    assert percentile([1, 2, 3, 4, 5], 50) == 3


def test_class_balance_separates_fast_sharing_from_cluster_wide_busyness():
    from marl_lb.sim.metrics import class_balance

    layout = ["fast_expensive", "slow_cheap", "fast_expensive", "slow_cheap"]
    # fast servers busy and equal, slow idle: all-server Jain is low, fast-only Jain is 1
    b = class_balance([0.9, 0.0, 0.9, 0.0], layout)
    assert b == {"util_fast": pytest.approx(0.9), "util_slow": 0.0, "jain_fast": pytest.approx(1.0)}
    assert jain_index([0.9, 0.0, 0.9, 0.0]) == pytest.approx(0.5)
    # every server saturated: all-server Jain is 1 although the cluster is overloaded
    assert jain_index([1, 1, 1, 1]) == pytest.approx(1.0)
    # one fast server doing everything: fast-only Jain is 1/2
    assert class_balance([0.9, 0.0, 0.0, 0.0], layout)["jain_fast"] == pytest.approx(0.5)
