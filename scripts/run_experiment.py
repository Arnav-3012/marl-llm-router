"""Train independent DDQN agents (one run per seed) and evaluate them on held-out traffic. Tier B.

uv run python -m scripts.run_experiment --exp main --seeds 0-4 [--lam 1 --beta 2 --k full --episodes
N]

Per seed (in parallel, --workers, default cores-1): train on windows of the train stream, save
weights, then
evaluate greedily (epsilon = 0) on the held-out stream at each rho in rho_eval. The held-out traffic
for a seed
is exactly what scripts/evaluate.py gives the baselines. Writes results/<exp>/<timestamp>_seed<k>/
{config.yaml, train_log.csv, agents.pt, eval_metrics.json, timing.json, events_rho<rho>.jsonl (seed
0: replay logs), DONE}.
Resumable: a seed with a DONE file is skipped; a crashed seed starts a new folder, nothing is
overwritten.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime

import torch
import yaml

from marl_lb.config import ROOT
from marl_lb.data.load import load_lambda_sat, rho_to_rate
from marl_lb.eval.evaluate import World
from marl_lb.eval.experiments import eval_agents, eval_baseline
from marl_lb.policies.heuristics import SEDLocal
from marl_lb.train.loop import train
from marl_lb.utils.io import make_run_dir
from scripts.evaluate import finished, parse_seeds


def build_cfg(a) -> dict:
    cfg = {
        **yaml.safe_load((ROOT / "configs" / "dqn.yaml").read_text()),
        **yaml.safe_load((ROOT / "configs" / "train.yaml").read_text()),
    }
    for key, val in (
        ("episodes", a.episodes),
        ("window_s", a.window_s),
        ("k", a.k),
        ("lambda_cost", a.lam),
        ("beta_coop", a.beta),
        ("cost_credit", a.cost_credit),
        ("epsilon_decay_episodes", a.eps_decay),
    ):
        if val is not None:
            cfg[key] = val
    if a.mix_code:  # ADR-034: half the training episodes come from the code trace's train part
        cfg["mix_code"] = True
    if a.load_scales:  # ADR-038: e.g. "0,0.5,1,1.5", one drawn per episode
        cfg["load_scales"] = [float(x) for x in a.load_scales.split(",")]
    if a.init_from:  # start from the saved agents of results/<exp> (same seed)
        cfg["init_from"] = a.init_from
    if a.eps_start is not None:  # fine-tuning explores less than training from scratch
        cfg["epsilon"] = {**cfg["epsilon"], "start": a.eps_start}
    if a.reject:  # fourth action, always legal (ADR-029): the network gets a fourth output
        cfg["reject_enabled"] = True
        cfg["network"] = {**cfg["network"], "n_actions": 4}
    if a.rho_train:  # e.g. "0.95" or "0.5,0.8,0.95" (one load drawn per episode)
        loads = [float(x) for x in a.rho_train.split(",")]
        cfg["rho_train"] = loads if len(loads) > 1 else loads[0]
    if a.delay_cost is not None:  # price of one wasted Forward or Defer, in reward points (ADR-027)
        cfg.update(forward_cost=a.delay_cost, defer_cost=a.delay_cost)
    if a.smoke:
        cfg.update(episodes=3, window_s=15, replay={**cfg["replay"], "warmup": 50}, rho_eval=[0.8])
    cfg.update(solo=a.solo, eval_split=a.eval_split, eval_window_s=a.eval_window_s)
    k = cfg["k"]
    cfg["k"] = k if k == "full" else int(k)
    return cfg


def run_seed(job) -> str:
    exp, seed, cfg, setting = job
    world = World()
    lam = load_lambda_sat(key=setting)
    rho_train = cfg["rho_train"] if isinstance(cfg["rho_train"], list) else [cfg["rho_train"]]
    cfg = {
        **cfg,
        "seed": seed,
        "lambda_sat_rps": lam,
        "rate_rps": rho_to_rate(rho_train[0], lam),
        "rates_rps": [rho_to_rate(r, lam) for r in rho_train],  # one train stream per load
    }
    run = make_run_dir(exp, seed, cfg)
    t0 = time.time()
    solo = cfg.get("solo")
    agents = train(
        world,
        cfg,
        seed,
        solo=solo,
        log_path=run / "train_log.csv",
        progress=lambda ep, st: print(
            f"[{exp} seed {seed}] ep {ep} return {st['return_mean']:.2f} "
            f"goodput {st['goodput_rps']:.2f} "
            f"sla {st['sla_attainment']:.3f} eps {st['epsilon']:.2f} wall {st['wall_s']:.1f}s",
            flush=True,
        ),
    )
    train_s = time.time() - t0
    torch.save(
        {i: ag.state_dict() for i, ag in enumerate(agents) if ag is not None}, run / "agents.pt"
    )
    out = {}
    for rho in cfg["rho_eval"]:
        ev = run / f"events_rho{rho}.jsonl" if seed == 0 else None
        rate, split, win = rho_to_rate(rho, lam), cfg["eval_split"], cfg.get("eval_window_s")
        out[str(rho)] = eval_agents(
            world,
            agents,
            rate,
            seed,
            cfg["k"],
            ev,
            split,
            win,
            fallback=SEDLocal() if solo is not None else None,
            # fmt: skip
            lambda_cost=cfg["lambda_cost"],
            beta_coop=cfg["beta_coop"],
            reject_enabled=cfg.get("reject_enabled", False),
        )
        if solo is not None:  # reference: the all-SED-local cluster on exactly the same traffic
            out[f"{rho}_all_sed_local"] = eval_baseline(
                world, "sed_local_full", 1.0, rate, seed, None, split, win
            )
    (run / "eval_metrics.json").write_text(json.dumps(out, indent=2, default=float))
    (run / "timing.json").write_text(
        json.dumps(
            {
                "train_wall_s": train_s,
                "episodes": cfg["episodes"],
                "s_per_episode": train_s / cfg["episodes"],
            },
            indent=2,
        )
    )
    (run / "DONE").write_text(datetime.now().isoformat())
    return str(run)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", required=True)
    ap.add_argument("--seeds", default="0-4")
    ap.add_argument("--workers", type=int, default=max((os.cpu_count() or 2) - 1, 1))
    ap.add_argument("--episodes", type=int)
    ap.add_argument("--window-s", type=float, dest="window_s")
    ap.add_argument("--k")
    ap.add_argument("--lam", type=float)
    ap.add_argument("--beta", type=float)
    ap.add_argument("--cost-credit", choices=["serving", "shared"], dest="cost_credit")
    ap.add_argument("--delay-cost", type=float, dest="delay_cost")
    ap.add_argument("--eps-decay", type=int, dest="eps_decay")
    ap.add_argument("--mix-code", action="store_true", dest="mix_code", help="train on conv + code")
    ap.add_argument("--load-scales", dest="load_scales", help="ADR-038 server slowdown draws")
    ap.add_argument("--init-from", dest="init_from", help="fine-tune the agents of results/<exp>")
    ap.add_argument("--eps-start", type=float, dest="eps_start")
    ap.add_argument(
        "--reject", action="store_true", help="add the Reject action (4 actions, ADR-029)"
    )
    ap.add_argument(
        "--rho-train", dest="rho_train", help="training load(s) as fractions of lambda_sat"
    )
    ap.add_argument("--setting", default="cache_on")
    ap.add_argument(
        "--solo",
        type=int,
        help="only this agent learns, the others are SED-local (M2.12 prototype)",
    )
    ap.add_argument(
        "--eval-split", default="heldout", choices=["heldout", "train"], dest="eval_split"
    )
    ap.add_argument("--eval-window-s", type=float, dest="eval_window_s")
    ap.add_argument(
        "--smoke", action="store_true", help="3 tiny episodes, 1 seed, 1 load (plumbing check)"
    )
    a = ap.parse_args()
    cfg = build_cfg(a)
    seeds = [0] if a.smoke else parse_seeds(a.seeds)
    exp = a.exp + ("_smoke" if a.smoke else "")
    todo = [(exp, s, cfg, a.setting) for s in seeds if not finished(exp, s)]
    print(
        f"{exp}: seeds to run {[j[1] for j in todo]} (finished seeds skipped); config {cfg}",
        flush=True,
    )
    with ProcessPoolExecutor(a.workers) as pool:
        for path in pool.map(run_seed, todo):
            print("wrote", path, flush=True)
    print(f"DONE {exp} {datetime.now().isoformat(timespec='seconds')}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as e:  # noqa: BLE001
        print(f"FAILED run_experiment: {e!r}", file=sys.stderr)
        raise
    sys.exit(code)
