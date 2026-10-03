# Phase plans

**Ordering rule (RULES.md #13): nothing from M6 onward starts before M5's charts exist in results/.**
Tick a task only after Arnav pastes passing test output (RULES.md #10). Each task ≤ 4h. [B] test tasks come before the [A] task they cover. One task = one commit: "<phase>: <what> (<metric if any>)".

## Phase S — Setup
- [ ] S.1 [B] Repo scaffold: folder tree, module docstrings, pyproject, .gitignore — done when: `uv sync` succeeds and `ruff check .` is clean
- [ ] S.2 [B] Configs and docs (architecture, ADR-001..007, templates, README) — done when: files reviewed and approved by Arnav
- [ ] S.3 [B] Git init, commit "S: repo scaffold", private GitHub repo pushed — done when: `git log` shows the commit and the remote exists

## Phase M0 — Data
- [ ] M0.1 [B] Download Azure LLM Inference 2023 and BurstGPT into data/raw (read-only) — done when: files present, row counts printed
- [ ] M0.2 [B] data/traces.py loaders — done when: tests/test_traces.py passes
- [ ] M0.3 [B] Notebook 01_trace_eda: arrival rates, P/O distributions, burstiness — done when: notebook runs top to bottom
- [ ] M0.4 [B] Normalisation constants to data/processed/normalisation.json, train/held-out split — done when: tests/test_traces.py covers split with no overlap
- [ ] M0.5 [B] Seeded stream sampler for a given ρ — done when: same seed gives identical stream (test passes)

## Phase M0.5 — Profiling (timebox 6h)
- [ ] M0.5.1 [B] Install llama.cpp, fetch Qwen2.5-3B Q4_K_M and a slow-class model — done when: llama-server answers a request
- [ ] M0.5.2 [B] profiling/bench_server.py: TTFT, TPOT at varying prompt length and batch size, prefix-cache reuse — done when: raw CSV written for both classes
- [ ] M0.5.3 [B] Tests for the fitting maths on synthetic data (known a, t0, k recovered) — done when: tests/test_fit_calibration.py passes
- [ ] M0.5.4 [A] profiling/fit_calibration.py: fit a, t0, k, cache speedup, interference — done when: tests/test_fit_calibration.py passes
- [ ] M0.5.5 [B] Write calibration.json, plot fit vs measured in notebook 02 — done when: fit residuals plotted and reviewed
- [ ] M0.5.6 [B] ADR: server class split, class prices, KV budgets — done when: ADR approved

## Phase M1 — Simulator + heuristics
- [ ] M1.1 [B] config.py + utils (seeding, logging, io) with tests — done when: tests/test_config.py and tests/test_utils.py pass
- [ ] M1.2 [B] sim/request.py + fill dt, episode_ticks, targets in configs via ADR — done when: tests/test_request.py passes
- [ ] M1.3 [B] tests/test_kv_cache.py (admit, release, full, fullness) — done when: tests written and failing as expected
- [ ] M1.4 [A] sim/kv_cache.py — done when: tests/test_kv_cache.py passes
- [ ] M1.5 [B] tests/test_prefix_cache.py (hit, miss, eviction, speedup) — done when: tests written
- [ ] M1.6 [A] sim/prefix_cache.py — done when: tests/test_prefix_cache.py passes
- [ ] M1.7 [B] tests/test_server.py (service time formula, batching, queue order) — done when: tests written
- [ ] M1.8 [A] sim/server.py service time + batching — done when: tests/test_server.py passes
- [ ] M1.9 [B] tests/test_cluster.py (reset/step shapes, masks, hops/defers limits, drop charging) + PettingZoo API-shape test — done when: tests written
- [ ] M1.10 [A] sim/cluster.py tick loop, routing actions, masks — done when: tests/test_cluster.py passes
- [ ] M1.11 [B] tests/test_conservation.py (no request lost or double-counted) — done when: test written
- [ ] M1.12 [A] Conservation fixes in cluster — done when: tests/test_conservation.py passes
- [ ] M1.13 [B] tests/test_metrics.py (goodput, percentiles, Jain's index on hand-computed cases) — done when: tests written
- [ ] M1.14 [A] sim/metrics.py — done when: tests/test_metrics.py passes
- [ ] M1.15 [B] tests/test_heuristics.py (each policy on hand-built states) — done when: tests written
- [ ] M1.16 [A] policies/heuristics.py: Random, Round-robin, JSQ, Po2 — done when: tests for these pass
- [ ] M1.17 [A] policies/heuristics.py: SED, Cache-aware — done when: tests/test_heuristics.py passes (viva: rewrite SED from memory)
- [ ] M1.18 [B] eval/evaluate.py + scripts/evaluate.py baseline run on held-out traffic — done when: results/baselines/ written with config copied
- [ ] M1.19 [B] Sanity check: SED beats Random at ρ=0.8 in results/ — done when: numbers reviewed with Arnav

## Phase M2 — Single-agent DDQN
- [ ] M2.1 [B] tests/test_networks.py (shapes, masked argmax) — done when: tests written
- [ ] M2.2 [A] agents/networks.py — done when: tests/test_networks.py passes
- [ ] M2.3 [B] tests/test_replay_buffer.py (capacity, overwrite, sample shapes) — done when: tests written
- [ ] M2.4 [A] agents/replay_buffer.py — done when: tests/test_replay_buffer.py passes
- [ ] M2.5 [B] tests/test_dqn_agent.py (DDQN target on a hand-computed batch, masked ε-greedy, target sync) — done when: tests written
- [ ] M2.6 [A] agents/dqn_agent.py act + epsilon — done when: act tests pass
- [ ] M2.7 [A] agents/dqn_agent.py DDQN update + target network — done when: tests/test_dqn_agent.py passes (viva: rewrite update from memory)
- [ ] M2.8 [B] tests/test_train_loop.py (pending transitions credited at resolution, ADR-004) — done when: tests written
- [ ] M2.9 [A] train/loop.py single-agent episodes — done when: tests/test_train_loop.py passes
- [ ] M2.10 [B] Fill lr, batch size, target update, warmup, ε decay in dqn.yaml via ADR — done when: ADR approved
- [ ] M2.11 [B] Train one agent against heuristic neighbours; plot return, TD loss, mean Q, ε, action histogram — done when: learning curve in results/ shows improvement over Random

## Phase M3 — Multi-agent
- [ ] M3.1 [B] tests for independent training (N=4 agents, per-agent buffers and rewards) — done when: tests written
- [ ] M3.2 [A] train/loop.py independent DDQN N=4 — done when: tests pass
- [ ] M3.3 [B] tests for reward terms (SLA, cost C, KV penalty, breach rate B_t) — done when: tests/test_reward.py written
- [ ] M3.4 [A] Reward in cluster: R_SLA − λ·C − β·B_t — done when: tests/test_reward.py passes (viva: rewrite reward from memory)
- [ ] M3.5 [B] ADR: β value and breach window W — done when: ADR approved
- [ ] M3.6 [B] tests for neighbour observation with k ∈ {0, 1, full} — done when: tests written
- [ ] M3.7 [A] Neighbour-wait observation in cluster — done when: tests pass
- [ ] M3.8 [B] tests/test_central_dqn.py — done when: tests written
- [ ] M3.9 [A] agents/central_dqn.py — done when: tests/test_central_dqn.py passes
- [ ] M3.10 [B] Smoke run: 5 seeds, N=4, no NaNs, conservation holds — done when: results/ written for all seeds

## Phase M4 — Experiments E1–E6
- [ ] M4.1 [B] tests/test_stats.py (mean, 95% CI against known values) — done when: tests written
- [ ] M4.2 [A] eval/stats.py — done when: tests/test_stats.py passes (viva: rewrite CI calc from memory)
- [ ] M4.3 [B] tests/test_pareto.py (dominated points, ties, single point) — done when: tests written
- [ ] M4.4 [A] eval/pareto.py — done when: tests/test_pareto.py passes
- [ ] M4.5 [B] scripts/run_experiment.py driving sweep × seeds with config copied per run — done when: dry-run lists all runs
- [ ] M4.6 [B] E1 baselines vs MARL at ρ ∈ {0.5, 0.8, 0.95}, 5 seeds — done when: results/baselines/ complete
- [ ] M4.7 [B] E2 cooperation on/off — done when: results/cooperation/ complete
- [ ] M4.8 [B] E3 λ ∈ {0, 0.25, 0.5, 1, 2} sweep — done when: results/lambda_sweep/ complete
- [ ] M4.9 [B] E4 k ∈ {0, 1, full} vs centralised — done when: results/k_ablation/ complete
- [ ] M4.10 [B] E5 train ρ=0.8, test ρ=0.95 and BurstGPT — done when: results/load_generalization/ complete
- [ ] M4.11 [B] E6 specialisation: slack of accepted requests by server class — done when: analysis table written from results/
- [ ] M4.12 [B] scripts/plot.py: goodput bars with CI, Pareto, k ablation, training curves — done when: figures in reports/figures/

## Phase M5 — Report + viva (course deliverable ends here)
- [ ] M5.1 [B] Results tables from results/ only (no invented numbers) — done when: tables match files
- [ ] M5.2 [B] Report draft: method, experiments, answers to the 3 questions — done when: draft reviewed
- [ ] M5.3 [B] Limitations and threats (non-stationarity, sim fidelity, N=4) — done when: section reviewed
- [ ] M5.4 [B] Viva question bank and from-memory rewrites of reward, DDQN update, SED, CI — done when: Arnav completes each
- [ ] M5.5 [B] Final report to reports/final_report.md and slides if required — done when: submitted
- [ ] M5.6 [B] Gate check: M5 charts exist in results/ and reports/figures/ — done when: Arnav confirms (unlocks M6)

## Phase M6 — Real deploy (blocked until M5.6)
- [ ] M6.1 [B] Start N=4 llama-servers on the M4 Pro per configs/servers.yaml — done when: all health endpoints respond
- [ ] M6.2 [B] router/server_client.py with tests against a mock server — done when: tests/test_server_client.py passes
- [ ] M6.3 [B] tests/test_observation.py (live state equals sim observation for the same state) — done when: tests written
- [ ] M6.4 [A] router/observation.py — done when: tests/test_observation.py passes
- [ ] M6.5 [B] tests/test_policy_router.py (masking, hops, defers) — done when: tests written
- [ ] M6.6 [A] router/policy_router.py — done when: tests/test_policy_router.py passes
- [ ] M6.7 [B] router/app.py FastAPI endpoint — done when: tests/test_app.py passes with a mock backend
- [ ] M6.8 [B] scripts/replay_trace.py against the live router — done when: a short replay completes with metrics logged
- [ ] M6.9 [B] E7 sim vs real for SED: gap = |sim − real| / real — done when: gap table in results/
- [ ] M6.10 [B] E7 for the learned policy and cache-aware — done when: results/ complete

## Phase M7 — Showcase
- [ ] M7.1 [B] docker/Dockerfile for router + replayer + sim/eval — done when: image builds and `scripts/evaluate.py` runs inside
- [ ] M7.2 [B] docker-compose profile `cpu` — done when: compose up serves a routed request
- [ ] M7.3 [B] docker-compose profile `host` (host.docker.internal) — done when: router reaches native llama-servers
- [ ] M7.4 [B] Export trained policy weights to demo/weights/ and precompute the Pareto frontier — done when: files committed
- [ ] M7.5 [B] demo/app.py controls and simulation (λ, ρ, k, policy) — done when: runs locally
- [ ] M7.6 [B] demo/app.py plots: per-server decisions, TTFT/cost series, Pareto point — done when: plots render
- [ ] M7.7 [B] Deploy to Hugging Face Space (CPU) — done when: public Space URL works
- [ ] M7.8 [B] 2-minute demo video of the real M6 router — done when: video linked in README
- [ ] M7.9 [B] README results table, Reproduce section, MIT licence — done when: README complete from results/
- [ ] M7.10 [B] Make repo public after grading — done when: Arnav confirms

## Phase M8 — Kaggle 2×T4 + vLLM validation (stretch)
- [ ] M8.1 [B] Kaggle notebook launching vLLM on 2×T4 — done when: both servers respond
- [ ] M8.2 [B] Profile vLLM servers into a second calibration file — done when: calibration written
- [ ] M8.3 [B] Replay trace through the router on vLLM — done when: metrics logged
- [ ] M8.4 [B] Compare sim vs vLLM real — done when: gap table written
