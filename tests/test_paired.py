"""Paired evaluation outputs (Sh.H1): same slice id, seed list and config hash for every policy,
event logs within their cap, and the paired-difference interval, all on a small fixture slice.
"""

import json

import pytest

from marl_lb.eval import paired
from marl_lb.eval.evaluate import run_episode
from marl_lb.policies.heuristics import RandomGlobal, SEDGlobal
from tests.helpers import make_cluster
from tests.test_cluster import random_stream

SEEDS = [0, 1, 2]
RHOS = [0.5, 0.8]
LAMBDA_SAT = 2.0  # fixture capacity in req/s; rho * LAMBDA_SAT is the stream rate


def global_runner(make_policy):
    def run(stream, seed, record):
        cluster = make_cluster(
            mode="global", global_policy=make_policy(seed), record=record, max_queue=50
        )
        metrics, _ = run_episode(cluster, stream, seed)
        return metrics, (cluster.run.events if record else [])

    return run


RUNNERS = {
    "sed_global": global_runner(lambda seed: SEDGlobal()),
    "random": global_runner(lambda seed: RandomGlobal(seed=seed)),
}


def stream_fn(rate, seed):
    return random_stream(n=60, rate=rate, seed=seed)


def run_fixture(tmp_path, cap=60000, runners=RUNNERS):
    return paired.evaluate_paired(
        runners,
        stream_fn,
        RHOS,
        lambda rho: rho * LAMBDA_SAT,
        SEEDS,
        "fixture",
        "cfg123",
        tmp_path,
        event_seed=0,
        event_cap=cap,
    )


def test_every_policy_file_carries_the_same_slice_seeds_and_config_hash(tmp_path):
    files = run_fixture(tmp_path)
    assert len(files) == len(RUNNERS) * len(RHOS)
    report = paired.verify_paired(tmp_path)
    assert set(report) == set(RHOS)
    for row in report.values():
        assert row["policies"] == ["random", "sed_global"]
        assert row["seeds"] == SEEDS and row["config_hash"] == "cfg123"
    docs = [json.loads(f.read_text()) for f in files]
    for rho in RHOS:
        same_load = [d for d in docs if d["rho"] == rho]
        assert len({d["slice_id"] for d in same_load}) == 1
        assert len({json.dumps(d["slice_ids"], sort_keys=True) for d in same_load}) == 1
    assert len({d["slice_id"] for d in docs if d["rho"] == 0.5}) == 1
    assert {d["slice_id"] for d in docs if d["rho"] == 0.5} != {
        d["slice_id"] for d in docs if d["rho"] == 0.8
    }  # a different load is a different slice


def test_verify_fails_when_a_policy_saw_different_traffic(tmp_path):
    run_fixture(tmp_path)
    f = tmp_path / "random_rho0.5.json"
    d = json.loads(f.read_text())
    d["slice_id"] = "000000000000"
    f.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="slice_id"):
        paired.verify_paired(tmp_path)


def test_verify_fails_on_different_seed_list_or_config_hash(tmp_path):
    run_fixture(tmp_path)
    f = tmp_path / "sed_global_rho0.8.json"
    d = json.loads(f.read_text())
    d["seeds"] = [0, 1]
    f.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="seeds"):
        paired.verify_paired(tmp_path)
    d["seeds"] = SEEDS
    d["config_hash"] = "other"
    f.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="config_hash"):
        paired.verify_paired(tmp_path)


def test_event_logs_respect_the_cap_and_keep_decisions(tmp_path):
    run_fixture(tmp_path, cap=40)
    report = paired.verify_paired(tmp_path)  # also checks kept <= cap and file line counts
    assert report
    for f in tmp_path.glob("*_rho*.json"):
        d = json.loads(f.read_text())
        assert d["events"]["kept"] <= 40 and d["events"]["seed"] == 0
        lines = (tmp_path / d["events_file"]).read_text().splitlines()
        assert len(lines) == d["events"]["kept"] <= 40


def test_cap_events_thins_snapshots_but_keeps_other_events_in_order():
    events = []
    for t in range(100):
        events.append({"e": "servers", "t": t})
        if t % 10 == 0:
            events.append({"e": "arrive", "t": t})
            events.append({"e": "resolve", "t": t})
    kept, info = paired.cap_events(events, cap=60)
    assert len(kept) <= 60 and not info["truncated"] and info["original"] == len(events)
    assert [e for e in kept if e["e"] != "servers"] == [e for e in events if e["e"] != "servers"]
    assert [e["t"] for e in kept] == sorted(e["t"] for e in kept)  # order preserved


def test_cap_events_truncates_and_says_so_when_decisions_alone_exceed_the_cap():
    events = [{"e": "arrive", "t": t} for t in range(50)]
    kept, info = paired.cap_events(events, cap=20)
    assert len(kept) == 20 and info["truncated"] and kept == events[:20]
    same, info = paired.cap_events(events, cap=50)
    assert same == events and not info["truncated"]


def test_stream_id_tracks_the_requests_not_the_object():
    a, b = stream_fn(1.0, 0), stream_fn(1.0, 0)
    assert a is not b and paired.stream_id(a) == paired.stream_id(b)
    assert paired.stream_id(a) != paired.stream_id(stream_fn(1.0, 1))
    assert paired.stream_id(a) != paired.stream_id(stream_fn(1.5, 0))


def test_run_one_detects_a_policy_that_changes_the_traffic():
    def meddler(stream, seed, record):
        stream.reverse()
        return {}, []

    with pytest.raises(RuntimeError, match="modified"):
        paired.run_one(meddler, stream_fn(1.0, 0), 0, record=False)


def test_config_hash_ignores_key_order_and_changes_with_a_value():
    assert paired.config_hash({"a": 1, "b": 2}) == paired.config_hash({"b": 2, "a": 1})
    assert paired.config_hash({"a": 1}) != paired.config_hash({"a": 2})


def test_paired_difference_has_known_mean_and_interval():
    a = {"0": {"g": 3.0}, "1": {"g": 4.0}, "2": {"g": 5.0}}
    b = {"0": {"g": 1.0}, "1": {"g": 2.0}, "2": {"g": 3.0}}
    same = paired.paired_difference(a, b, "g")
    assert same["mean_diff"] == pytest.approx(2.0) and same["ci95"] == pytest.approx([2.0, 2.0])
    assert same["excludes_zero"] and same["n"] == 3
    c = {"0": {"g": 2.0}, "1": {"g": 4.0}, "2": {"g": 6.0}}  # differences 1, 2, 3 against b
    d = paired.paired_difference(c, b, "g")
    # mean 2, sd 1, n 3: half-width = t(0.975, 2) / sqrt(3) = 4.3027 / 1.7321
    assert d["mean_diff"] == pytest.approx(2.0)
    assert d["ci95"] == pytest.approx([2.0 - 2.4843, 2.0 + 2.4843], abs=1e-3)
    assert not d["excludes_zero"]


def test_paired_difference_uses_only_shared_seeds_and_needs_two():
    a = {"0": {"g": 1.0}, "1": {"g": 2.0}, "2": {"g": 3.0}}
    b = {"1": {"g": 1.0}, "2": {"g": 1.0}}
    assert paired.paired_difference(a, b, "g")["seeds"] == [1, 2]
    with pytest.raises(ValueError, match="at least 2"):
        paired.paired_difference(a, {"0": {"g": 1.0}}, "g")
