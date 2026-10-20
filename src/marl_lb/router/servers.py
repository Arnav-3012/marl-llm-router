"""Start and stop the four real llama-servers as the profiling run did (Sh.L3, Sh.L6). Tier B.

Same models, flags, threads and slots as profiling/bench_server.py (configs/profiling.yaml), in
layout order (configs/sim.yaml): ports 8081 fast, 8082 slow, 8083 fast, 8084 slow. Process ids go to
results/live/servers.pid so stop() can end them. Used by scripts/live_servers.py and by the router's
POST /servers/start for the guided live test.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess

import httpx
import yaml

from marl_lb.config import ROOT

PIDFILE = ROOT / "results" / "live" / "servers.pid"


def plan() -> list[tuple[str, int, list[str]]]:
    """(class, port, command) per layout entry, from the profiling config (one source of truth)."""
    prof = yaml.safe_load((ROOT / "configs" / "profiling.yaml").read_text())
    layout = yaml.safe_load((ROOT / "configs" / "sim.yaml").read_text())["layout"]
    used = {c: 0 for c in prof["servers"]}
    out = []
    for cls in layout:
        spec = prof["servers"][cls]
        port = spec["ports"][used[cls]]
        used[cls] += 1
        cmd = [
            prof["llama_server_bin"],
            *["-m", str(ROOT / spec["model"])],
            *["-ngl", str(spec["n_gpu_layers"])],
            *["-t", str(spec["threads"])],
            *["-c", str(prof["ctx_size"])],
            *["-np", str(prof["parallel_slots"])],
            *["--host", prof["host"]],
            *["--port", str(port)],
        ]
        out.append((cls, port, cmd))
    return out


def running() -> list[dict]:
    return json.loads(PIDFILE.read_text()) if PIDFILE.exists() else []


def start() -> list[dict]:
    """Launch the four servers (does not wait); raises if already started or a model is missing."""
    if PIDFILE.exists():
        raise RuntimeError(f"{PIDFILE} exists: servers may already be running (stop them first)")
    for _, _, cmd in plan():
        model = cmd[cmd.index("-m") + 1]
        if not os.path.exists(model):
            raise FileNotFoundError(f"model file missing: {model}")
    PIDFILE.parent.mkdir(parents=True, exist_ok=True)
    logs = ROOT / "results" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    pids = []
    for cls, port, cmd in plan():
        proc = subprocess.Popen(
            cmd, stdout=open(logs / f"llama_{port}.log", "w"), stderr=subprocess.STDOUT
        )
        pids.append({"pid": proc.pid, "port": port, "class": cls})
    PIDFILE.write_text(json.dumps(pids))
    return pids


def healthy(port: int) -> bool:
    try:
        return httpx.get(f"http://127.0.0.1:{port}/health", timeout=2).json().get("status") == "ok"
    except (httpx.HTTPError, ValueError):
        return False


def stop() -> list[int]:
    """SIGTERM the recorded servers; returns the pids signalled."""
    done = []
    for p in running():
        try:
            os.kill(p["pid"], signal.SIGTERM)
            done.append(p["pid"])
        except ProcessLookupError:
            pass
    if PIDFILE.exists():
        PIDFILE.unlink()
    return done
