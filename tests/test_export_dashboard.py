"""Dashboard export on FIXTURE results only: null on missing, cap respected, schema_version,
traceability (Sh.2).
"""

import json

import pytest
from scripts.export_dashboard_data import (
    SCHEMA_VERSION,
    frames_from_events,
    run_export,
)  # fmt: skip

M = {
    "goodput_rps": 3.0,
    "sla_attainment": 0.9,
    "breach_rate": 0.1,
    "drop_rate": 0.0,
    "ttft_p95": 2.0,
    # fmt: skip
    "tpot_p95": 0.04,
    "e2e_p95": 5.0,
    "cost_per_request": 4.0,
    "cache_hit_rate": 0.2,
    "jain_utilisation": 0.9,
}


def make_run(root, exp, seed, files, done=True):
    d = root / "results" / exp / f"2026_seed{seed}"
    d.mkdir(parents=True)
    (d / "config.yaml").write_text("k: full\n")
    for name, obj in files.items():
        (d / name).write_text(obj if isinstance(obj, str) else json.dumps(obj))
    if done:
        (d / "DONE").write_text("x")
    return d


def scaled(m, f):
    return {k: v * f for k, v in m.items()}


@pytest.fixture
def fixture_root(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "decisions.md").write_text(
        "## ADR-001: Ticks\nStatus: accepted · Date: x\n"
    )
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "sim.yaml").write_text("dt: 0.1\n")
    for seed, f in ((0, 1.0), (1, 2.0)):
        make_run(
            tmp_path,
            "baselines",
            seed,
            {"metrics.json": {"sed_global@0.8": scaled(M, f), "sed_local_full@0.8": scaled(M, f)}},
        )
        make_run(
            tmp_path,
            "main",
            seed,
            {
                "eval_metrics.json": {"0.8": scaled(M, f)},
                "train_log.csv": (
                    "episode,return_mean,goodput_rps,sla_attainment,td_loss,mean_q,epsilon,"
                    "act_accept,act_forward,act_defer\n"
                    "0,1,2,0.5,nan,0,1,5,2,1\n1,2,3,0.6,0.1,0.2,0.9,6,2,1\n"
                ),
            },
        )
    return tmp_path


def load(out, name):
    return json.loads((out / name).read_text())


def test_missing_results_become_not_run_never_a_number(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "decisions.md").write_text("")
    (tmp_path / "results").mkdir()
    out = tmp_path / "out"
    run_export(tmp_path / "results", out, root=tmp_path, dt=0.1)
    for name in (
        "baselines.json",
        "pareto.json",
        "observability.json",
        "training.json",
        "traces.json",
    ):
        env = load(out, name)
        assert (
            env["status"] == "not_run"
            and env["data"] is None
            and env["schema_version"] == SCHEMA_VERSION
        )
    assert load(out, "replay_ddqn_0.8.json")["status"] == "not_run"


def test_every_file_has_a_schema_version_and_the_manifest_lists_them(fixture_root):
    out = fixture_root / "out"
    names = run_export(fixture_root / "results", out, root=fixture_root, dt=0.1)
    manifest = load(out, "manifest.json")
    assert manifest["schema_version"] == SCHEMA_VERSION and set(manifest["files"]) == set(names)
    assert all(load(out, n)["schema_version"] == SCHEMA_VERSION for n in names)


def test_numbers_are_the_seed_means_of_the_result_files_and_carry_their_source(fixture_root):
    out = fixture_root / "out"
    run_export(fixture_root / "results", out, root=fixture_root, dt=0.1)
    env = load(out, "baselines.json")
    g = env["data"]["baselines"]["policies"]["sed_global"]["0.8"]["goodput_rps"]
    assert g["mean"] == pytest.approx(4.5) and g["n"] == 2 and g["ci"] > 0  # mean of 3.0 and 6.0
    src = env["source"]["baselines"]
    assert src["n_seeds"] == 2 and len(src["config_hash"]) == 12
    assert all(f.startswith("results/baselines/") for f in src["files"])
    learned = env["data"]["learned"]["rows"]["0.8"]["goodput_rps"]
    assert learned["mean"] == pytest.approx(4.5)


