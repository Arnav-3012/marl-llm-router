"""Capacity probe criteria, rehearsal check and server plan (Sh.L3, Sh.L6), on the mock router."""

import pytest
from fastapi.testclient import TestClient
from scripts.demo_check import check
from scripts.live_capacity_probe import Probe, criteria_from_events

from marl_lb.router.app import Settings, create_app
from marl_lb.router.servers import plan


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    root = tmp_path_factory.mktemp("live")
    with TestClient(create_app(Settings("mock", 0.01, live_root=root, agents_exp=None))) as c:
        c.root = root
        yield c


def events(n, finish_after, window=100.0, status="done"):
    out = []
    for i in range(n):
        t = i * window / n
        out.append({"e": "arrive", "req": i, "t": t})
        out.append({"e": "resolve", "req": i, "t": t + finish_after, "status": status})
    return out


def test_criteria_pass_for_a_cluster_that_keeps_up_and_fail_for_one_that_falls_behind():
    ok = criteria_from_events(events(100, 1.0), 100.0)
    assert ok["completion_ratio"] == 1.0 and ok["drop_rate"] == 0 and ok["backlog_ratio"] <= 1.5
    late = criteria_from_events(events(100, 400.0), 100.0)  # nothing finishes inside the window
    assert late["completion_ratio"] == 0.0 and late["backlog_ratio"] > 1.5
    drops = criteria_from_events(events(100, 1.0, status="dropped"), 100.0)
    assert drops["drop_rate"] == 1.0


def test_probe_runs_one_point_through_the_api_and_reports_the_three_criteria(client):
    probe = Probe(client, window_s=1.0, seeds=[0], poll_s=0.1)
    point = probe.evaluate(0.3)
    assert set(point) == {"completion_ratio", "drop_rate", "backlog_ratio"}
    assert len(probe.points) == 1 and probe.points[0]["run_id"]


def test_demo_check_is_ready_against_the_mock_and_says_it_is_a_mock(client):
    ok, msg = check(client, seconds=1.0, rho=0.5, live_root=client.root, poll_s=0.1)
    assert ok and msg.startswith("READY") and "MOCK" in msg


def test_demo_check_explains_why_it_is_not_ready():
    class Down:
        def get(self, url):
            class R:
                def json(self):
                    return {
                        "backends": [
                            {"name": "server2", "up": False},
                            {"name": "server0", "up": True},
                        ]
                    }

            return R()

    ok, msg = check(Down())
    assert not ok and msg.startswith("NOT READY") and "server2" in msg

    class Dead:
        def get(self, url):
            raise ConnectionError("refused")

    ok, msg = check(Dead())
    assert not ok and "does not answer" in msg


def test_server_plan_matches_the_profiling_setup_in_layout_order():
    p = plan()
    assert [c for c, _, _ in p] == ["fast_expensive", "slow_cheap", "fast_expensive", "slow_cheap"]
    assert [port for _, port, _ in p] == [8081, 8082, 8083, 8084]
    fast, slow = p[0][2], p[1][2]
    assert fast[fast.index("-ngl") + 1] == "99" and slow[slow.index("-ngl") + 1] == "0"
    assert all("--host" in cmd and cmd[cmd.index("--host") + 1] == "127.0.0.1" for _, _, cmd in p)


def test_demo_live_prints_the_numbers_the_recorded_results_hold_for_the_same_slice():
    import glob
    import json

    from scripts.demo_live import run_policy

    from marl_lb.config import ROOT

    files = sorted(glob.glob(str(ROOT / "results" / "baselines_v2" / "*_seed0" / "metrics.json")))
    if not files:
        pytest.skip("no recorded baselines in this checkout")
    stored = json.loads(open(files[-1]).read())["sed_global@0.5"]
    live = run_policy("sed", 0.5, 0)
    for key in ("goodput_rps", "sla_attainment", "drop_rate", "ttft_p95", "cost_per_request"):
        assert live[key] == pytest.approx(stored[key])


def test_fill_presentation_writes_only_between_its_markers_and_never_invents(tmp_path):
    import json

    from scripts.fill_presentation import layout_block, live_block, numbers_block, splice

    data = tmp_path / "data"
    data.mkdir()
    assert "not been run" in layout_block(data) and "no real-server run" in live_block(data)
    assert "not exported" in numbers_block(data)
    f = tmp_path / "p.md"
    f.write_text("keep this\n<!-- AUTO:live -->\nold\n<!-- /AUTO:live -->\nand this\n")
    live = {
        "runs": [
            {
                "policy": "sed_global",
                "metrics": {"goodput_rps": 0.3, "sla_attainment": 0.9, "drop_rate": 0.0},
            }
        ],
        "capacity": {"lambda_sat_rps": 0.5, "quick": True},
    }
    (data / "live.json").write_text(json.dumps({"status": "ok", "data": live}))
    splice(f, "live", live_block(data))
    text = f.read_text()
    assert text.startswith("keep this\n") and text.endswith("and this\n") and "old" not in text
    assert "0.50 req/s" in text and "anecdote" in text
    splice(f, "live", live_block(data))  # idempotent
    assert f.read_text() == text
