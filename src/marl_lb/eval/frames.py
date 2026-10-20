"""Per-tick frames for the dashboard from an event log (simulator replay or live run). Tier B."""


def frames_from_events(events: list, dt: float, cap: int) -> list:
    """Per-tick frames {t, queue, active, kv, arrivals, acts, resolves}; if more than `cap`, ticks
    are
    merged.
    """
    by_tick: dict = {}
    for e in events:
        f = by_tick.setdefault(
            e["tick"],
            {
                "tick": e["tick"],
                "t": e["t"],
                "arrivals": [],
                "acts": [],
                "resolves": [],
                "forwards": [],
            },
        )
        kind = e["e"]
        if kind == "servers":
            f.update(queue=e["queue"], active=e["active"], kv=e["kv"])
        elif kind == "arrive":
            f["arrivals"].append({"req": e["req"], "entry": e["entry"], "p": e["p"], "o": e["o"]})
        elif kind == "act":
            f["acts"].append({"agent": e["agent"], "req": e["req"], "action": e["action"]})
        elif kind == "forward":
            f["forwards"].append({"req": e["req"], "src": e["src"], "dst": e["dst"]})
        elif kind == "resolve":
            f["resolves"].append(
                {
                    "req": e["req"],
                    "ok": e["ok"],
                    "status": e["status"],
                    "server": e.get("server"),
                    "ttft": e.get("ttft"),  # seconds, None if never served
                    "cost": e.get("cost"),  # synthetic price x busy seconds
                }
            )
    ticks = sorted(by_tick)
    step = max(1, -(-len(ticks) // cap))
    out = []
    for i in range(0, len(ticks), step):
        group = [by_tick[t] for t in ticks[i : i + step]]
        last = group[-1]
        merged = {
            "tick": last["tick"],
            "t": last["t"],
            "queue": last.get("queue"),
            "active": last.get("active"),
            "kv": last.get("kv"),
            "arrivals": [a for g in group for a in g["arrivals"]],
            "acts": [a for g in group for a in g["acts"]],
            # fmt: skip
            "forwards": [a for g in group for a in g["forwards"]],
            "resolves": [a for g in group for a in g["resolves"]],
        }
        out.append(merged)
    return out
