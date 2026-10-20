"""Export results/ to the JSON files the dashboard reads (demo/site/public/data/). Tier B.

uv run python -m scripts.export_dashboard_data [--results results] [--out demo/site/public/data]

Rules (ADR-019): reads results/ ONLY; every file is an envelope {schema_version, status, ...}; a
result that
is missing is status "not_run" with data null (never a placeholder number); every number's source
files and
the sha256 prefix of the config it came from are listed under "source". Replay logs are capped
(default
2000 frames) by merging skipped ticks into the kept frame.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml

from marl_lb.config import ROOT
from marl_lb.eval.frames import frames_from_events
from marl_lb.eval.paired import paired_difference, verify_paired
from marl_lb.eval.pareto import pareto_front
from marl_lb.eval.stats import aggregate as _aggregate
from marl_lb.sim.metrics import class_balance

SCHEMA_VERSION = 1
METRICS = [
    "goodput_rps",
    "sla_attainment",
    "breach_rate",
    "drop_rate",
    "ttft_p95",
    "tpot_p95",
    "e2e_p95",
    "cost_per_request",
    "cache_hit_rate",
    "jain_utilisation",
    "util_fast",
    "util_slow",
    "jain_fast",
]
RHOS = ["0.5", "0.8", "0.95"]
VERSIONED = {"baselines", "main", "k0", "lambda0", "lambda2"}  # have *_v2 folders (ADR-027)
SUFFIX = ""  # "_v2" reads results/main_v2, baselines_v2, ... (ADR-027); set by --suffix


def X(name: str) -> str:
    """Experiment folder name with the version suffix."""
    return name + SUFFIX


REPLAY_POLICIES = {  # dashboard name -> where its events live
    "ddqn": ("e8_mix", None),  # the final agents (Reject action, ADR-034)
    "route_to_fast_shed": ("baselines_e8", "route_to_fast_shed"),
    "route_to_fast": ("baselines", "route_to_fast"),
    "random": ("baselines", "random"),
    "sed_local": ("baselines", "sed_local_full"),
    "cache_aware": ("baselines", "cache_aware_local_full"),
    "sed_global": ("baselines", "sed_global"),
}


def _layout() -> list:
    return yaml.safe_load((ROOT / "configs" / "sim.yaml").read_text())["layout"]


def aggregate(runs: list, keys: list) -> dict:
    """stats.aggregate after adding the class balance metrics (ADR-030) to each per-seed metric
    dict that has a per-server utilisation (they are derived, so older results get them too).
    """
    layout = _layout()
    runs = [
        {**r, **class_balance(r["utilisation"], layout)}
        if len(r.get("utilisation", [])) == len(layout)
        else r
        for r in runs
    ]
    return _aggregate(runs, keys)


def envelope(data, source: dict | None = None, reason: str | None = None) -> dict:
    if data is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "not_run",
            "reason": reason or "no result in results/",
            "data": None,
            "source": None,
        }
    return {"schema_version": SCHEMA_VERSION, "status": "ok", "data": data, "source": source}


def finished_runs(results: Path, exp: str) -> list:
    return sorted(d for d in (results / exp).glob("*_seed*") if (d / "DONE").exists())


def config_hash(runs: list) -> str:
    """sha256 prefix over every run's config.yaml (one config copied per seed gives one hash)."""
    h = hashlib.sha256()
    for r in runs:
        cfg = r / "config.yaml"
        if cfg.exists():
            h.update(cfg.read_bytes())
    return h.hexdigest()[:12]


def source_of(results: Path, runs: list, files: list) -> dict:
    return {
        "files": sorted(
            {
                str((r / f).relative_to(results.parent))
                for r in runs
                for f in files
                if (r / f).exists()
            }
        ),
        "config_hash": config_hash(runs),
        "n_seeds": len(runs),
    }


