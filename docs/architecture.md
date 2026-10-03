# Architecture

Source of truth for module map, interfaces and tiers. Update when an interface changes (CLAUDE.md, end of session).
Signatures below are text contracts, not code. Types are indicative; finalise per-module in its task.

## Data flow

```
 PROFILE            CALIBRATE             TRAIN               DEPLOY              COMPARE             SHOWCASE
 (real servers)     (fit params)          (simulator)         (real servers)      (metrics)           (demo)

 llama-server  -->  fit_calibration  -->  sim/cluster   -->   router/app     -->  eval/evaluate  -->  docker compose
 bench_server       |                     + agents/*          + policy_router      + eval/stats        demo/app.py (HF Space)
 raw timings        v                     + train/loop        + observation        + eval/pareto       2-min video
                    profiling/            |                   |                    sim-to-real gap
                    calibration.json      v                   v                    (SED first)
                    (only source of       weights (.pt)       real-side metrics
                     server physics)

 data/traces (Azure 2023, BurstGPT) --> request streams feeding both the simulator and the replayer
```

## Module map

| Path | Purpose | Tier |
|---|---|---|
| profiling/bench_server.py | benchmark real llama-server | B |
| profiling/fit_calibration.py | fit a, t0, k, cache speedup, interference | A |
| src/marl_lb/config.py | YAML -> dataclasses | B |
| src/marl_lb/utils/{seeding,logging,io}.py | seeds, CSV logs, run dirs | B |
| src/marl_lb/data/traces.py | trace loading and sampling | B |
| src/marl_lb/data/load.py | ρ = λ_arr / λ_sat helper, ρ → arrival rate in req/s (ADR-011) | B |
| src/marl_lb/sim/request.py | request record | B |
| src/marl_lb/sim/server.py | service time, batching, queue | A |
| src/marl_lb/sim/kv_cache.py | KV token budget | A |
| src/marl_lb/sim/prefix_cache.py | prefix hits and speedup | A |
| src/marl_lb/sim/cluster.py | ParallelEnv, ticks, reward | A |
| src/marl_lb/sim/metrics.py | goodput, latency, fairness | A |
| src/marl_lb/policies/heuristics.py | six baselines | A |
| src/marl_lb/agents/{networks,replay_buffer,dqn_agent,central_dqn}.py | learners | A |
| src/marl_lb/train/loop.py | training loop | A |
| src/marl_lb/eval/evaluate.py | evaluation runner | B |
| src/marl_lb/eval/{stats,pareto}.py | mean/CI, Pareto frontier | A |
| src/marl_lb/router/{app,server_client}.py | FastAPI app, httpx client | B |
| src/marl_lb/router/{observation,policy_router}.py | live observation, live policy | A |
| scripts/*.py | CLI entry points | B |
| docker/*, demo/* | showcase | B |
| tests/*, configs/*, docs/* | verification, config, docs | B |

## Public interfaces

Observation (7 floats in [0,1]): own expected wait, own KV fullness, prompt size, slack on this server, hop count, neighbour mean wait within radius k (0 if k=0), prefix-hit fraction (0 if cache variant off).
Actions: 0 Accept, 1 Forward, 2 Defer. Illegal actions masked.

### config
- load_config(path: Path) -> Config
- resolve_experiment(path: Path, overrides: dict) -> list[RunSpec]   # sweep x seeds expansion

### utils
- seed_everything(seed: int) -> None
- make_run_dir(exp: str, seed: int, config: Config) -> Path   # results/<exp>/<timestamp>_seed<k>/, config copied in
- CsvLogger(path: Path).log(row: dict[str, float]) -> None

### data.traces
- load_azure_2023(path: Path) -> DataFrame
- load_burstgpt(path: Path) -> DataFrame
- sample_stream(trace: DataFrame, rho: float, seed: int, split: str) -> list[Request]   # split: "train" | "heldout"

### sim.request
- Request(id: int, arrival: float, prompt_tokens: int, output_tokens: int, conv_id: int, ttft_target: float, tpot_target: float, hops: int, defers: int)

### sim.server (Tier A)
- Server(class_cfg, calibration: dict)
- Server.enqueue(req: Request, tick: int) -> None
- Server.step(tick: int) -> list[CompletedRequest]
- Server.expected_wait() -> float ; Server.kv_fullness() -> float ; Server.busy_seconds -> float

### sim.kv_cache / sim.prefix_cache (Tier A)
- KVCache(budget_tokens: int).can_admit(tokens: int) -> bool ; .admit(req_id, tokens) ; .release(req_id) ; .fullness() -> float
- PrefixCache(capacity).hit_tokens(req: Request) -> int ; .insert(req: Request) -> None

### sim.cluster (Tier A, PettingZoo ParallelEnv shape)
- reset(seed: int | None) -> (obs: dict[agent, ndarray[7]], info: dict)
- step(actions: dict[agent, int]) -> (obs, rewards: dict[agent, float], terminations, truncations, infos)
- action_mask(agent) -> ndarray[3] of bool
- Invariant: every arrived request ends exactly once as completed or dropped (conservation).

### sim.metrics (Tier A)
- MetricsCollector.record(event) -> None ; .summary() -> dict[str, float]   # goodput, ttft/tpot p50/p95, e2e, sla, breach, drop, cost/request, cache hit, utilisation, jain

### policies.heuristics (Tier A)
- policy(obs_or_state, mask) -> int ; one callable per baseline: random, round_robin, jsq, po2, sed, cache_aware

### agents (Tier A)
- QNetwork(obs_dim=7, hidden=(64,64), n_actions=3).forward(x: Tensor[B,7]) -> Tensor[B,3]
- ReplayBuffer(capacity).push(transition) ; .sample(batch: int) -> Batch ; len()
- DQNAgent.act(obs, mask, eps: float) -> int ; .learn(batch) -> dict[str, float] ; .sync_target() ; .save(path) ; .load(path)
- CentralDQN: same shape, joint observation -> joint action

### train.loop (Tier A)
- train(cfg: Config, seed: int, run_dir: Path) -> TrainResult   # logs return, TD loss, mean Q, epsilon, action histogram

### eval
- evaluate(policy, cfg: Config, seeds: list[int], rho: float, source: str) -> DataFrame   (B)
- mean_ci95(values: ndarray) -> (mean: float, half_width: float)   (A)
- pareto_front(points: ndarray[n,2]) -> ndarray[m]   # indices of non-dominated (cost, latency)   (A)

### router
- app: POST /v1/route (request) -> response from chosen server   (B)
- ServerClient(url).complete(prompt, max_tokens) -> Completion with timings ; .state() -> ServerState   (B)
- build_observation(server_states, request, k: int) -> ndarray[7]   (A; must equal sim observation)
- PolicyRouter(policy).route(request) -> RoutingDecision(action, target)   (A)

### scripts
- train.py --config --seed ; evaluate.py --config --policy ; run_experiment.py --experiment ; plot.py --exp ; replay_trace.py --trace --router-url

## Ownership map (Tier A: Arnav types; Tier B: Claude Code writes)

- Tier A: profiling/fit_calibration.py, sim/{server,kv_cache,prefix_cache,cluster,metrics}.py, policies/heuristics.py, agents/*, train/loop.py, eval/{stats,pareto}.py, router/{observation,policy_router}.py
- Tier B: config, utils, data/{traces,load}, sim/request, scripts, plotting, eval/evaluate, router/{app,server_client}, profiling/bench_server, tests, configs, docs, docker/*, demo/*
- Not in map: ask which tier (CLAUDE.md). Never downgrade A to B.
