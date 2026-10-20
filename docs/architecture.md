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
| src/marl_lb/data/traces.py | trace loaders and stream sampler | B |
| src/marl_lb/data/processed.py | normalisation constants (99th percentile, clip to [0,1]), time-ordered train/held-out split | A |
| notebooks/01_trace_eda.ipynb | trace EDA (analysis cells); skeleton is B | A (Claude writes since 2026-10-20, RULES.md #3) |
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
Decision protocol (ADR-013): each agent decides on at most one request per tick, the oldest it holds (FIFO); other held requests wait (counts toward TTFT, not a Defer, no cost).
Idle-agent rule (ADR-013): an agent holding no request this tick gets a zero observation (7 zeros) and an all-False mask; it takes no action and no transition is recorded.
Entry rule (ADR-013): each arriving request lands at an entry agent chosen uniformly at random (seeded); config field entry_rule: uniform in configs/sim.yaml.
Deferred-to-back rule (ADR-013): a deferred request moves to the back of the agent's held queue, so the oldest request is not re-decided every tick.
Forward-target rule (ADR-013, SED-style): the environment sends a forwarded request to the visible neighbour (within radius k) minimising expected wait + this request's estimated service time on that neighbour, ties to the lowest index; the agent only decides whether to forward. Forward is masked when k=0 or at the hop limit; Defer is masked at the defer limit.

### config
- load_config(path: Path) -> Config
- resolve_experiment(path: Path, overrides: dict) -> list[RunSpec]   # sweep x seeds expansion

### utils
- seed_everything(seed: int) -> None
- make_run_dir(exp: str, seed: int, config: Config) -> Path   # results/<exp>/<timestamp>_seed<k>/, config copied in
- CsvLogger(path: Path).log(row: dict[str, float]) -> None

### data.traces
- load_azure_2023(path: Path, drop_failures: bool = False) -> DataFrame
- load_burstgpt(path: Path, drop_failures: bool = False) -> DataFrame
  # Canonical schema: arrival_s (float64, s from the file's first request), prompt_tokens (int64), output_tokens (int64), session_id (nullable string), source (file stem), then BurstGPT extras (Model, Log Type, Elapsed time if present). df.attrs["n_failures"] = rows with output_tokens == 0, counted before any dropping. ValueError names the file on missing column, decreasing time or negative tokens.
- sample_stream(trace: DataFrame, arrival_rate_rps: float, seed: int, split: str, *, train_fraction: float | None = None, sessions: dict | None = None) -> list[StreamRequest]   # split: "train" | "heldout"
  # trace = canonical Azure conv DataFrame without failure rows (ValueError otherwise, ADR-017); the part is cut with processed.time_split (train_fraction defaults to configs/data.yaml processed.train_fraction, sessions to configs/sessions.yaml). arrival_rate_rps in req/s: one factor rescales the clock so (n − 1) / (last − first) equals it; the first arrival is 0. The ρ → rate conversion lives in data/load.py (ADR-011, M1.28), not here. Same arguments give an identical list; inputs are not modified. The seed drives the conversation layer only (ADR-018, proposed).
- StreamRequest(arrival_s: float, prompt_tokens: int, output_tokens: int, conversation_id: int, turn_index: int, history_included: bool)   # frozen dataclass defined in data/traces.py because sim/request.py does not exist until M1.2; M1.2 maps it to sim.request.Request (id, arrival, conv_id, ... plus the fields the simulator adds). history_included: this turn re-sends the previous turn, so up to previous prompt + previous output tokens of its prompt are cacheable (M1.6 takes the min with its own prompt).
- session_plan(seed: int, index: int, sessions: dict) -> SessionPlan(n_turns, gaps_s, history_included)   # (seed, row index) only; no rate argument, so think times are never compressed (ADR-009)
- load_sessions_config(path=configs/sessions.yaml) -> dict ; summarise_stream(stream) -> dict   # realised follow-up share etc.

### data.processed (Tier A)
- time_split(df: DataFrame, train_fraction: float) -> TimeSplit(train, heldout, cutoff_s; n_train, n_heldout)
  # df sorted by arrival_s. Cut = t_min + train_fraction × (t_max − t_min) (split by duration, ADR-016): train is arrival_s < cutoff_s, held-out is arrival_s >= cutoff_s, so the parts are disjoint and same-instant requests stay together. arrival_s is not re-zeroed. ValueError on unsorted input, train_fraction outside (0, 1), or an empty part.
- fit_normalisation(train: DataFrame, features: list[str], percentile: float) -> dict[str, float]   # np.percentile (linear) per feature; ValueError if a constant is not > 0. Pass the TRAIN part only.
- normalise(df: DataFrame, constants: dict[str, float]) -> DataFrame   # value / constant clipped to [0, 1]; only the fitted features, float64
- build_processed(raw_path: Path, out_dir: Path, *, train_fraction: float, percentile: float, features: list[str]) -> dict
  # load_azure_2023(drop_failures=True) (ADR-017) → time_split → fit_normalisation on train → writes out_dir/train.csv, heldout.csv (canonical schema), normalisation.json {source, percentile, fitted_on: "train", n_fit_rows, constants: {feature: value}} and split.json {source, train_fraction, cutoff_s, n_train, n_heldout, n_failures_dropped}. Returns source, train_fraction, cutoff_s, n_train, n_heldout, n_failures_dropped, constants.
- CLI: `uv run python -m marl_lb.data.processed`; settings from the `processed` block of configs/data.yaml (source_file, out_dir, train_fraction, percentile, features). data/processed/* is gitignored, so the files are regenerated, not committed.
- The observation builder (M1.14) reads data/processed/normalisation.json → ["constants"][feature].

### profiling
- bench_server.py (Tier B): `uv run python -m profiling.bench_server [--smoke] [--only prefill,batch,joint,cache,interference]`. Starts the 4 llama-servers from configs/profiling.yaml (2 fast-expensive on Metal, 2 slow-cheap CPU-only), measures, and writes results/profiling/<timestamp>_seed<k>/ with one raw CSV per experiment and class (`prefill_<class>.csv`, `batch_<class>.csv`, `joint_<class>.csv`, `cache_<class>.csv`, `interference_<class>.csv`), `config_resolved.yaml`, `meta.json` (chip, RAM, macOS, llama.cpp version/commit, model files with sha256, server command lines, ctx size, threads, wall time per experiment, row counts) and the llama-server logs. Warm-up runs are discarded, not written. Prompts are token-id lists, so lengths are exact. Pure helpers: make_prompt, ttft_and_tpot, all_active_step_time, neighbour_order.
- fit_calibration.py (Tier A): `fit_prefill(df) -> {a, c, a_se, c_se, r2, shape{curved, quad_coef, quad_t}, residual_summary, ...}`; `fit_decode(df) -> {t0, k, ..., r2, n_runs}` (one value per run, not per request row); `fit_cache(df, a, c) -> {cached_token_cost_ratio r, cache_speedup = 1/r}`; `fit_interference(df, n_servers) -> {prefill, decode: {s, linear_r2, fixed_multiplier_slowdown, by_level[...]}}` (ADR-015 option A fit, with the per-level table for A/B/C); `fit_run(run_dir) -> dict` writes fit_output.json and fit_residuals.csv in the run directory and does NOT write profiling/calibration.json (M0.5.5, after ADR-015). CLI: `uv run python -m profiling.fit_calibration --run <dir>`.

### sim.request
- Request (sim/request.py, __slots__ class): id, arrival, prompt_tokens, output_tokens, conv_id, turn_index, history_included, ttft_target, tpot_target, hops, defers, plus runtime state (holder, server, status, cached_tokens, pf_left, dec_left, t_enqueue, t_first, t_done, attributed_s, resident_ticks, hot_ticks, decisions). `Request.from_stream(i, StreamRequest, ttft_target, tpot_target)` maps the M0.6 record (ADR-018). Properties ttft, tpot, e2e; `sla_met()`.

### sim.server (Tier A)
- Server(index, class_name, cls: dict, sim: dict, est_output_tokens) with cls from calibration.json classes (a, cached_token_cost_ratio, t0, k, s_prefill, s_decode, kv_token_budget, max_batch, price_per_busy_second).
- Server.enqueue(req, now) ; Server.advance(t_start, t_end, n_other_busy, n_servers) -> list[Request] finished in the window (exact, not tick-by-tick; result independent of how the window is cut) ; Server.end_of_tick(kv_threshold)
- Server.expected_wait() (remaining prefill + expected remaining decode, using only router-visible information) ; est_service_seconds(req) ; can_accept(req) ; kv_fullness() ; busy_seconds ; n_present() ; is_busy()
- Interference (ADR-015): prefill seconds x (1 + s_prefill * n_other_busy/(N-1)), decode step x (1 + s_decode * ...).

### sim.cluster (Tier A)
- SimParams (typed record of configs/sim.yaml; `SimParams.from_config(sim, layout, est_output_tokens, prompt_norm)`).
- Cluster(params, classes, mode="agents"|"global", global_policy=None, record_events=False): ParallelEnv shape. reset(stream, seed) -> (obs, infos); step(actions) -> (obs, rewards, terminations, truncations, infos); agents "agent_i"; infos[agent] = {mask (3 bools), decide (bool), req_id}. pop_transitions() -> list[Transition(agent, obs, mask, action, tick, reward, next_obs, next_mask, truncated)] (ADR-010: complete when the request has resolved AND the agent has decided again). `run` holds per-episode state (requests, resolved, events, discarded_end, drops_unacted, drops_by_holder, l_integral).
- Replay event log (ADR-020): with record_events=True, run.events is a list of {tick, t, e, ...}: e in arrive (req, entry, p, o), act (agent, req, action), forward (req, src, dst), servers (queue[], active[], kv[]), resolve (req, status, ok, server). eval.evaluate.save_events writes it as JSON lines; scripts/export_dashboard_data.py turns it into capped frames.
- slice_stream(stream, start_s, length_s): a window of a stream, re-zeroed (training episodes).

### sim.metrics (Tier A)
- summarise(cluster) -> dict: goodput_rps (SLA-met completions / arrival window), throughput_rps, sla_attainment, breach_rate, drop_rate, ttft p50/p95/p99, tpot p50/p95, e2e p50/p95, cost_per_request, cache_hit_rate, utilisation, jain_utilisation, completed_by_class, little_L, little_lambda_W, decisions, discarded_end_transitions, drops_unacted, drops_by_holder. jain_index(x), percentile(v, q).

### policies.heuristics (Tier A)
- Local (act(obs[7], mask[3]) -> action): AcceptAll (random routing via the uniform entry rule), SEDLocal, CacheAwareLocal(w). Global (assign(cluster, req) -> server | None): RandomGlobal, RoundRobin, JSQ, Po2, SEDGlobal, CacheAwareGlobal(w, wait_scale_s). Local JSQ/Po2 forms are not implemented (demo track).

### agents and train (Tier A)
- agents.networks: QNetwork(obs_dim=7, hidden=(64,64), n_actions=3), masked_argmax(q, mask). agents.replay_buffer: ReplayBuffer(capacity).add/sample. agents.dqn_agent: DQNAgent(cfg, seed).act(obs, mask, epsilon) / remember(tr) / ready() / learn() -> (loss, mean_q), epsilon_at(episode, cfg). No terminal flag (truncation, ADR-010); reward_scale in dqn.yaml.
- train.loop: make_agents(cfg, n, seed, solo=None), agent_actions(agents, obs, infos, epsilon, fallback), run_learning_episode(...), train(world, cfg, seed, log_path, progress, solo) (episode = a seeded window of the train stream), greedy_actions(agents, fallback).

### eval
- eval.evaluate: World (sim.yaml + overrides, calibration.json, normalisation.json, the Azure trace; `.cluster(...)`, `.stream(rate, seed, split)`), run_episode(cluster, stream, seed, act_fn), local_actions(policy), save_events. eval.experiments: suite(world, cache_w), eval_baseline(...), eval_agents(...) (every policy gets the same held-out stream for a given (rate, seed)). eval.saturation: point_criteria, is_saturated, find_lambda_sat (ADR-011). eval.stats: mean_ci (Student t), aggregate. eval.pareto: pareto_front. data.load: rho_to_rate(rho, lambda_sat).
- scripts (heavy jobs are run by Arnav, docs/RUN.md): saturation_sweep, evaluate, run_experiment, run_stage_{1,2,3}.sh, export_dashboard_data, make_fixture_data.

### sim.kv_cache / sim.prefix_cache (Tier A)
- KVCache(budget_tokens: int).can_admit(tokens: int) -> bool ; .admit(req_id, tokens) ; .release(req_id) ; .fullness() -> float
- PrefixCache(capacity).hit_tokens(req: Request) -> int ; .insert(req: Request) -> None

### sim.cluster (Tier A, PettingZoo ParallelEnv shape)
- reset(seed: int | None) -> (obs: dict[agent, ndarray[7]], info: dict)
- step(actions: dict[agent, int]) -> (obs, rewards: dict[agent, float], terminations, truncations, infos)
- action_mask(agent) -> ndarray[3] of bool   # all-False for an idle agent
- Direct-assignment mode (for global policies, ADR-012): step_direct(policy: GlobalPolicy) -> (cluster_state, infos); each arriving request is placed on policy.assign(cluster_state, request), bypassing agents, Forward and Defer; same metrics and same conservation invariant.
- ClusterState: per-server expected wait, KV fullness, queue length, class, and prefix-hit tokens for the request being placed.
- Invariant: every arrived request ends exactly once as completed or dropped (conservation).

### sim.metrics (Tier A)
- MetricsCollector.record(event) -> None ; .summary() -> dict[str, float]   # goodput, ttft/tpot p50/p95, e2e, sla, breach, drop, cost/request, cache hit, utilisation, jain
- Cost attribution (ADR-014): per-request cost C_j (prefill seconds in full, each decode step's t_step(B_i) split equally across the B_i requests in that step, times class price) must satisfy Σ_j C_j = Σ_i c_i × busy_seconds_i over an episode, so cost per request stays consistent with the reward. Drops count against the last holder here (per-server stats); reward credit follows ADR-010.

### policies.heuristics (Tier A)
- LocalPolicy.act(obs[7], mask[3]) -> int   # action in {0 Accept, 1 Forward, 2 Defer}; may use only the 7 observation features (ADR-012)
- GlobalPolicy.assign(cluster_state, request) -> int   # server index, full cluster state, used in direct-assignment mode
- One per baseline: random, round_robin (stateless), and jsq, po2, sed, cache_aware each in a local and a global form

### agents (Tier A)
- Transition(obs[7], mask[3], action: int, decision_tick: int, reward: float, next_obs[7], next_mask[3], truncated: bool)   # ADR-010: next_obs = the agent's next decision observation; discount γ per decision; episode end is truncation (bootstrap)
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

## Ownership map (since 2026-10-20 Claude Code writes, runs and commits both tiers; the tier marks viva importance)

- Tier A: notebooks/01_trace_eda.ipynb (analysis cells), data/processed.py, profiling/fit_calibration.py, sim/{server,kv_cache,prefix_cache,cluster,metrics}.py, policies/heuristics.py, agents/*, train/loop.py, eval/{stats,pareto}.py, router/{observation,policy_router}.py
- Tier B: config, utils, data/{traces,load}, download script, stream sampler, sim/request, scripts, plotting, eval/evaluate, router/{app,server_client}, profiling/bench_server, tests, configs, docs, docker/*, demo/*
- Not in map: ask which tier (CLAUDE.md). Never downgrade A to B.
