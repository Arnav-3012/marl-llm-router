"""Paired evaluation outputs for the head-to-head page (Sh.H1, ADR-025). Tier B.

Every policy is run on the SAME traffic slice with the same seeds. Each policy gets one file per
load, `<policy>_rho<rho>.json`, that records which slice it saw (a hash of the request list), the
seed list and a hash of everything that defines the world, so the page (and `verify_paired`) can
prove two policies were compared on identical traffic. The replay event log of one seed is written
beside it, capped so the dashboard can load it.

Nothing here knows about the real simulator: a runner is any function
`runner(stream, seed, record) -> (metrics_dict, events_list)`, so the logic is tested on a fixture.
"""

from __future__ import annotations

import hashlib
import json
from math import ceil, sqrt
from pathlib import Path

from scipy import stats

HASH_LEN = 12


def _jsonable(o):
    """json.dumps fallback: NumPy scalars (and 0-d arrays) become plain Python numbers."""
    if hasattr(o, "item"):
        return o.item()
    raise TypeError(f"{type(o).__name__} is not JSON serializable")


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:HASH_LEN]


def stream_id(stream: list) -> str:
    """Hash of the request list (arrival, lengths, conversation, turn, history flag).

    Two streams with the same id contain the same requests in the same order.
    """
    rows = [
        (
            round(float(r.arrival_s), 9),
            int(r.prompt_tokens),
            int(r.output_tokens),
            int(r.conversation_id),
            int(r.turn_index),
            bool(r.history_included),
        )
        for r in stream
    ]
    return _digest(json.dumps(rows))


def config_hash(cfg: dict) -> str:
    """Hash of a config dict (keys sorted, so key order does not matter)."""
    return _digest(json.dumps(cfg, sort_keys=True, default=str))


def cap_events(events: list, cap: int) -> tuple[list, dict]:
    """Shrink an event log to at most `cap` events, keeping every arrival/decision/resolution.

    The per-tick "servers" snapshots are what makes a log big, so those are thinned evenly. If the
    other events alone exceed the cap, the log is cut to its first `cap` events and `truncated`
    says so. Order is preserved.
    """
    info = {"cap": cap, "original": len(events), "truncated": False}
    if len(events) <= cap:
        return list(events), {**info, "kept": len(events)}
    snaps = [i for i, e in enumerate(events) if e.get("e") == "servers"]
    other = len(events) - len(snaps)
    if other >= cap:
        kept = events[:cap]
        return kept, {**info, "kept": len(kept), "truncated": True}
    budget = cap - other
    step = ceil(len(snaps) / budget)
    keep_snaps = set(snaps[::step])
    kept = [e for i, e in enumerate(events) if e.get("e") != "servers" or i in keep_snaps]
    return kept, {**info, "kept": len(kept)}


def run_one(runner, stream: list, seed: int, record: bool) -> dict:
    """Run one policy on one stream and prove the stream was not changed by the run."""
    before = stream_id(stream)
    metrics, events = runner(stream, seed, record)
    if stream_id(stream) != before:
        raise RuntimeError("a policy modified the traffic stream it was given")
    return {
        "seed": seed,
        "slice_id": before,
        "metrics": metrics,
        "events": events if record else [],
    }


def write_policy_file(
    out_dir: Path,
    policy: str,
    rho: float,
    rate_rps: float,
    split: str,
    cfg_hash: str,
    results: list,
    event_seed: int,
    event_cap: int,
) -> Path:
    """Write <policy>_rho<rho>.json (+ capped events of `event_seed`) from run_one results."""
    out_dir = Path(out_dir)
    seeds = sorted(r["seed"] for r in results)
    slice_ids = {str(r["seed"]): r["slice_id"] for r in results}
    # One id for the whole slice set of this load: the per-seed ids in seed order.
    set_id = _digest(json.dumps([slice_ids[str(s)] for s in seeds]))
    base = f"{policy}_rho{rho}"
    events_meta = None
    for r in results:
        if r["seed"] == event_seed and r["events"]:
            kept, events_meta = cap_events(r["events"], event_cap)
            events_meta["seed"] = event_seed
            (out_dir / f"{base}.events.jsonl").write_text(
                "".join(json.dumps(e, default=_jsonable) + "\n" for e in kept)
            )
    doc = {
        "policy": policy,
        "rho": rho,
        "rate_rps": rate_rps,
        "split": split,
        "seeds": seeds,
        "slice_ids": slice_ids,
        "slice_id": set_id,
        "config_hash": cfg_hash,
        "per_seed": {str(r["seed"]): r["metrics"] for r in results},
        "events": events_meta,
        "events_file": f"{base}.events.jsonl" if events_meta else None,
    }
    path = out_dir / f"{base}.json"
    path.write_text(json.dumps(doc, indent=2, default=_jsonable))
    return path