def learned_rows(results: Path, exp: str, label: str):
    """Aggregate eval_metrics.json of an experiment over seeds: {rho: {metric: {mean, ci, n}}}."""
    runs = finished_runs(results, exp)
    if not runs:
        return None, None
    evals = [json.loads((r / "eval_metrics.json").read_text()) for r in runs]
    rows = {
        rho: aggregate([e[rho] for e in evals if rho in e], METRICS)
        for rho in RHOS
        if any(rho in e for e in evals)
    }
    return {"label": label, "rows": rows}, source_of(
        results, runs, ["eval_metrics.json", "config.yaml"]
    )


def baseline_rows(results: Path, exp: str | None = None):
    runs = finished_runs(results, exp or X("baselines"))
    if not runs:
        return None, None
    per_seed = [json.loads((r / "metrics.json").read_text()) for r in runs]
    keys = sorted({k for m in per_seed for k in m})
    table: dict = {}
    for k in keys:
        policy, rho = k.rsplit("@", 1)
        table.setdefault(policy, {})[rho] = aggregate([m[k] for m in per_seed if k in m], METRICS)
    return {"policies": table}, source_of(results, runs, ["metrics.json", "config.yaml"])


def export_baselines(results: Path):
    data, src = baseline_rows(results)
    learned, lsrc = learned_rows(results, X("main"), "DDQN independent, k=full, lambda=1")
    if data is None and learned is None:
        return envelope(None, reason="neither results/baselines nor results/main exist yet")
    out = {"metrics": METRICS, "baselines": data, "learned": learned, "learned_extra": []}
    sources = {"baselines": src, "learned": lsrc}
    # E8 (ADR-029): agents with the Reject action and the hand shed rule, when they have been run
    shed, ssrc = baseline_rows(results, "baselines_e8")
    if shed and data is not None and "route_to_fast_shed" in shed["policies"]:
        data["policies"]["route_to_fast_shed"] = shed["policies"]["route_to_fast_shed"]
        sources["route_to_fast_shed"] = ssrc
    for ident, exp, label in (
        ("ddqn_reject_mix", "e8_mix", "DDQN + Reject (trained on conversation + code traffic)"),
        ("ddqn_reject_ft", "e8_ft", "DDQN + Reject (v2 agents fine-tuned)"),
        ("ddqn_reject_scratch", "e8_scratch", "DDQN + Reject (trained on conversation traffic)"),
        ("ddqn_ft_ctrl", "e8_ft_ctrl", "DDQN fine-tuned without Reject (control)"),
    ):
        rows, rsrc = learned_rows(results, exp, label)
        if rows:
            out["learned_extra"].append({"id": ident, **rows})
            sources[ident] = rsrc
    return envelope(out, sources)


def export_pareto(results: Path):
    points = []
    for exp, lam in ((X("lambda0"), 0.0), (X("main"), 1.0), (X("lambda2"), 2.0)):
        rows, src = learned_rows(results, exp, f"DDQN lambda={lam}")
        if rows and "0.8" in rows["rows"]:
            m = rows["rows"]["0.8"]
            if m["cost_per_request"]["mean"] is not None and m["ttft_p95"]["mean"] is not None:
                points.append(
                    {
                        "label": f"DDQN lambda={lam}",
                        "kind": "learned",
                        "lambda": lam,
                        "cost": m["cost_per_request"],
                        "latency": m["ttft_p95"],
                        "goodput": m["goodput_rps"],
                        "source": src,
                    }
                )
    base, bsrc = baseline_rows(results)
    for policy in (
        "sed_global",
        "route_to_fast",
        "sed_local_full",
        "cache_aware_global",
        "random",
        "jsq_global",
    ):
        m = (base or {"policies": {}})["policies"].get(policy, {}).get("0.8")
        if m and m["cost_per_request"]["mean"] is not None and m["ttft_p95"]["mean"] is not None:
            points.append(
                {
                    "label": policy,
                    "kind": "baseline",
                    "lambda": None,
                    "cost": m["cost_per_request"],
                    "latency": m["ttft_p95"],
                    "goodput": m["goodput_rps"],
                    "source": bsrc,
                }
            )
    if not any(p["kind"] == "learned" for p in points):
        return envelope(None, reason="no lambda sweep in results/ yet (E3 not run)")
    front = set(pareto_front([(p["cost"]["mean"], p["latency"]["mean"]) for p in points]))
    for i, p in enumerate(points):
        p["on_frontier"] = i in front
    return envelope(
        {"rho": 0.8, "x": "cost_per_request", "y": "ttft_p95", "points": points},
        {"note": "points carry their own source"},
    )


