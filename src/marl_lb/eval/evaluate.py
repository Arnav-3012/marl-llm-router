"""Build the simulated world from configs/data and run policies on it. Tier B.

World loads everything a run needs (sim config, calibration.json, normalisation constants, the Azure
trace) so scripts and tests build clusters and traffic the same way. run_episode plays one stream
through a Cluster with a policy (local heuristic, global heuristic or learned agents) and returns
the
metrics and, if asked, the replay event log.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import yaml

from marl_lb.config import ROOT
from marl_lb.data.traces import load_azure_2023, sample_stream
from marl_lb.sim.cluster import Cluster, SimParams
from marl_lb.sim.metrics import summarise


def deep_update(base: dict, new: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in new.items():
        out[k] = (
            deep_update(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
        )
    return out


class World:
    """sim.yaml (+ overrides), calibration.json, normalisation.json and the trace, loaded once."""

    def __init__(self, overrides: dict | None = None, root: Path = ROOT):
        sim = yaml.safe_load((root / "configs" / "sim.yaml").read_text())
        self.sim = deep_update(sim, overrides or {})
        self.calib = json.loads((root / self.sim["calibration_path"]).read_text())
        norm = json.loads((root / self.sim["traffic"]["normalisation_path"]).read_text())
        data_cfg = yaml.safe_load((root / "configs" / "data.yaml").read_text())["processed"]
        self.trace = load_azure_2023(
            root / "data" / "raw" / data_cfg["source_file"], drop_failures=True
        )
        self.train_fraction = data_cfg["train_fraction"]
        cut = self.trace["arrival_s"].iloc[0] + self.train_fraction * np.ptp(
            self.trace["arrival_s"]
        )
        self.est_output_tokens = float(
            self.trace.loc[self.trace["arrival_s"] < cut, "output_tokens"].mean()
        )
        self.params = SimParams.from_config(
            self.sim, self.sim["layout"], self.est_output_tokens, norm["constants"]["prompt_tokens"]
        )
        self.params.interference_model = self.calib.get("interference_model", "A")

    def cluster(
        self,
        mode: str = "agents",
        global_policy=None,
        record_events: bool = False,
        **param_overrides,
    ):
        params = SimParams(**{**self.params.__dict__, **param_overrides})
        return Cluster(params, self.calib["classes"], mode, global_policy, record_events)

    def stream(self, rate_rps: float, seed: int, split: str) -> list:
        return sample_stream(self.trace, rate_rps, seed, split, train_fraction=self.train_fraction)


def local_actions(policy):
    """Wrap a LocalPolicy as an actions function for run_episode: act(obs, mask), or, for rules
    that need to know which agent they are (RouteToFast), act_agent(index, obs, mask).
    """

    def fn(obs, infos):
        out = {}
        for i, name in enumerate(obs):
            if not infos[name]["decide"]:
                out[name] = 0
            elif hasattr(policy, "act_agent"):
                out[name] = int(policy.act_agent(i, obs[name], infos[name]["mask"]))
            else:
                out[name] = int(policy.act(obs[name], infos[name]["mask"]))
        return out

    return fn


def run_episode(
    cluster: Cluster, stream: list, seed: int, act_fn=None, collect_transitions: bool = False
):
    """Play `stream` to the end. act_fn(obs, infos) -> {agent: action}; None for global mode.

    Returns (metrics, transitions). transitions is [] unless collect_transitions.
    """
    obs, infos = cluster.reset(stream, seed)
    transitions: list = []
    while not cluster.finished:
        actions = act_fn(obs, infos) if act_fn is not None else {}
        obs, _, _, _, infos = cluster.step(actions)
        if collect_transitions:
            transitions.extend(cluster.pop_transitions())
    return summarise(cluster), transitions


def save_events(cluster: Cluster, path: Path) -> None:
    """Replay event log of the episode just played (one JSON object per line)."""
    with open(path, "w") as f:
        for e in cluster.run.events:
            f.write(json.dumps(e) + "\n")