def evaluate_paired(
    runners: dict,
    stream_fn,
    rhos: list,
    rate_fn,
    seeds: list,
    split: str,
    cfg_hash: str,
    out_dir: Path,
    event_seed: int = 0,
    event_cap: int = 60000,
) -> list:
    """Serial paired evaluation: every runner sees the very same stream object per (rho, seed)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for rho in rhos:
        rate = rate_fn(rho)
        streams = {s: stream_fn(rate, s) for s in seeds}
        for name, runner in runners.items():
            results = [run_one(runner, streams[s], s, record=(s == event_seed)) for s in seeds]
            written.append(
                write_policy_file(
                    out_dir, name, rho, rate, split, cfg_hash, results, event_seed, event_cap
                )
            )
    return written


def verify_paired(out_dir: Path) -> dict:
    """Check that, per load, every policy file has the same slice id, seed list and config hash.

    Returns {rho: {"policies": [...], "slice_id": ..., "seeds": [...], "config_hash": ...}} and
    raises ValueError naming the first mismatch. Also checks that an events file respects its cap.
    """
    files = sorted(Path(out_dir).glob("*_rho*.json"))
    if not files:
        raise ValueError(f"no policy files in {out_dir}")
    by_rho: dict = {}
    for f in files:
        d = json.loads(f.read_text())
        by_rho.setdefault(d["rho"], []).append((f.name, d))
        ev = d.get("events")
        if ev and ev["kept"] > ev["cap"]:
            raise ValueError(f"{f.name}: {ev['kept']} events kept, cap is {ev['cap']}")
        if d.get("events_file"):
            n = sum(1 for _ in open(Path(out_dir) / d["events_file"]))
            if n != ev["kept"]:
                raise ValueError(f"{f.name}: events file has {n} lines, metadata says {ev['kept']}")
    report = {}
    for rho, items in by_rho.items():
        first_name, first = items[0]
        for name, d in items[1:]:
            for key in ("slice_id", "seeds", "config_hash", "split"):
                if d[key] != first[key]:
                    raise ValueError(
                        f"rho {rho}: {name} has {key} {d[key]!r}, {first_name} has {first[key]!r}"
                    )
        report[rho] = {
            "policies": sorted(d["policy"] for _, d in items),
            "slice_id": first["slice_id"],
            "seeds": first["seeds"],
            "config_hash": first["config_hash"],
        }
    return report


def paired_difference(a_per_seed: dict, b_per_seed: dict, metric: str) -> dict:
    """Mean of (a - b) over the seeds both have, with a 95% Student-t interval.

    Because both policies saw the same traffic per seed, the per-seed difference removes the
    traffic noise; the interval is therefore usually tighter than two separate intervals.
    """
    seeds = sorted(set(a_per_seed) & set(b_per_seed), key=int)
    if len(seeds) < 2:
        raise ValueError("a paired difference needs at least 2 shared seeds")
    diff = [a_per_seed[s][metric] - b_per_seed[s][metric] for s in seeds]
    n = len(diff)
    mean = sum(diff) / n
    sd = sqrt(sum((d - mean) ** 2 for d in diff) / (n - 1))
    half = float(stats.t.ppf(0.975, n - 1) * sd / sqrt(n))
    return {
        "metric": metric,
        "n": n,
        "seeds": [int(s) for s in seeds],
        "mean_diff": mean,
        "ci95": [mean - half, mean + half],
        "excludes_zero": bool(mean - half > 0 or mean + half < 0),
    }