def export_observability(results: Path):
    k_full, s1 = learned_rows(results, X("main"), "DDQN k=full")
    k0, s2 = learned_rows(results, X("k0"), "DDQN k=0")
    base, s3 = baseline_rows(results)
    if not (k_full or k0):
        return envelope(None, reason="no k ablation in results/ yet (E4 not run)")
    refs = {
        p: (base or {"policies": {}})["policies"].get(p)
        for p in ("sed_local_k0", "sed_local_full", "sed_global")
    }
    return envelope(
        {"learned": [x for x in (k0, k_full) if x], "references": refs},
        {"learned_k0": s2, "learned_k_full": s1, "baselines": s3},
    )


def export_behaviour(results: Path):
    """Action shares of the learned agents by class, wait and prompt size (analyse_behaviour)."""
    f = results / "behaviour" / "e8_mix.json"  # the final agents
    if not f.exists():
        f = results / "behaviour" / f"{X('main')}.json"
    if not f.exists():
        return envelope(None, reason="no behaviour analysis yet (scripts/analyse_behaviour.py)")
    d = json.loads(f.read_text())
    data = {k: d[k] for k in ("agents_experiment", "seeds", "split", "rhos")}
    sim = yaml.safe_load((ROOT / "configs" / "sim.yaml").read_text())
    norm = json.loads((ROOT / sim["traffic"]["normalisation_path"]).read_text())
    # the bins are fractions of these constants; the page converts them to seconds and tokens
    data["units"] = {
        "wait_s": sim["wait_scale_s"],
        "prompt_tokens": norm["constants"]["prompt_tokens"],
    }
    return envelope(
        data,
        {"files": [f"behaviour/{f.name}"], "n_seeds": len(d["seeds"]), "note": "held-out stream"},
    )


def _sweep(results: Path, folder: str, refs: list) -> dict | None:
    """Load sweep (ADR-032): goodput per policy and load; paired differences agents minus each."""
    runs = sorted(d for d in (results / folder).glob("*") if (d / "DONE").exists())
    if not runs:
        return None
    d = runs[-1]
    rhos = sorted({float(f.stem.split("_rho")[-1]) for f in d.glob("ddqn_agents_rho*.json")})
    out = {"folder": f"{folder}/{d.name}", "rhos": rhos, "policies": {}, "diff": {}}
    for pol in ["ddqn_agents", *refs]:
        out["policies"][pol] = []
        for rho in rhos:
            f = d / f"{pol}_rho{rho}.json"
            if not f.exists():
                out["policies"][pol].append(None)
                continue
            per = json.loads(f.read_text())["per_seed"]
            out["policies"][pol].append(
                _aggregate([m for m in per.values()], ["goodput_rps"])["goodput_rps"]
            )
    for ref in refs:
        out["diff"][ref] = []
        for rho in rhos:
            a = json.loads((d / f"ddqn_agents_rho{rho}.json").read_text())["per_seed"]
            b = json.loads((d / f"{ref}_rho{rho}.json").read_text())["per_seed"]
            diffs = [a[s]["goodput_rps"] - b[s]["goodput_rps"] for s in sorted(a) if s in b]
            out["diff"][ref].append(_aggregate([{"x": x} for x in diffs], ["x"])["x"])
    return out


