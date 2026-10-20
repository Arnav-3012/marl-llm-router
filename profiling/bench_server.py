"""Benchmark real llama-servers (TTFT, TPOT, batch scaling, prefix cache, interference). Tier B.

Writes RAW measurements only (one CSV per experiment and server class, plus meta.json); it fits
nothing. profiling/fit_calibration.py reads these CSVs. Every grid size, repeat count and server
flag comes from configs/profiling.yaml.

Run from the repo root:  uv run python -m profiling.bench_server [--smoke]

What it measures (Deep-Dive Guide H1, ADR-015):
  prefill      TTFT against prompt length P, one request alone, 1 output token  -> a
  batch        decode step time against the number of concurrent requests B     -> t0, k
  joint        TTFT and TPOT over a (P, B) grid
  cache        TTFT of "shared prefix + new text" cold vs warm                   -> cache speedup
  interference TTFT / TPOT of a probe while 0..N-1 OTHER servers are busy        -> ADR-015 option A

Prompts are sent as lists of token ids, so the prompt length is exact. TTFT and TPOT are timed on
the client from the streamed response (the server's own timings are recorded beside them).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import platform
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "profiling.yaml"
EXPERIMENTS = ["prefill", "batch", "joint", "cache", "interference"]

# --------------------------------------------------------------------------------------------
# Pure helpers (unit-tested in tests/test_bench_helpers.py)
# --------------------------------------------------------------------------------------------


def make_prompt(rng: np.random.Generator, pool: np.ndarray, n_tokens: int) -> list[int]:
    """n_tokens random token ids drawn from `pool` (ids of ordinary text, no special tokens)."""
    return rng.choice(pool, size=n_tokens, replace=True).tolist()


def ttft_and_tpot(t_send: float, token_times: list[float]) -> tuple[float, float]:
    """(TTFT, TPOT) in seconds from the send time and the arrival time of each streamed token.

    TTFT = first token - send. TPOT = mean gap between consecutive tokens after the first
    (nan with fewer than two tokens).
    """
    ttft = token_times[0] - t_send
    if len(token_times) < 2:
        return ttft, float("nan")
    return ttft, (token_times[-1] - token_times[0]) / (len(token_times) - 1)


def all_active_step_time(token_times: list[list[float]], min_tokens: int = 8) -> float:
    """Decode step time while ALL requests of one batched run are decoding, in seconds.

    The window starts when the last request has produced its first token and ends when the first
    request finishes; inside it every request emits one token per step, so
    step time = window length / tokens emitted per request in the window. This keeps prefill
    of late-starting requests, and the ramp-down, out of the TPOT used to fit t0 and k.
    Returns nan if the window holds fewer than `min_tokens` tokens per request.
    """
    start = max(t[0] for t in token_times)
    end = min(t[-1] for t in token_times)
    if end <= start:
        return float("nan")
    counts = [sum(1 for x in t if start < x <= end) for t in token_times]
    mean_count = float(np.mean(counts))
    if mean_count < min_tokens:
        return float("nan")
    return (end - start) / mean_count


def neighbour_order(own_port: int, class_ports: dict[str, list[int]], own_class: str) -> list[int]:
    """Other servers in switch-on order: same-class sibling(s) first, then the other class."""
    same = [p for p in class_ports[own_class] if p != own_port]
    other = [p for c, ports in class_ports.items() if c != own_class for p in ports]
    return same + other


# --------------------------------------------------------------------------------------------
# Talking to llama-server
# --------------------------------------------------------------------------------------------


class Server:
    """One running llama-server: its class, port and a tokeniser pool for building prompts."""

    def __init__(self, server_class: str, port: int, host: str):
        self.server_class, self.port, self.url = server_class, port, f"http://{host}:{port}"
        self.pool: np.ndarray | None = None


async def stream_completion(
    client: httpx.AsyncClient,
    server: Server,
    prompt_ids: list[int],
    n_predict: int,
    cache_prompt: bool,
) -> dict:
    """One streamed /completion call; returns timing fields. Every streamed chunk is one token."""
    body = {
        "prompt": prompt_ids,
        "n_predict": n_predict,
        "temperature": 0,
        "ignore_eos": True,  # always emit exactly n_predict tokens
        "cache_prompt": cache_prompt,
        "stream": True,
    }
    t_send = time.perf_counter()
    token_times: list[float] = []
    final: dict = {}
    async with client.stream("POST", f"{server.url}/completion", json=body) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            chunk = json.loads(line[6:])
            if chunk.get("stop"):
                final = chunk
                break
            token_times.append(time.perf_counter())
    if not token_times:
        raise RuntimeError(f"{server.url}: no tokens streamed")
    ttft, tpot = ttft_and_tpot(t_send, token_times)
    t = final.get("timings", {})
    return {
        "t_send": t_send,
        "token_times": token_times,
        "ttft_s": ttft,
        "tpot_s": tpot,
        "n_tokens": len(token_times),
        "srv_prompt_n": t.get("prompt_n"),
        "srv_cache_n": t.get("cache_n"),
        "srv_prompt_ms": t.get("prompt_ms"),
        "srv_predicted_per_token_ms": t.get("predicted_per_token_ms"),
    }


def srv_fields(r: dict) -> dict:
    return {k: r[k] for k in r if k.startswith("srv_")}


# --------------------------------------------------------------------------------------------
# Experiments. Each returns rows (list of dicts) for ONE server class.
# --------------------------------------------------------------------------------------------


class Bench:
    def __init__(self, cfg: dict, servers: dict[str, list[Server]], rng: np.random.Generator):
        self.cfg, self.servers, self.rng = cfg, servers, rng
        self.client = httpx.AsyncClient(timeout=cfg["request_timeout_s"])

    def prompt(self, server: Server, n: int) -> list[int]:
        return make_prompt(self.rng, server.pool, n)

    async def warmup(self, fn) -> None:
        """Run fn() `warmup_runs` times and throw the results away."""
        for _ in range(self.cfg["warmup_runs"]):
            await fn()

    async def batch_run(self, server: Server, b: int, p: int, n_predict: int) -> list[dict]:
        """b concurrent requests of p prompt tokens each (fresh text, no cache)."""
        prompts = [self.prompt(server, p) for _ in range(b)]
        return await asyncio.gather(
            *[
                stream_completion(self.client, server, ids, n_predict, cache_prompt=False)
                for ids in prompts
            ]
        )

    # -- a: TTFT against prompt length, one request alone, one output token ---------------------
    async def prefill(self, server: Server) -> list[dict]:
        rows = []
        for p in self.cfg["prefill_prompt_tokens"]:
            run = lambda p=p: self.batch_run(server, 1, p, 1)  # noqa: E731
            await self.warmup(run)
            for rep in range(self.cfg["repeats"]):
                (r,) = await run()
                rows.append(
                    {"prompt_tokens": p, "repeat": rep, "ttft_s": r["ttft_s"], **srv_fields(r)}
                )
        return rows

    # -- t0, k: decode step time against batch size (short prompt) -----------------------------
    async def batch(self, server: Server) -> list[dict]:
        return await self._grid(server, [self.cfg["batch_prompt_tokens"]], self.cfg["batch_sizes"])

    # -- TTFT and TPOT over prompt length x batch size ------------------------------------------
    async def joint(self, server: Server) -> list[dict]:
        return await self._grid(
            server, self.cfg["joint_prompt_tokens"], self.cfg["joint_batch_sizes"]
        )

    async def _grid(self, server: Server, prompt_lens: list[int], batch_sizes: list[int]):
        rows, n_out = [], self.cfg["decode_tokens"]
        for p in prompt_lens:
            for b in batch_sizes:
                run = lambda p=p, b=b: self.batch_run(server, b, p, n_out)  # noqa: E731
                await self.warmup(run)
                for rep in range(self.cfg["repeats"]):
                    t0 = time.perf_counter()
                    results = await run()
                    wall = time.perf_counter() - t0
                    step = all_active_step_time([r["token_times"] for r in results])
                    for i, r in enumerate(results):
                        rows.append(
                            {
                                "batch_size": b,
                                "prompt_tokens": p,
                                "repeat": rep,
                                "request": i,
                                "ttft_s": r["ttft_s"],
                                "tpot_s": r["tpot_s"],
                                "step_time_all_active_s": step,
                                "n_tokens": r["n_tokens"],
                                "run_wall_s": wall,
                                **srv_fields(r),
                            }
                        )
        return rows

    # -- prefix cache: cold vs warm -------------------------------------------------------------
    async def cache(self, server: Server) -> list[dict]:
        rows, new = [], self.cfg["cache_new_tokens"]
        for prefix_len in self.cfg["cache_prefix_tokens"]:

            async def cold(prefix_len=prefix_len):
                ids = self.prompt(server, prefix_len + new)
                return await stream_completion(self.client, server, ids, 1, cache_prompt=False)

            async def warm(prefix_len=prefix_len):
                prefix = self.prompt(server, prefix_len)
                # Prime: the server processes and keeps the prefix (+ some other tail).
                await stream_completion(
                    self.client, server, prefix + self.prompt(server, new), 1, cache_prompt=True
                )
                # Measure: same prefix, different new text.
                return await stream_completion(
                    self.client, server, prefix + self.prompt(server, new), 1, cache_prompt=True
                )

            for condition, fn in (("cold", cold), ("warm", warm)):
                await self.warmup(fn)
                for rep in range(self.cfg["repeats"]):
                    r = await fn()
                    rows.append(
                        {
                            "prefix_tokens": prefix_len,
                            "new_tokens": new,
                            "prompt_tokens": prefix_len + new,
                            "condition": condition,
                            "repeat": rep,
                            "ttft_s": r["ttft_s"],
                            **srv_fields(r),
                        }
                    )
        return rows

    # -- interference: probe one server while n OTHER servers run a closed loop ------------------
    async def interference(self, target: Server) -> list[dict]:
        cfg = self.cfg
        class_ports = {c: [s.port for s in ss] for c, ss in self.servers.items()}
        by_port = {s.port: s for ss in self.servers.values() for s in ss}
        order = neighbour_order(target.port, class_ports, target.server_class)
        rows = []
        for n_busy in cfg["interference_levels"]:
            busy = [by_port[p] for p in order[:n_busy]]
            stop = asyncio.Event()
            done = {s.port: 0 for s in busy}

            async def loop(s: Server, stop=stop, done=done):
                while not stop.is_set():
                    ids = self.prompt(s, cfg["interference_background_prompt_tokens"])
                    await stream_completion(
                        self.client, s, ids, cfg["decode_tokens"], cache_prompt=False
                    )
                    done[s.port] += 1

            tasks = [asyncio.create_task(loop(s)) for s in busy]
            await asyncio.sleep(cfg["interference_settle_s"])
            probes = (
                ("prefill", cfg["interference_probe_prefill_tokens"], 1),
                ("decode", cfg["interference_probe_decode_prompt_tokens"], cfg["decode_tokens"]),
            )
            for name, p, n_out in probes:
                run = lambda p=p, n_out=n_out: self.batch_run(target, 1, p, n_out)  # noqa: E731
                await self.warmup(run)
                for rep in range(cfg["repeats"]):
                    (r,) = await run()
                    rows.append(
                        {
                            "n_other_busy": n_busy,
                            "busy_ports": " ".join(str(s.port) for s in busy),
                            "probe": name,
                            "prompt_tokens": p,
                            "repeat": rep,
                            "ttft_s": r["ttft_s"],
                            "tpot_s": r["tpot_s"],
                            "n_tokens": r["n_tokens"],
                            **srv_fields(r),
                        }
                    )
            stop.set()
            await asyncio.gather(*tasks, return_exceptions=True)
            for row in rows:  # background requests finished while this level ran
                if row["n_other_busy"] == n_busy:
                    row["bg_requests_completed"] = sum(done.values())
        return rows


# --------------------------------------------------------------------------------------------
# Server processes and machine info
# --------------------------------------------------------------------------------------------


def server_command(cfg: dict, spec: dict, port: int) -> list[str]:
    return [
        cfg["llama_server_bin"],
        "-m", str(ROOT / spec["model"]),
        "-ngl", str(spec["n_gpu_layers"]),
        "-t", str(spec["threads"]),
        "-c", str(cfg["ctx_size"]),
        "-np", str(cfg["parallel_slots"]),
        "--host", cfg["host"],
        "--port", str(port),
    ]  # fmt: skip


def start_servers(cfg: dict, run_dir: Path) -> tuple[dict[str, list[Server]], list, dict]:
    """Start every configured llama-server; return Server objects, processes and the commands."""
    servers: dict[str, list[Server]] = {}
    procs, commands = [], {}
    for cls, spec in cfg["servers"].items():
        servers[cls] = []
        for port in spec["ports"]:
            cmd = server_command(cfg, spec, port)
            log = open(run_dir / f"llama_server_{cls}_{port}.log", "w")  # noqa: SIM115
            procs.append(subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT))
            commands[f"{cls}:{port}"] = cmd
            servers[cls].append(Server(cls, port, cfg["host"]))
    return servers, procs, commands


async def wait_healthy(servers: dict[str, list[Server]], timeout_s: float = 300) -> None:
    deadline = time.time() + timeout_s
    async with httpx.AsyncClient(timeout=5) as c:
        for s in [s for ss in servers.values() for s in ss]:
            while True:
                try:
                    if (await c.get(f"{s.url}/health")).json().get("status") == "ok":
                        break
                except (httpx.HTTPError, ValueError):
                    pass
                if time.time() > deadline:
                    raise RuntimeError(f"{s.url} not healthy after {timeout_s}s")
                await asyncio.sleep(1)


async def build_pools(cfg: dict, servers: dict[str, list[Server]]) -> None:
    """Token-id pool per server: tokenise pseudo-random syllable text once (seeded)."""
    rng = np.random.default_rng(cfg["seed"])
    cons, vowels = list("bcdfghjklmnprstvwz"), list("aeiou")
    words = [
        "".join(rng.choice(cons) + rng.choice(vowels) for _ in range(int(rng.integers(1, 4))))
        for _ in range(6000)
    ]
    text = " ".join(words)
    async with httpx.AsyncClient(timeout=60) as c:
        for ss in servers.values():
            for s in ss:
                r = await c.post(f"{s.url}/tokenize", json={"content": text, "add_special": False})
                s.pool = np.array(r.json()["tokens"], dtype=np.int64)


def sh(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def machine_info(cfg: dict, commands: dict) -> dict:
    """Chip, RAM, OS, llama.cpp version, model files (size + sha256), flags, power state."""
    models = {}
    for cls, spec in cfg["servers"].items():
        path = ROOT / spec["model"]
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(1 << 24), b""):
                h.update(block)
        models[cls] = {"file": spec["model"], "bytes": path.stat().st_size, "sha256": h.hexdigest()}
    return {
        "chip": sh(["sysctl", "-n", "machdep.cpu.brand_string"]),
        "ram_bytes": int(sh(["sysctl", "-n", "hw.memsize"]) or 0),
        "cpu_cores_performance": sh(["sysctl", "-n", "hw.perflevel0.physicalcpu"]),
        "cpu_cores_efficiency": sh(["sysctl", "-n", "hw.perflevel1.physicalcpu"]),
        "macos": sh(["sw_vers", "-productVersion"]),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "llama_server_path": shutil.which(cfg["llama_server_bin"]),
        "llama_server_version": sh([cfg["llama_server_bin"], "--version"]),
        "models": models,
        "ctx_size_total": cfg["ctx_size"],
        "parallel_slots": cfg["parallel_slots"],
        "ctx_per_slot": cfg["ctx_size"] // cfg["parallel_slots"],
        "server_commands": commands,
        "power": sh(["pmset", "-g", "batt"]).splitlines()[:2],
        "low_power_mode": [ln for ln in sh(["pmset", "-g"]).splitlines() if "lowpowermode" in ln],
        "repo_commit": sh(["git", "-C", str(ROOT), "rev-parse", "HEAD"]),
    }


# --------------------------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------------------------


async def run_all(cfg: dict, run_dir: Path, experiments: list[str]) -> dict:
    servers, procs, commands = start_servers(cfg, run_dir)
    meta = {"started": datetime.now().isoformat(timespec="seconds"), "timings_s": {}}
    t_start = time.perf_counter()
    try:
        await wait_healthy(servers)
        await build_pools(cfg, servers)
        meta["machine"] = machine_info(cfg, commands)
        bench = Bench(cfg, servers, np.random.default_rng(cfg["seed"] + 1))
        counts = {}
        for exp in experiments:
            t0 = time.perf_counter()
            for cls, ss in servers.items():
                rows = await getattr(bench, exp)(
                    ss[0]
                )  # the first server of each class is the target
                df = pd.DataFrame(rows)
                df.insert(0, "server_class", cls)
                df.insert(1, "port", ss[0].port)
                df.to_csv(run_dir / f"{exp}_{cls}.csv", index=False)
                counts[f"{exp}_{cls}"] = len(df)
                print(f"{exp:13s} {cls:14s} {len(df):5d} rows  {time.perf_counter() - t0:7.1f}s")
            meta["timings_s"][exp] = round(time.perf_counter() - t0, 1)
        meta["row_counts"] = counts
        await bench.client.aclose()
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=20)
            except subprocess.TimeoutExpired:
                p.kill()
        meta["finished"] = datetime.now().isoformat(timespec="seconds")
        meta["wall_s"] = round(time.perf_counter() - t_start, 1)
    return meta


def load_config(path: Path, smoke: bool, quick: bool = False) -> dict:
    cfg = yaml.safe_load(Path(path).read_text())
    if smoke:
        cfg.update(cfg["smoke"])
    elif quick:
        cfg.update(cfg["quick"])
    return cfg


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--smoke", action="store_true", help="tiny grids from the config's smoke block")
    ap.add_argument(
        "--quick", action="store_true", help="5 repeats, 1 warm-up (config quick block)"
    )
    ap.add_argument("--only", default=",".join(EXPERIMENTS), help="comma list of experiments")
    args = ap.parse_args()
    cfg = load_config(args.config, args.smoke, args.quick)
    experiments = [e for e in args.only.split(",") if e]
    unknown = set(experiments) - set(EXPERIMENTS)
    if unknown:
        raise SystemExit(f"unknown experiment(s) {sorted(unknown)}; choose from {EXPERIMENTS}")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = "_smoke" if args.smoke else "_quick" if args.quick else ""
    run_dir = ROOT / cfg["output_root"] / f"{stamp}_seed{cfg['seed']}{suffix}"
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "config_resolved.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    meta = asyncio.run(run_all(cfg, run_dir, experiments))
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"run dir: {run_dir}\nwall time: {meta['wall_s']} s")


if __name__ == "__main__":
    main()
