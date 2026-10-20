"""Paired evaluation for the head-to-head page: all policies, same held-out slice (Sh.H1). Tier B.

uv run python -m scripts.evaluate_paired [--workers N] [--seeds 0-4] [--rhos 0.5,0.8,0.95] [--smoke]

Policies: the baselines named in configs/paired.yaml plus the learned agents from the saved weights
of results/<experiment>/*_seed<k>/agents.pt. Every policy at a given load and seed receives a stream
built the same way (same rate, seed and split), and every output file records a hash of that stream,
the seed list and a hash of the simulator config, so `verify_paired` can show the traffic was
identical. Writes results/paired/<timestamp>/{<policy>_rho<rho>.json, *.events.jsonl, config.yaml,
paired_report.json, DONE}. --smoke: 1 seed, 1 load, small cap, written to results/paired_smoke/.
Prints `DONE paired_eval <timestamp>`; exits non-zero on failure.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime

import torch
import yaml

from marl_lb.agents.dqn_agent import DQNAgent
from marl_lb.config import ROOT
from marl_lb.data.load import load_lambda_sat, rho_to_rate
from marl_lb.eval import paired
from marl_lb.eval.evaluate import World, local_actions, run_episode
from marl_lb.eval.experiments import suite
from marl_lb.train.loop import greedy_actions
from scripts.evaluate import parse_seeds

_CTX: dict = {}


def _init(cfg: dict) -> None:
    _CTX["cfg"] = cfg
    _CTX["world"] = World()
    _CTX["agents"] = {}


def load_agents(experiment: str, seed: int, n: int) -> tuple:
    """Agents of the newest results/<experiment>/*_seed<seed>/ run, and that run's config."""
    runs = sorted((ROOT / "results" / experiment).glob(f"*_seed{seed}"))
    runs = [r for r in runs if (r / "agents.pt").exists()]
    if not runs:
        raise FileNotFoundError(f"no agents.pt for seed {seed} in results/{experiment}")
    run = runs[-1]
    cfg = yaml.safe_load((run / "config.yaml").read_text())
    states = torch.load(run / "agents.pt", map_location="cpu")
    agents = []
    for i in range(n):
        agent = DQNAgent(cfg, seed * 1000 + i)
        agent.load_state_dict(states[i])
        agents.append(agent)
    return agents, cfg


def make_runner(name: str):
    world, cfg = _CTX["world"], _CTX["cfg"]
    if name == cfg["learned"]["name"]:

        def run_learned(stream, seed, record):
            if seed not in _CTX["agents"]:
                _CTX["agents"][seed] = load_agents(
                    cfg["learned"]["experiment"], seed, len(world.params.layout)
                )
            agents, train_cfg = _CTX["agents"][seed]
            cluster = world.cluster(
                k=train_cfg["k"],
                record_events=record,
                lambda_cost=train_cfg["lambda_cost"],
                beta_coop=train_cfg["beta_coop"],
            )
            metrics, _ = run_episode(cluster, stream, seed, greedy_actions(agents, None))
            return metrics, (cluster.run.events if record else [])

        return run_learned

    mode, kw, factory = suite(world, cfg["cache_aware_w"])[name]

    def run_baseline(stream, seed, record):
        policy = factory(seed)
        if mode == "global":
            cluster = world.cluster(mode="global", global_policy=policy, record_events=record, **kw)
            metrics, _ = run_episode(cluster, stream, seed)
        else:
            cluster = world.cluster(record_events=record, **kw)
            metrics, _ = run_episode(cluster, stream, seed, local_actions(policy))
        return metrics, (cluster.run.events if record else [])

    return run_baseline


def run_job(job: tuple) -> dict:
    name, rho, seed, record = job
    cfg, world = _CTX["cfg"], _CTX["world"]
    stream = world.stream(cfg["rates"][str(rho)], seed, cfg["split"])
    out = paired.run_one(make_runner(name), stream, seed, record)
    return {"policy": name, "rho": rho, **out}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=max((os.cpu_count() or 2) - 1, 1))
    ap.add_argument("--seeds")
    ap.add_argument("--rhos")
    ap.add_argument(
        "--smoke", action="store_true", help="1 seed, 1 load, small cap, *_smoke folder"
    )
    a = ap.parse_args()
    cfg = yaml.safe_load((ROOT / "configs" / "paired.yaml").read_text())
    if a.seeds:
        cfg["seeds"] = parse_seeds(a.seeds)
    if a.rhos:
        cfg["rhos"] = [float(x) for x in a.rhos.split(",")]
    if a.smoke:
        cfg.update(seeds=[0], rhos=[0.5], event_cap=2000)
    if cfg["split"] != "heldout":
        raise ValueError("paired evaluation is held-out only (RULES: never tune on this slice)")

    world = World()
    lam = load_lambda_sat()
    cfg["lambda_sat_rps"] = lam
    cfg["rates"] = {str(rho): rho_to_rate(rho, lam) for rho in cfg["rhos"]}
    cfg_hash = paired.config_hash(
        {
            "sim": world.sim,
            "calibration": world.calib,
            "lambda_sat_rps": lam,
            "split": cfg["split"],
            "seeds": cfg["seeds"],
            "rhos": cfg["rhos"],
        }
    )
    names = [*cfg["baselines"], cfg["learned"]["name"]]
    out_dir = ROOT / "results" / ("paired_smoke" if a.smoke else "paired")
    out_dir = out_dir / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=False)
    (out_dir / "config.yaml").write_text(yaml.safe_dump({**cfg, "config_hash": cfg_hash}))

    jobs = [
        (name, rho, seed, seed == cfg["event_seed"])
        for rho in cfg["rhos"]
        for name in names
        for seed in cfg["seeds"]
    ]
    print(f"{len(jobs)} runs: {len(names)} policies x {len(cfg['rhos'])} loads x "
          f"{len(cfg['seeds'])} seeds (workers {a.workers})", flush=True)  # fmt: skip
    with ProcessPoolExecutor(a.workers, initializer=_init, initargs=(cfg,)) as pool:
        results = list(pool.map(run_job, jobs))

    for rho in cfg["rhos"]:
        for name in names:
            mine = [r for r in results if r["policy"] == name and r["rho"] == rho]
            paired.write_policy_file(
                out_dir, name, rho, cfg["rates"][str(rho)], cfg["split"], cfg_hash, mine,
                cfg["event_seed"], cfg["event_cap"],
            )  # fmt: skip
    report = paired.verify_paired(out_dir)
    (out_dir / "paired_report.json").write_text(json.dumps(report, indent=2))
    (out_dir / "DONE").write_text(datetime.now().isoformat())
    print(f"wrote {out_dir}")
    print(f"DONE paired_eval {datetime.now().isoformat(timespec='seconds')}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as e:  # noqa: BLE001
        print(f"FAILED paired_eval: {e!r}", file=sys.stderr)
        raise
    sys.exit(code)