def test_unfinished_runs_are_ignored(fixture_root):
    make_run(
        fixture_root,
        "baselines",
        2,
        {"metrics.json": {"sed_global@0.8": scaled(M, 100)}},
        done=False,
    )
    out = fixture_root / "out"
    run_export(fixture_root / "results", out, root=fixture_root, dt=0.1)
    assert load(out, "baselines.json")["source"]["baselines"]["n_seeds"] == 2


def test_training_curve_averages_over_seeds_and_skips_nan(fixture_root):
    out = fixture_root / "out"
    run_export(fixture_root / "results", out, root=fixture_root, dt=0.1)
    ep = load(out, "training.json")["data"]["episodes"]
    assert (
        ep[0]["return_mean"] == 1
        and ep[0]["td_loss"] is None
        and ep[1]["td_loss"] == pytest.approx(0.1)
    )


def test_replay_frame_cap_is_respected_and_events_are_kept():
    events = []
    for t in range(1000):
        events.append(
            {"tick": t, "t": t * 0.1, "e": "servers", "queue": [t], "active": [1], "kv": [0.1]}
        )
        events.append(
            {"tick": t, "t": t * 0.1, "e": "arrive", "req": t, "entry": 0, "p": 10, "o": 5}
        )
    frames = frames_from_events(events, 0.1, cap=100)
    assert len(frames) <= 100
    assert sum(len(f["arrivals"]) for f in frames) == 1000  # merged, not lost
    assert frames[-1]["tick"] == 999


def test_method_page_lists_the_adrs(fixture_root):
    out = fixture_root / "out"
    run_export(fixture_root / "results", out, root=fixture_root, dt=0.1)
    assert load(out, "method.json")["data"]["adrs"][0] == {
        "id": "ADR-001",
        "title": "Ticks",
        "status": "accepted",
    }


# ---- head-to-head (Sh.H2): paired results -> headtohead.json + replay files --------------------
def make_paired_run(root, seeds=(0, 1, 2), cap=60000):
    import yaml

    from marl_lb.eval import paired
    from tests.test_paired import RUNNERS, stream_fn

    run = root / "results" / "paired" / "20261020-000000"
    run.mkdir(parents=True)
    runners = {"ddqn_agents": RUNNERS["sed_global"], **RUNNERS}
    paired.evaluate_paired(
        runners, stream_fn, [0.5, 0.8], lambda rho: rho * 2.0, list(seeds), "heldout", "cfg1", run,
        event_seed=0, event_cap=cap,
    )  # fmt: skip
    cfg = {
        "learned": {"name": "ddqn_agents", "experiment": "main"},
        "baselines": ["random", "sed_global"],
        "event_seed": 0,
        "split": "heldout",
    }
    (run / "config.yaml").write_text(yaml.safe_dump(cfg))
    (run / "DONE").write_text("x")
    return run


def test_headtohead_is_not_run_without_a_paired_folder(fixture_root):
    out = fixture_root / "out"
    run_export(fixture_root / "results", out, root=fixture_root, dt=0.1)
    env = load(out, "headtohead.json")
    assert env["status"] == "not_run" and env["data"] is None and "evaluate_paired" in env["reason"]
    assert "headtohead.json" in load(out, "manifest.json")["files"]


