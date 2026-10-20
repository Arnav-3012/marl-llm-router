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
