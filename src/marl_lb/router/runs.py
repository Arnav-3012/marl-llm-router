"""Live runs: synthetic prompts, replay of a held-out slice, metrics and the run folder. Tier B.

A run replays a seeded held-out slice through a PolicyRouter against real (or mock) servers: each
request is sent at its arrival time with a synthetic prompt of the recorded prompt length and the
recorded output length as the token budget. Everything a run produces goes to
results/live/<run_id>/ (config, slice id, seed, policy, machine metadata, event log, metrics).
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
from datetime import datetime
from pathlib import Path

import numpy as np
import yaml

from marl_lb.eval.paired import stream_id
from marl_lb.sim.cluster import slice_stream
from marl_lb.sim.request import Request


def synth_prompt(salt: int, conv_id: int, turn: int, history_included: bool, n: int) -> list[int]:
    """Token ids for a request of n tokens. A turn that re-sends its history draws from its
    conversation's stream, so later turns share the earlier prefix (prefix-cache behaviour); other
    turns get their own stream. `salt` differs per run so one run never warms the next one's cache.
    """
    key = conv_id if history_included else conv_id * 1000 + turn + 1
    rng = np.random.default_rng([salt, key])
    return rng.integers(1000, 30000, size=n).tolist()


def percentile(values, q: float) -> float | None:
    return float(np.percentile(values, q)) if len(values) else None


def live_metrics(resolved: list, servers: list, window_s: float, episode_s: float) -> dict:
    """The simulator's headline metrics from a finished live run (same definitions)."""
    done = [r for r in resolved if r.status == "done"]
    met = [r for r in done if r.sla_met()]
    n = max(len(resolved), 1)
    busy = [s.busy_seconds for s in servers]
    cost = sum(s.price * s.busy_seconds for s in servers)
    layout = [s.class_name for s in servers]
    return {
        "n_arrived": len(resolved),
        "n_completed": len(done),
        "n_dropped": len(resolved) - len(done),
        "n_sla_met": len(met),
        "goodput_rps": len(met) / max(window_s, 1e-9),
        "sla_attainment": len(met) / n,
        "drop_rate": (len(resolved) - len(done)) / n,
        "ttft_p50": percentile([r.ttft for r in done], 50),
        "ttft_p95": percentile([r.ttft for r in done], 95),
        "cost_per_request": cost / len(done) if done else None,
        "utilisation": [b / max(episode_s, 1e-9) for b in busy],
        "completed_by_class": {
            c: sum(1 for r in done if layout[r.server] == c) for c in sorted(set(layout))
        },
        "arrival_window_s": window_s,
        "episode_s": episode_s,
    }


def machine_info() -> dict:
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "python": platform.python_version(),
        "note": "all servers share one machine; synthetic price per busy second",
    }


class SimulationRun:
    """One replay of a held-out slice. Create, `await run.run()`, read run.metrics."""

    def __init__(
        self,
        run_id: str,
        router,
        stream: list,
        cfg: dict,
        root: Path,
        ttft_target: float,
        tpot_target: float,
        time_scale: float = 1.0,
        sample_dt: float = 0.1,
        salt: int = 0,
    ):
        self.run_id, self.router, self.stream, self.cfg = run_id, router, stream, cfg
        self.root, self.scale, self.sample_dt, self.salt = root, time_scale, sample_dt, salt
        self.ttft_target, self.tpot_target = ttft_target, tpot_target
        self.state = "new"
        self.metrics: dict | None = None
        self.dir = root / run_id
        self._tasks: list = []
        self._stop = False
        self.sent = 0

    def stop(self) -> None:
        self._stop = True

    async def _sampler(self) -> None:
        while True:
            self.router.events.snapshot_servers(self.router.now(), self.router.cluster.servers)
            await asyncio.sleep(self.sample_dt)

    async def run(self) -> dict:
        self.state = "running"
        sampler = asyncio.create_task(self._sampler())
        r = self.router
        r.t0 = r.clock()
        last_arrival = 0.0
        try:
            for i, s in enumerate(self.stream):
                if self._stop:
                    break
                delay = s.arrival_s * self.scale - r.now()
                if delay > 0:
                    await asyncio.sleep(delay)
                req = Request.from_stream(i, s, self.ttft_target, self.tpot_target)
                prompt = synth_prompt(
                    self.salt, s.conversation_id, s.turn_index, s.history_included, s.prompt_tokens
                )
                self._tasks.append(asyncio.create_task(r.handle(req, prompt, s.output_tokens)))
                self.sent += 1
                last_arrival = r.now()
            await asyncio.gather(*self._tasks, return_exceptions=True)
        finally:
            sampler.cancel()
        episode_s = r.now()
        self.metrics = live_metrics(
            r.resolved, r.cluster.servers, max(last_arrival, 1e-9), episode_s
        )
        self.metrics["time_scale"] = self.scale
        self.state = "stopped" if self._stop else "done"
        self.write(episode_s)
        return self.metrics

    def write(self, episode_s: float) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "config.yaml").write_text(yaml.safe_dump({**self.cfg, "state": self.state}))
        (self.dir / "slice.json").write_text(
            json.dumps(
                {
                    "slice_id": stream_id(self.stream),
                    "n_requests": len(self.stream),
                    "seed": self.cfg.get("seed"),
                    "split": "heldout",
                    "requests_sent": self.sent,
                },
                indent=2,
            )
        )
        (self.dir / "machine.json").write_text(json.dumps(machine_info(), indent=2))
        (self.dir / "metrics.json").write_text(json.dumps(self.metrics, indent=2, default=float))
        with open(self.dir / "events.jsonl", "w") as f:
            for e in self.router.events.events:
                f.write(json.dumps(e, default=float) + "\n")
        (self.dir / "DONE").write_text(datetime.now().isoformat())


def make_slice(world, rate_rps: float, seed: int, seconds: float) -> list:
    """The first `seconds` of the held-out stream at `rate_rps` (as the evaluation builds it)."""
    return slice_stream(world.stream(rate_rps, seed, "heldout"), 0.0, seconds)
