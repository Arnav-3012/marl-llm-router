"""Event log in the schema of the simulator's replay log, so the dashboard reads both. Tier B.

Each event: {"tick", "t", "e", ...}: arrive, act, forward, servers (per-server queue/active/KV
snapshots), resolve. tick = int(t / dt) with the simulator's dt, so the replay code can use it
unchanged.
"""

from __future__ import annotations

import threading


class EventLog:
    def __init__(self, dt: float = 0.1):
        self.dt = dt
        self.events: list[dict] = []
        self._lock = threading.Lock()

    def emit(self, kind: str, t: float, **kw) -> None:
        with self._lock:
            self.events.append({"tick": int(t / self.dt), "t": round(t, 4), "e": kind, **kw})

    def since(self, index: int) -> list[dict]:
        with self._lock:
            return self.events[index:]

    def snapshot_servers(self, t: float, servers: list) -> None:
        self.emit(
            "servers",
            t=t,
            queue=[len(s.queue) for s in servers],
            active=[len(s.active) for s in servers],
            kv=[round(s.kv_fullness(), 3) for s in servers],
        )