def test_headtohead_exports_summaries_paired_differences_and_replays(fixture_root):
    make_paired_run(fixture_root)
    out = fixture_root / "out"
    run_export(fixture_root / "results", out, root=fixture_root, dt=0.1, cap=200)
    env = load(out, "headtohead.json")
    assert env["status"] == "ok" and env["source"]["n_seeds"] == 3
    d = env["data"]
    assert d["learned"] == "ddqn_agents"
    assert [p["id"] for p in d["policies"]] == ["ddqn_agents", "random", "sed_global"]
    assert [p["mode"] for p in d["policies"]] == ["agents", "agents", "global"]
    for row in d["rhos"].values():
        assert row["seeds"] == [0, 1, 2] and row["config_hash"] == "cfg1" and row["slice_id"]
        assert set(row["summary"]) == {"ddqn_agents", "random", "sed_global"}
        assert row["summary"]["sed_global"]["goodput_rps"]["n"] == 3
        assert set(row["paired_diff"]) == {"random", "sed_global"}  # learned vs each baseline
        # the "learned" runner here IS sed_global, so its paired difference to sed_global is 0
        assert row["paired_diff"]["sed_global"]["goodput_rps"]["mean_diff"] == 0
        assert not row["paired_diff"]["sed_global"]["goodput_rps"]["excludes_zero"]
        rel = row["replay"]["random"]
        replay = load(out, rel)
        assert replay["status"] == "ok" and replay["data"]["mode"] == "agents"
        frames = replay["data"]["frames"]
        assert 0 < len(frames) <= 200
        resolves = [r for f in frames for r in f["resolves"]]
        assert resolves and all("ttft" in r and "cost" in r for r in resolves)
        assert any(r["ttft"] is not None and r["cost"] is not None for r in resolves)
    assert rel in load(out, "manifest.json")["files"]


def test_headtohead_refuses_a_paired_folder_whose_policies_saw_different_traffic(fixture_root):
    run = make_paired_run(fixture_root)
    f = run / "random_rho0.5.json"
    doc = json.loads(f.read_text())
    doc["slice_id"] = "ffffffffffff"
    f.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="slice_id"):
        run_export(fixture_root / "results", fixture_root / "out", root=fixture_root, dt=0.1)


def test_training_export_has_one_series_per_seed(fixture_root):
    out = fixture_root / "out"
    run_export(fixture_root / "results", out, root=fixture_root, cap=50)
    d = load(out, "training.json")["data"]
    assert d["n_seeds"] == len(d["seeds"]) >= 1
    assert sorted(s["seed"] for s in d["seeds"]) == [s["seed"] for s in d["seeds"]]
    assert len(d["seeds"][0]["episodes"]) == len(d["episodes"])


def test_balance_metrics_are_derived_from_the_stored_utilisation(fixture_root):
    from scripts.export_dashboard_data import aggregate

    layout = ["fast_expensive", "slow_cheap", "fast_expensive", "slow_cheap"]
    runs = [{"utilisation": [0.9, 0.0, 0.9, 0.0]}, {"utilisation": [0.8, 0.1, 0.8, 0.1]}]
    out = aggregate(runs, ["util_fast", "util_slow", "jain_fast"])
    assert out["util_fast"]["mean"] == pytest.approx(0.85) and out["util_slow"]["mean"] == 0.05
    assert out["jain_fast"]["mean"] == pytest.approx(1.0) and len(layout) == 4


def test_behaviour_export_is_not_run_without_the_analysis_file(fixture_root):
    out = fixture_root / "out"
    run_export(fixture_root / "results", out, root=fixture_root, cap=50)
    assert load(out, "behaviour.json")["status"] == "not_run"


def test_reject_runs_and_the_shed_rule_appear_on_the_baselines_export_only_when_run(fixture_root):
    out = fixture_root / "out"
    run_export(fixture_root / "results", out, root=fixture_root, cap=50)
    d = load(out, "baselines.json")["data"]
    assert d["learned_extra"] == [] and "route_to_fast_shed" not in d["baselines"]["policies"]
    for seed in (0, 1):
        make_run(fixture_root, "e8_scratch", seed, {"eval_metrics.json": {"0.8": scaled(M, 1.5)}})
        make_run(
            fixture_root, "baselines_e8", seed,
            {"metrics.json": {"route_to_fast_shed@0.8": scaled(M, 1.2)}},
        )  # fmt: skip
    run_export(fixture_root / "results", out, root=fixture_root, cap=50)
    d = load(out, "baselines.json")["data"]
    assert [x["id"] for x in d["learned_extra"]] == ["ddqn_reject_scratch"]
    shed = d["baselines"]["policies"]["route_to_fast_shed"]["0.8"]["goodput_rps"]
    assert shed["mean"] == pytest.approx(3.0 * 1.2)