def export_stress(results: Path):
    """ADR-032 tests: load sweep, server degradation, feature shuffling (v2 and Reject agents)."""
    data = {
        "sweep_reject": _sweep(
            results, "paired_sweep_mix", ["route_to_fast", "route_to_fast_shed", "sed_global"]
        ),
        "sweep_v2": _sweep(results, "paired_sweep", ["route_to_fast", "sed_global"]),
        "degradation": {},
        "shuffle": {},
    }
    for exp in ("main_v2", "e8_mix"):
        f = results / "degradation" / f"{exp}.json"
        if f.exists():
            data["degradation"][exp] = json.loads(f.read_text())
        f = results / "shuffle" / f"{exp}.json"
        if f.exists():
            data["shuffle"][exp] = json.loads(f.read_text())
    f = results / "shift" / "e8_mix.json"
    data["shift"] = json.loads(f.read_text()) if f.exists() else None
    if not (data["sweep_reject"] or data["sweep_v2"] or data["degradation"] or data["shuffle"]):
        return envelope(None, reason="the stress tests (ADR-032) have not been run")
    files = [x["folder"] for x in (data["sweep_reject"], data["sweep_v2"]) if x]
    files += [f"degradation/{e}.json" for e in data["degradation"]]
    files += [f"shuffle/{e}.json" for e in data["shuffle"]]
    files += ["shift/e8_mix.json"] if data["shift"] else []
    return envelope(
        data, {"files": [f"results/{f}" for f in files], "n_seeds": 5, "note": "held-out stream"}
    )


