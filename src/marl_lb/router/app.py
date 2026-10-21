"""FastAPI router app: chat and simulate through a policy onto llama-servers (or mocks). Tier B.

127.0.0.1 only. GET /health (readiness), POST /chat, POST /simulate (replay a held-out slice),
GET /simulate/status, POST /simulate/stop, GET /state, GET /runs, GET /runs/{id},
GET /runs/{id}/frames. Every simulate run writes results/live/<run_id>/ (Sh.L2). Mock mode runs the
same code against in-process mock servers (time scaled down); real mode needs four llama-servers.

  uv run python -m marl_lb.router.app --mock [--time-scale 0.01] [--port 8000]
  uv run python -m marl_lb.router.app --ports 8081,8082,8083,8084 [--agents-exp e8_mix]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from marl_lb.config import ROOT
from marl_lb.data.load import load_lambda_sat
from marl_lb.eval.evaluate import World
from marl_lb.eval.frames import frames_from_events
from marl_lb.router import servers as llama_servers
from marl_lb.router.events import EventLog
from marl_lb.router.factory import POLICIES, build_policy
from marl_lb.router.livecheck import LiveCheck
from marl_lb.router.mock import MockLlamaServer
from marl_lb.router.observation import LiveCluster
from marl_lb.router.policy_router import PolicyRouter
from marl_lb.router.runs import SimulationRun, make_slice
from marl_lb.router.server_client import HttpTransport, InProcessTransport, LlamaClient
from marl_lb.sim.request import Request

REAL_LAMBDA_FILE = "real_lambda_sat.json"


@dataclass
class Backend:
    name: str
    class_name: str
    url: str


@dataclass
class Settings:
    mode: str = "mock"  # mock | real
    time_scale: float = 0.01  # mock only: service and arrival times are multiplied by this
    ports: list = field(default_factory=list)  # real mode: one llama-server port per layout entry
    agents_exp: str | None = "e8_mix"
    adaptive: bool = False  # ADR-039: measure real server speeds and correct wait estimates
    robust_exp: str | None = None  # ADR-038 agents trained on random slowdowns
    live_root: Path = ROOT / "results" / "live"
    host: str = "127.0.0.1"


class ChatBody(BaseModel):
    prompt: str
    n_predict: int = 64
    policy: str = "sed_local_full"


class SimBody(BaseModel):
    policy: str = "sed_global"
    rho: float | None = None
    rate_rps: float | None = None
    seconds: float = 60.0
    seed: int = 0
    drain_s: float | None = None


class CheckBody(BaseModel):
    seconds: float = 60.0
    rho: float = 0.8
    seed: int = 0
    policies: list[str] = ["sed_global", "route_to_fast_shed", "ddqn_agents"]
    capacity: str = "auto"  # auto: reuse the measured capacity, measure it quickly if missing
    rate_rps: float | None = None  # a fixed arrival rate: skips the capacity step (overload demo)
    drain_s: float | None = None  # stop waiting this long after the last arrival (quick demos)
    rates: list[float] | None = None  # the full showdown: one round per rate (req/s)


class State:
    """Everything the endpoints share; built lazily (the world loads the trace)."""

    def __init__(self, settings: Settings):
        self.s = settings
        self._world: World | None = None
        self.current: SimulationRun | None = None
        self.task: asyncio.Task | None = None
        self.chat_routers: dict = {}
        self.chat_id = 0
        self.n_runs = 0
        self.check = None
        self.scale = settings.time_scale if settings.mode == "mock" else 1.0
        self._build_backends()

    @property
    def world(self) -> World:
        if self._world is None:
            self._world = World()
        return self._world

    def _build_backends(self) -> None:
        layout = yaml.safe_load((ROOT / "configs" / "sim.yaml").read_text())["layout"]
        calib_path = os.environ.get("MARL_CALIBRATION", "profiling/calibration.json")  # ADR-037
        calib = json.loads((ROOT / calib_path).read_text())["classes"]
        if self.s.mode == "mock":
            mocks = {
                f"mock://{i}": MockLlamaServer(calib[c], self.s.time_scale, f"m{i}")
                for i, c in enumerate(layout)
            }
            self.backends = [
                Backend(f"server{i}", c, u)
                for i, (c, u) in enumerate(zip(layout, mocks, strict=True))
            ]
            self.transport = InProcessTransport(mocks)
        else:
            if len(self.s.ports) != len(layout):
                raise ValueError(
                    f"real mode needs {len(layout)} ports (the layout), got {self.s.ports}"
                )
            self.backends = [
                Backend(f"server{i}", c, f"http://127.0.0.1:{p}")
                for i, (c, p) in enumerate(zip(layout, self.s.ports, strict=True))
            ]
            self.transport = HttpTransport()
        self.client = LlamaClient(self.transport)

    def lambda_sat(self) -> float:
        if self.s.mode == "mock":
            return load_lambda_sat()  # the simulator's: mock runs only rehearse the plumbing
        f = self.s.live_root / REAL_LAMBDA_FILE
        if not f.exists():
            raise HTTPException(
                409, "real capacity not measured yet: run scripts/live_capacity_probe.py (Sh.L3)"
            )
        return float(json.loads(f.read_text())["lambda_sat_rps"])

    def busy(self) -> bool:
        return bool(
            (self.current and self.current.state == "running")
            or (self.check and self.check.state == "running")
        )

    def make_run(
        self,
        policy: str,
        seed: int,
        seconds: float,
        rho: float | None = None,
        rate_rps: float | None = None,
        drain_s: float | None = None,
    ) -> tuple[SimulationRun, float]:
        """A ready-to-run replay of the held-out slice (seconds of real run time) and its rate."""
        rate = rate_rps if rate_rps is not None else rho * self.lambda_sat()
        router = self.new_router(policy, seed)
        stream = make_slice(self.world, rate, seed, seconds / self.scale)
        self.n_runs += 1
        run_id = f"{datetime.now():%Y%m%d-%H%M%S}_{self.n_runs:03d}_{policy}_seed{seed}"
        cfg = {
            "policy": policy,
            "rho": rho,
            "rate_rps": rate,
            "seed": seed,
            "seconds": seconds,
            "mode": self.s.mode,
            "time_scale": self.scale,
            "agents_exp": {"ddqn_agents": self.s.agents_exp, "ddqn_robust": self.s.robust_exp}.get(
                policy
            ),
            "layout": self.world.params.layout,
        }
        run = SimulationRun(
            run_id,
            router,
            stream,
            cfg,
            self.s.live_root,
            self.world.params.ttft_target,
            self.world.params.tpot_target,
            self.scale,
            0.1 * self.scale,
            salt=int(time.time()) % 100000 + self.n_runs,
            drain_s=drain_s,
        )
        return run, rate

    def new_router(self, policy_name: str, seed: int) -> PolicyRouter:
        world = self.world
        try:
            policy, params = build_policy(
                policy_name, world, self.s.agents_exp, seed, self.s.robust_exp
            )
        except (ValueError, FileNotFoundError) as e:
            raise HTTPException(400, str(e)) from e
        cluster = LiveCluster(
            params, world.calib["classes"], world.est_output_tokens, self.s.adaptive
        )
        dt = params.dt * self.scale
        return PolicyRouter(
            self.backends,
            cluster,
            policy,
            self.client,
            time.perf_counter,
            EventLog(dt=0.1 * self.scale),
            seed=seed,
            decision_dt=dt,
        )


def create_app(settings: Settings | None = None) -> FastAPI:
    st = State(settings or Settings())
    app = FastAPI(title="marl-llm-router (live)", docs_url=None, redoc_url=None)
    app.state.st = st
    # the dashboard (a static site on another local port) reads this API: allow local origins only
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health():
        up = [await st.client.health(b.url) for b in st.backends]
        return {
            "status": "ok" if all(up) else "degraded",
            "mode": st.s.mode,
            "time_scale": st.scale,
            "backends": [
                {"name": b.name, "class": b.class_name, "url": b.url, "up": u}
                for b, u in zip(st.backends, up, strict=True)
            ],
            "policies": POLICIES,
            "adaptive": st.s.adaptive,
            "running": st.current.run_id if st.current and st.current.state == "running" else None,
        }

    @app.post("/chat")
    async def chat(body: ChatBody):
        if body.policy not in POLICIES:
            raise HTTPException(400, f"unknown policy; choose from {POLICIES}")
        router = st.chat_routers.get(body.policy)
        if router is None:
            router = st.chat_routers[body.policy] = st.new_router(body.policy, 0)
        st.chat_id += 1
        n_prompt = max(
            1, len(body.prompt) // 4
        )  # a rough token count, only used for the observation
        req = Request(
            st.chat_id,
            0.0,
            n_prompt,
            body.n_predict,
            st.chat_id,
            0,
            False,
            st.world.params.ttft_target,
            st.world.params.tpot_target,
        )
        out = await router.handle(req, body.prompt, body.n_predict)
        if out.status == "dropped":  # the policy chose Reject: a normal outcome, not an error
            return {
                "refused": True,
                "policy": body.policy,
                "actions": out.actions,
                "hops": req.hops,
            }
        if out.status != "done":
            raise HTTPException(
                503, f"request {out.status}: the policy refused it or the server failed"
            )
        b = st.backends[out.server]
        c = out.completion
        return {
            "text": c.text,
            "server": b.name,
            "class": b.class_name,
            "policy": body.policy,
            "ttft_s": c.ttft_s,
            "tpot_s": c.tpot_s,
            "n_tokens": c.n_tokens,
            "actions": out.actions,
            "hops": req.hops,
            "time_scale": st.scale,
        }

    @app.post("/simulate")
    async def simulate(body: SimBody):
        if st.busy():
            raise HTTPException(409, "a run or a live test is still going")
        if body.rho is None and body.rate_rps is None:
            raise HTTPException(400, "give rho (of the real capacity) or rate_rps")
        run, rate = st.make_run(
            body.policy, body.seed, body.seconds, body.rho, body.rate_rps, body.drain_s
        )
        st.current = run
        st.task = asyncio.create_task(run.run())
        return {"run_id": run.run_id, "rate_rps": rate, "n_requests": len(run.stream)}

    @app.get("/simulate/status")
    async def status():
        r = st.current
        if r is None:
            return {"state": "idle"}
        return {
            "state": r.state,
            "run_id": r.run_id,
            "sent": r.sent,
            "of": len(r.stream),
            "resolved": len(r.router.resolved),
            "metrics": r.metrics,
        }

    @app.post("/simulate/stop")
    async def stop():
        if st.current and st.current.state == "running":
            st.current.stop()
        return {"state": st.current.state if st.current else "idle"}

    @app.post("/livecheck/start")
    async def livecheck_start(body: CheckBody):
        if st.busy():
            raise HTTPException(409, "a run or a live test is still going")
        for p in body.policies:
            if p not in POLICIES:
                raise HTTPException(400, f"unknown policy {p!r}")
        st.check = LiveCheck(st)
        st.check.task = asyncio.create_task(st.check.run(body.model_dump()))
        return {"state": "running"}

    @app.get("/livecheck/status")
    async def livecheck_status(since: int = 0):
        c = st.check
        if c is None:
            return {"state": "idle", "messages": [], "rows": [], "current_run": None}
        return {
            "state": c.state,
            "messages": c.messages[since:],
            "n": len(c.messages),
            "rows": c.rows,
            "current_run": c.current_run,
            "opts": c.opts,
        }

    @app.post("/livecheck/stop")
    async def livecheck_stop():
        if st.check:
            st.check.stop()
        return {"state": st.check.state if st.check else "idle"}

    @app.get("/servers")
    async def servers_state():
        procs = llama_servers.running()
        return {
            "mode": st.s.mode,
            "recorded": procs,
            "healthy": [llama_servers.healthy(p["port"]) for p in procs],
        }

    @app.post("/servers/start")
    async def servers_start():
        if st.s.mode != "real":
            raise HTTPException(400, "mock mode has no real servers to start")
        try:
            return {"started": llama_servers.start()}
        except (RuntimeError, FileNotFoundError) as e:
            raise HTTPException(409, str(e)) from e

    @app.post("/servers/stop")
    async def servers_stop():
        if st.s.mode != "real":
            raise HTTPException(400, "mock mode has no real servers to stop")
        return {"stopped": llama_servers.stop()}

    @app.get("/state")
    async def state():
        r = st.current
        servers = r.router.cluster.servers if r else []
        return {
            "servers": [
                {
                    "name": b.name,
                    "class": b.class_name,
                    "queue": len(s.queue),
                    "active": len(s.active),
                    "kv": round(s.kv_fullness(), 3),
                    "completed": s.completed,
                    "busy_s": round(s.busy_seconds, 3),
                }
                for b, s in zip(st.backends, servers, strict=False)
            ],
            "run": r.run_id if r else None,
            "state": r.state if r else "idle",
        }

    def run_dir(run_id: str) -> Path:
        d = st.s.live_root / run_id
        if not d.exists():
            raise HTTPException(404, "no such run")
        return d

    @app.get("/runs")
    async def runs():
        out = []
        for d in sorted(st.s.live_root.glob("*/DONE")):
            cfg = yaml.safe_load((d.parent / "config.yaml").read_text())
            out.append(
                {"run_id": d.parent.name, "policy": cfg.get("policy"), "seed": cfg.get("seed")}
            )
        return out

    @app.get("/runs/{run_id}")
    async def run_info(run_id: str):
        d = run_dir(run_id)
        return {
            "config": yaml.safe_load((d / "config.yaml").read_text()),
            "slice": json.loads((d / "slice.json").read_text()),
            "metrics": json.loads((d / "metrics.json").read_text()),
            "machine": json.loads((d / "machine.json").read_text()),
        }

    @app.get("/events")
    async def event_stream():
        """Server-sent events of the current run (the simulator's event schema), until it ends."""

        async def gen():
            idx = 0
            while True:
                run = st.current
                evs = run.router.events.since(idx) if run else []
                for e in evs:
                    yield f"data: {json.dumps(e, default=float)}\n\n"
                idx += len(evs)
                if run is None or (run.state not in ("new", "running") and not evs):
                    yield "event: end\ndata: {}\n\n"
                    return
                await asyncio.sleep(0.1)

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.get("/runs/{run_id}/events")
    async def run_events(run_id: str):
        if st.current and st.current.run_id == run_id and st.current.state == "running":
            return {"events": list(st.current.router.events.events), "done": False}
        lines = (run_dir(run_id) / "events.jsonl").read_text().splitlines()
        return {"events": [json.loads(line) for line in lines], "done": True}

    @app.get("/runs/{run_id}/frames")
    async def frames(run_id: str, since: int = -1, cap: int = 600):
        if st.current and st.current.run_id == run_id and st.current.state == "running":
            events = list(st.current.router.events.events)
        else:
            events = [
                json.loads(line)
                for line in (run_dir(run_id) / "events.jsonl").read_text().splitlines()
            ]
        out = frames_from_events(events, 0.1 * st.scale, cap)
        return {"frames": [f for f in out if f["tick"] > since], "dt": 0.1 * st.scale}

    return app


def main() -> None:
    import uvicorn

    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--time-scale", type=float, default=0.01)
    ap.add_argument("--ports", default="", help="real mode: llama-server ports in layout order")
    ap.add_argument("--agents-exp", default="e8_mix")
    ap.add_argument(
        "--adaptive",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="ADR-039: correct wait estimates with live speeds (default on in real mode)",
    )
    ap.add_argument("--robust-exp", default=None, help="ADR-038 robust agents, e.g. e8_robust")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    settings = Settings(
        "mock" if a.mock else "real",
        a.time_scale,
        [int(p) for p in a.ports.split(",") if p],
        a.agents_exp,
        robust_exp=a.robust_exp,
        adaptive=(not a.mock) if a.adaptive is None else a.adaptive,
    )
    uvicorn.run(create_app(settings), host="127.0.0.1", port=a.port, log_level="info")


if __name__ == "__main__":
    main()
