"""Start or stop the four real llama-servers as the profiling run did (Sh.L3, Sh.L6). Tier B.

uv run python -m scripts.live_servers start [--wait 300]    # starts 4 servers, waits for /health
uv run python -m scripts.live_servers stop

The logic is in marl_lb.router.servers (also used by the router's guided live test). Logs go to
results/logs/llama_<port>.log; process ids to results/live/servers.pid.
"""

from __future__ import annotations

import argparse
import sys
import time

from marl_lb.router import servers


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["start", "stop"])
    ap.add_argument("--wait", type=float, default=300.0)
    a = ap.parse_args()
    if a.action == "stop":
        print(f"stopped {servers.stop()}")
        return 0
    try:
        pids = servers.start()
    except (RuntimeError, FileNotFoundError) as e:
        print(e, file=sys.stderr)
        return 1
    for p in pids:
        print(f"started {p['class']} on {p['port']} (pid {p['pid']})")
    t0 = time.time()
    while time.time() - t0 < a.wait:
        if all(servers.healthy(p["port"]) for p in pids):
            print("all four servers are healthy")
            return 0
        time.sleep(2)
    print("timeout: not all servers became healthy; see results/logs/llama_*.log", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
