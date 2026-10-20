"""Live router app in mock mode (Sh.L1, Sh.L2): health, chat, simulate, run folder, frames."""

import time

import pytest
from fastapi.testclient import TestClient

from marl_lb.router.app import Settings, create_app

SCALE = 0.01


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    root = tmp_path_factory.mktemp("live")
    app = create_app(Settings("mock", SCALE, live_root=root, agents_exp=None))
    with TestClient(app) as c:
        c.root = root
        yield c


def wait_done(c, timeout=90):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = c.get("/simulate/status").json()
        if s["state"] in ("done", "stopped"):
            return s
        time.sleep(0.2)
    raise AssertionError("run did not finish")


def test_health_lists_the_four_backends_and_the_policies(client):
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["mode"] == "mock" and len(h["backends"]) == 4
    assert {b["class"] for b in h["backends"]} == {"fast_expensive", "slow_cheap"}
    assert "sed_global" in h["policies"] and "ddqn_agents" in h["policies"]


def test_chat_goes_through_a_policy_and_reports_the_server_and_timings(client):
    r = client.post("/chat", json={"prompt": "Hello there, how are you today?", "n_predict": 6,
                                   "policy": "sed_local_full"})  # fmt: skip
    assert r.status_code == 200
    j = r.json()
    assert j["n_tokens"] == 6 and j["server"].startswith("server") and j["ttft_s"] > 0
    assert client.post("/chat", json={"prompt": "x", "policy": "nope"}).status_code == 400


def test_a_learned_policy_without_weights_is_refused_clearly(client):
    r = client.post("/chat", json={"prompt": "hi", "policy": "ddqn_agents"})
    assert r.status_code == 400 and "agents experiment" in r.json()["detail"]


def test_simulate_runs_a_slice_and_writes_the_run_folder(client):
    r = client.post(
        "/simulate", json={"policy": "sed_global", "rho": 0.5, "seconds": 1.5, "seed": 0}
    )
    assert r.status_code == 200 and r.json()["n_requests"] > 5
    assert client.post("/simulate", json={"policy": "random", "rho": 0.5}).status_code == 409
    s = wait_done(client)
    run_id = s["run_id"]
    d = client.root / run_id
    for name in (
        "config.yaml",
        "slice.json",
        "events.jsonl",
        "metrics.json",
        "machine.json",
        "DONE",
    ):
        assert (d / name).exists(), name
    info = client.get(f"/runs/{run_id}").json()
    m = info["metrics"]
    assert m["n_arrived"] == info["slice"]["requests_sent"] and m["n_completed"] > 0
    assert m["time_scale"] == SCALE and 0 <= m["sla_attainment"] <= 1 and m["goodput_rps"] > 0
    assert info["config"]["policy"] == "sed_global" and info["slice"]["slice_id"]
    frames = client.get(f"/runs/{run_id}/frames").json()["frames"]
    assert frames and {"t", "queue", "arrivals", "resolves"} <= set(frames[-1])
    assert any(f["resolves"] for f in frames)
    assert run_id in [x["run_id"] for x in client.get("/runs").json()]
    assert client.get("/runs/nope").status_code == 404


def test_the_same_slice_and_seed_gives_the_same_slice_id_for_two_policies(client):
    ids = []
    for pol in ("random", "route_to_fast"):
        client.post("/simulate", json={"policy": pol, "rho": 0.5, "seconds": 1.0, "seed": 3})
        s = wait_done(client)
        ids.append(client.get(f"/runs/{s['run_id']}").json()["slice"]["slice_id"])
    assert ids[0] == ids[1]


def test_real_mode_without_a_measured_capacity_refuses_rho(tmp_path):
    app = create_app(Settings("mock", SCALE, live_root=tmp_path, agents_exp=None))
    st = app.state.st
    st.s.mode = "real"  # only the capacity lookup is exercised
    with pytest.raises(Exception, match="capacity not measured"):
        st.lambda_sat()


def test_the_event_stream_delivers_the_run_events_in_the_simulator_schema(client):
    import json

    client.post("/simulate", json={"policy": "random", "rho": 0.5, "seconds": 1.0, "seed": 1})
    kinds = set()
    with client.stream("GET", "/events") as r:
        for line in r.iter_lines():
            if line.startswith("data: ") and line != "data: {}":
                e = json.loads(line[6:])
                assert {"tick", "t", "e"} <= set(e)
                kinds.add(e["e"])
            if line.startswith("event: end"):
                break
    assert {"arrive", "act", "resolve", "servers"} <= kinds
    wait_done(client)


def test_the_guided_live_test_narrates_runs_two_policies_on_one_slice_and_reports(client):
    r = client.post("/livecheck/start", json={"seconds": 1.0, "rho": 0.5, "seed": 2,
                                              "policies": ["random", "route_to_fast"]})  # fmt: skip
    assert r.status_code == 200
    assert client.post("/livecheck/start", json={"policies": ["random"]}).status_code == 409
    assert client.post("/simulate", json={"policy": "random", "rho": 0.5}).status_code == 409
    t0 = time.time()
    while time.time() - t0 < 120:
        s = client.get("/livecheck/status").json()
        if s["state"] in ("done", "failed", "stopped"):
            break
        time.sleep(0.3)
    assert s["state"] == "done", s["messages"][-3:]
    text = " ".join(m["text"] for m in s["messages"])
    for phrase in (
        "Checking the four servers",
        "Run 1 of 2",
        "Run 2 of 2",
        "same requests",
        "anecdote",
    ):
        assert phrase in text, phrase
    assert "MOCK" in text and len(s["rows"]) == 2 and s["rows"][0]["slice"] == s["rows"][1]["slice"]
    assert all(m["kind"] in ("info", "ok", "warn", "error") for m in s["messages"])
    part = client.get(f"/livecheck/status?since={s['n'] - 1}").json()["messages"]
    assert len(part) == 1  # polling with `since` returns only the new messages
    assert client.post("/servers/start").status_code == 400  # mock mode has no real servers


def test_the_guided_live_test_can_be_stopped(client):
    client.post(
        "/livecheck/start", json={"seconds": 30.0, "rho": 0.5, "policies": ["random", "sed_global"]}
    )
    time.sleep(1.5)
    client.post("/livecheck/stop")
    t0 = time.time()
    while time.time() - t0 < 60:
        s = client.get("/livecheck/status").json()
        if s["state"] != "running":
            break
        time.sleep(0.3)
    assert s["state"] == "stopped"