def export_training(results: Path, max_points: int = 200):
    runs = finished_runs(results, X("main"))
    if not runs:
        return envelope(None, reason="no main training run in results/ yet")
    cols = [
        "return_mean",
        "goodput_rps",
        "sla_attainment",
        "td_loss",
        "mean_q",
        "epsilon",
        "act_accept",
        "act_forward",
        "act_defer",
    ]
    per_seed = []
    for r in runs:
        with open(r / "train_log.csv") as f:
            per_seed.append(list(csv.DictReader(f)))
    n = min(len(x) for x in per_seed)
    step = max(1, n // max_points)
    eps = []
    for i in range(0, n, step):
        row = {"episode": i}
        for c in cols:
            vals = [float(x[i][c]) for x in per_seed if x[i][c] not in ("", "nan")]
            row[c] = sum(vals) / len(vals) if vals else None
        eps.append(row)

    def num(v):
        return None if v in ("", "nan") else float(v)

    seeds = [  # one thinned series per seed, so the page can show every seed (ADR-001)
        {
            "seed": int(re.search(r"_seed(\d+)$", r.name).group(1)),
            "episodes": [
                {"episode": i, **{c: num(rows[i][c]) for c in cols}} for i in range(0, n, step)
            ],
        }
        for r, rows in zip(runs, per_seed, strict=True)
    ]
    return envelope(
        {"columns": cols, "n_seeds": len(runs), "episodes": eps, "seeds": seeds},
        source_of(results, runs, ["train_log.csv", "config.yaml"]),
    )


def export_traces(results: Path):
    p = results / "eda" / "trace_summary.json"
    if not p.exists():
        return envelope(None, reason="results/eda/trace_summary.json missing")
    return envelope(json.loads(p.read_text()), {"files": [str(p.relative_to(results.parent))]})


def adr_index(root: Path) -> list:
    out = []
    text = (root / "docs" / "decisions.md").read_text()
    for m in re.finditer(r"^## (ADR-\d+): (.+)\n(?:Status: ([^·\n]+))?", text, re.M):
        out.append(
            {"id": m.group(1), "title": m.group(2).strip(), "status": (m.group(3) or "").strip()}
        )
    return out


def export_method(results: Path, root: Path):
    runs = (
        sorted((results / "profiling").glob("*_seed*")) if (results / "profiling").exists() else []
    )
    runs = [r for r in runs if (r / "fit_output.json").exists() and not r.name.endswith("_smoke")]
    fit = json.loads((runs[-1] / "fit_output.json").read_text()) if runs else None
    meta = (
        json.loads((runs[-1] / "meta.json").read_text())
        if runs and (runs[-1] / "meta.json").exists()
        else None
    )
    sat = results / "saturation" / "lambda_sat.json"
    calib = root / "profiling" / "calibration.json"
    data = {
        "adrs": adr_index(root),
        "profiling_fit": fit,
        "profiling_machine": meta.get("machine") if meta else None,
        "lambda_sat": json.loads(sat.read_text()) if sat.exists() else None,
        "calibration": json.loads(calib.read_text()) if calib.exists() else None,
    }
    src = {
        "files": [
            str(p.relative_to(root))
            for p in (
                runs[-1] / "fit_output.json" if runs else None,
                sat if sat.exists() else None,
                calib if calib.exists() else None,
            )
            if p
        ]
    }
    return envelope(data, src)


def export_replays(
    results: Path, out: Path, dt: float, cap: int, layout: list | None = None
) -> list:
    written = []
    for name, (exp, policy) in REPLAY_POLICIES.items():
        folder = X(exp) if exp in VERSIONED else exp
        runs = [r for r in finished_runs(results, folder) if r.name.endswith("_seed0")]
        for rho in RHOS:
            fname = (
                f"events_rho{rho}.jsonl" if policy is None else f"events_{policy}_rho{rho}.jsonl"
            )
            path = runs[0] / fname if runs else None
            rel = f"replay_{name}_{rho}.json"
            if path is None or not path.exists():
                (out / rel).write_text(
                    json.dumps(envelope(None, reason=f"no event log for {name} at rho {rho}"))
                )
            else:
                events = [json.loads(line) for line in path.read_text().splitlines() if line]
                data = {
                    "policy": name,
                    "rho": float(rho),
                    "dt": dt,
                    "layout": layout,
                    "frames": frames_from_events(events, dt, cap),
                }
                (out / rel).write_text(
                    json.dumps(
                        envelope(
                            data,
                            {
                                "files": [str(path.relative_to(results.parent))],
                                "config_hash": config_hash(runs),
                                "n_seeds": 1,
                            },
                        )
                    )
                )
            written.append(rel)
    return written


H2H_LABEL = {
    "ddqn_agents": "Learned agents (DDQN + Reject)",
    "route_to_fast_shed": "Hand-written rule: route to fast + shed",
    "random": "Random (entry rule)",
    "route_to_fast": "Hand-written rule: route to fast",
    "sed_global": "SED global",
    "sed_local_full": "SED local (k=full)",
    "cache_aware_global": "Cache-aware global",
    "cache_aware_local_full": "Cache-aware local",
}
H2H_DIFF_METRICS = ["goodput_rps", "sla_attainment", "drop_rate", "ttft_p95", "cost_per_request"]
H2H_FRAME_CAP = (
    1200  # two panes are drawn at once, so a replay has fewer frames than the Replay page
)


def latest_paired(results: Path):
    done = sorted(d for d in (results / "paired").glob("*") if (d / "DONE").exists())
    return done[-1] if done else None


def export_headtohead(results: Path, out: Path, dt: float, cap: int, layout: list | None) -> list:
    """headtohead.json (summaries, paired differences, provenance) + h2h_replay_<policy>_<rho>.json.

    Reads the newest finished results/paired/<run>/ and refuses (raises) if its policies did not see
    identical traffic (verify_paired). A missing run becomes a labelled "not run" file.
    """
    import yaml

    written = ["headtohead.json"]
    run = latest_paired(results)
    if run is None:
        reason = "no finished results/paired/<run>/ yet (scripts/evaluate_paired.py)"
        (out / "headtohead.json").write_text(json.dumps(envelope(None, reason=reason)))
        return written
    report = verify_paired(run)
    cfg = yaml.safe_load((run / "config.yaml").read_text())
    docs = {}
    for f in sorted(run.glob("*_rho*.json")):
        d = json.loads(f.read_text())
        docs[(d["policy"], str(d["rho"]))] = (f, d)
    learned = cfg["learned"]["name"]
    pids = [p for p in [learned, *cfg["baselines"]] if any(k[0] == p for k in docs)]
    data = {
        "dt": dt,
        "layout": layout,
        "learned": learned,
        "event_seed": cfg["event_seed"],
        "slice_split": cfg["split"],
        "policies": [
            {
                "id": p,
                "label": H2H_LABEL.get(p, p),
                "kind": "learned" if p == learned else "baseline",
                "mode": "global" if p.endswith("_global") else "agents",
            }
            for p in pids
        ],
        "rhos": {},
    }
    for rho in [str(r) for r in sorted(report)]:
        rows = {p: docs[(p, rho)][1] for p in pids if (p, rho) in docs}
        learned_doc = rows.get(learned)
        entry = {
            "slice_id": report[float(rho)]["slice_id"],
            "seeds": report[float(rho)]["seeds"],
            "config_hash": report[float(rho)]["config_hash"],
            "summary": {
                p: aggregate(list(d["per_seed"].values()), METRICS) for p, d in rows.items()
            },
            "paired_diff": {},
            "replay": {},
        }
        for p, d in rows.items():
            if p != learned and learned_doc is not None:
                try:
                    entry["paired_diff"][p] = {
                        m: paired_difference(learned_doc["per_seed"], d["per_seed"], m)
                        for m in H2H_DIFF_METRICS
                    }
                except ValueError:  # fewer than 2 shared seeds
                    entry["paired_diff"][p] = None
            rel = f"h2h_replay_{p}_{rho}.json"
            events_path = run / d["events_file"] if d.get("events_file") else None
            if events_path is None or not events_path.exists():
                (out / rel).write_text(
                    json.dumps(envelope(None, reason=f"no event log for {p} at rho {rho}"))
                )
                entry["replay"][p] = None
            else:
                events = [json.loads(x) for x in events_path.read_text().splitlines() if x]
                replay = {
                    "policy": p,
                    "rho": float(rho),
                    "dt": dt,
                    "layout": layout,
                    "mode": "global" if p.endswith("_global") else "agents",
                    "seed": cfg["event_seed"],
                    "events": d["events"],
                    "frames": frames_from_events(events, dt, min(cap, H2H_FRAME_CAP)),
                }
                src = {
                    "files": [str(events_path.relative_to(results.parent))],
                    "config_hash": d["config_hash"],
                    "n_seeds": 1,
                    "note": f"slice {d['slice_id']}, seed {cfg['event_seed']}",
                }
                (out / rel).write_text(json.dumps(envelope(replay, src), default=float))
                entry["replay"][p] = rel
                written.append(rel)
        data["rhos"][rho] = entry
    source = {
        "files": sorted(str(f.relative_to(results.parent)) for f, _ in docs.values()),
        "config_hash": next(iter(report.values()))["config_hash"],
        "n_seeds": len(next(iter(report.values()))["seeds"]),
        "note": "every policy on the identical held-out slice (verified)",
    }
    (out / "headtohead.json").write_text(json.dumps(envelope(data, source), default=float))
    return written


def export_overview(results: Path, root: Path, baselines: dict, observability: dict, pareto: dict):
    def headline(env, getter):
        try:
            return getter(env["data"]) if env["status"] == "ok" else None
        except (KeyError, TypeError):
            return None

    q1 = headline(
        baselines,
        lambda d: {
            "rho": "0.8",
            "metric": "goodput_rps",
            "ddqn": d["learned"]["rows"]["0.8"]["goodput_rps"] if d["learned"] else None,
            "sed_local_full": d["baselines"]["policies"]["sed_local_full"]["0.8"]["goodput_rps"],
            "sed_global": d["baselines"]["policies"]["sed_global"]["0.8"]["goodput_rps"],
            "route_to_fast": d["baselines"]["policies"]
            .get("route_to_fast", {})
            .get("0.8", {})
            .get("goodput_rps"),
            "cache_aware_local_full": d["baselines"]["policies"]["cache_aware_local_full"]["0.8"][
                "goodput_rps"
            ],
        },
    )

    def reject_headline(d):
        extra = {x["id"]: x["rows"] for x in d.get("learned_extra") or []}
        pol = d["baselines"]["policies"]
        if "ddqn_reject_mix" not in extra or "route_to_fast_shed" not in pol:
            return None

        def at(table, rho):
            m = table[rho]
            return {"goodput": m["goodput_rps"], "drop_rate": m["drop_rate"]}

        out = {"rhos": {}}
        for rho in ("0.8", "0.95"):
            out["rhos"][rho] = {
                "reject_scratch": at(extra["ddqn_reject_mix"], rho),
                "reject_ft": at(extra["ddqn_reject_ft"], rho)
                if "ddqn_reject_ft" in extra
                else None,
                "v2": at(d["learned"]["rows"], rho),
                "sed_global": at(pol["sed_global"], rho),
                "route_to_fast": at(pol["route_to_fast"], rho),
                "route_to_fast_shed": at(pol["route_to_fast_shed"], rho),
            }
        return out

    def real_runs() -> int:
        """Finished live runs against REAL servers (mock rehearsals do not count)."""
        n = 0
        for d in (results / "live").glob("*/DONE"):
            try:
                cfg = yaml.safe_load((d.parent / "config.yaml").read_text())
            except (OSError, yaml.YAMLError):
                continue
            n += int(cfg.get("mode") == "real")
        return n

    experiments = {  # keyed by the plain experiment name; the folder carries the version suffix
        e: len(finished_runs(results, X(e) if e in VERSIONED else e))
        for e in ("baselines", "main", "k0", "lambda0", "lambda2", "prototype", "timing")
    }
    data = {
        "q1_goodput": q1,
        "q2_pareto_available": pareto["status"] == "ok",
        "q2_frontier": headline(  # which learned settings sit on the cost-latency frontier
            pareto,
            lambda d: {
                "learned": [p["label"] for p in d["points"] if p["kind"] == "learned"],
                "on_frontier": [
                    p["label"] for p in d["points"] if p["kind"] == "learned" and p["on_frontier"]
                ],
            },
        ),
        "q3_observability_available": observability["status"] == "ok",
        "real_server_runs": real_runs(),
        "q4_reject": headline(baselines, reject_headline),
        "experiments_finished_seeds": experiments,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "not_done": [
            "break-it experiments (M2/M3)",
            "E5 burst test",
            "E6 specialisation",
            "centralised DQN reference",
            "full 10-repeat profiling (this calibration used 5 repeats)",
            "real-server replay and sim-to-real gap (E7)",
            "Docker, Hugging Face Space and demo video",
            "3D scene and dynamic results",
        ],
    }
    return envelope(
        data, {"note": "headline numbers are copied from baselines.json (see its source)"}
    )


def run_export(
    results: Path,
    out: Path,
    root: Path = ROOT,
    cap: int = 2000,
    dt: float | None = None,
    suffix: str = "",
) -> list:
    global SUFFIX
    SUFFIX = suffix
    out.mkdir(parents=True, exist_ok=True)
    layout = None
    if dt is None:
        import yaml

        sim = yaml.safe_load((root / "configs" / "sim.yaml").read_text())
        dt, layout = sim["dt"], sim.get("layout")
    files = {
        "baselines.json": export_baselines(results),
        "pareto.json": export_pareto(results),
        "observability.json": export_observability(results),
        "behaviour.json": export_behaviour(results),
        "stress.json": export_stress(results),
        "training.json": export_training(results),
        "traces.json": export_traces(results),
        "method.json": export_method(results, root),
    }
    files["overview.json"] = export_overview(
        results, root, files["baselines.json"], files["observability.json"], files["pareto.json"]
    )
    for name, env in files.items():
        (out / name).write_text(json.dumps(env, indent=1, default=float))
    names = sorted(files) + export_replays(results, out, dt, cap, layout)
    names += export_headtohead(results, out, dt, cap, layout)
    (out / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "files": names,
                "exported_at": datetime.now().isoformat(timespec="seconds"),
            },
            indent=1,
        )
    )
    return names


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, default=ROOT / "results")
    ap.add_argument("--out", type=Path, default=ROOT / "demo" / "site" / "public" / "data")
    ap.add_argument("--cap", type=int, default=2000)
    ap.add_argument("--suffix", default="", help="read results/<exp><suffix>, e.g. _v2 (ADR-027)")
    a = ap.parse_args()
    names = run_export(a.results, a.out, cap=a.cap, suffix=a.suffix)
    print(f"wrote {len(names)} files to {a.out}")
    print(f"DONE export_dashboard_data {datetime.now().isoformat(timespec='seconds')}")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as e:  # noqa: BLE001
        print(f"FAILED export_dashboard_data: {e!r}", file=sys.stderr)
        raise
    sys.exit(code)
