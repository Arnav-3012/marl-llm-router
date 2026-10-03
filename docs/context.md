# MARL LLM Router — Project Context
Owner: Arnav · Course: AAI (RL & Multi-Agent Systems) mini project · Group: E035, E032 · Deadline: 2026-10-27 · Last updated: 2026-10-03 (S.8)

## One line
Independent Double-DQN agents, one per heterogeneous LLM server, learn Accept/Forward/Defer routing in a simulator calibrated on real llama.cpp servers. We measure goodput vs strong heuristics, a cost–latency Pareto frontier, the price of partial observability, and the sim-to-real gap; then ship it as a reproducible, demo-able project.

## Questions
1. Do learned agents match or beat SED and cache-aware routing on goodput?
2. Does sweeping λ trace a cost–latency Pareto frontier that fixed rules cannot?
3. Price of partial observability: decentralised k=0/1/full vs a centralised DQN.

## Positioning
Learning + CV project, not a research paper, not RLHF. Train in simulation; real servers for calibration and validation only. Repo private until the course is graded, then public (MIT).

## Pipeline
Profile (real) → Calibrate (profiling/calibration.json) → Train (sim) → Deploy (FastAPI router on real servers) → Compare (metrics + sim-to-real gap) → Showcase (Docker, HF Space demo, video)

## Environment
- N=4 servers, 2 classes: fast-expensive, slow-cheap. Real: llama-server; fast = Qwen2.5-3B Q4 on Metal; slow = 0.5–1.5B or CPU-only (-ngl 0).
- Request: arrival, prompt tokens P, output tokens O, conversation id (source: next line), TTFT target, TPOT target, hops, defers. Sampled from Azure LLM Inference Trace 2023; burst tests from BurstGPT.
- conversation id: BurstGPT Session ID (conversation-mode rows only); Azure 2023 has none, see ADR-009
- Service: T = a·(P − P_cached) + Σ t_step(B_i), with t_step(B) = t0 + k·B. a, t0, k, cache speedup and interference come only from calibration.json.
- Capacity = KV token budget. Time = discrete ticks, dt set in config.
- Entry: each request lands at one entry agent chosen uniformly at random (seeded; entry_rule: uniform in configs/sim.yaml, ADR-013); Forward passes it on.
- Env API: PettingZoo ParallelEnv shape.

## Agent
- Observation in [0,1]: own expected wait, own KV fullness, prompt size, slack on this server, hop count, neighbour mean wait within radius k (0 when k=0), prefix-hit fraction (cache variant).
- Actions: Accept / Forward (max 2 hops) / Defer (max D). Illegal actions masked. No legal action left → drop; it counts against the last holder in per-server metrics.
- Reward: r = R_SLA − λ·C − KV term − β·B_t, per decision transition (ADR-010, ADR-014). R_SLA: +10 met both targets, −10 missed a target, −5 dropped (shared by every agent that acted on the request, no extra charge). C is per request, charged at resolution to the serving agent's Accept transition: class price × service seconds attributed to the request (prefill in full, each decode step split across the batch), with Σ_j C_j = Σ_i c_i × busy_seconds_i. KV term: −w_kv × fraction of the request's resident ticks with KV > 80%, serving agent, at resolution (replaces "−1 per step"). β·B_t: every transition, B_t = cluster breach rate over the last W steps sampled at its decision tick. Outcomes credited at resolution with the decision-time state.
- Learner: Independent Double DQN, MLP 7→64→64→3 ReLU, Huber loss, Adam, target net, replay buffer 20–50k, ε 1.0→0.05, γ=0.99, gradient clip 10.
- Reference: centralised DQN as the upper bound. Future work: VDN.

## Baselines (same traffic as RL)
Random, Round-robin, JSQ, Po2, SED, Cache-aware — each in local (per-agent, same observation and k as the agents) and global (full state) form where applicable, see ADR-012. Cache-aware score: overlap − w·load.

## Metrics
- Headline: goodput.
- Latency: TTFT, TPOT p50/p95 (p99 if enough requests), E2E.
- Outcomes: SLA attainment, breach rate, drop rate, cost per request, cache hit rate, utilisation, Jain's index.
- Training health: return, TD loss, mean Q, ε, action histogram.
- Stats: 5 seeds, mean ± 95% CI, ε=0 on held-out traffic.
- Sim-to-real gap = |sim − real| / real, computed for SED first.

## Experiments
- E1: baselines vs MARL at ρ ∈ {0.5, 0.8, 0.95}
- E2: cooperation term on/off
- E3: λ ∈ {0, 0.25, 0.5, 1, 2} → Pareto frontier
- E4: k ∈ {0, 1, full} vs centralised
- E5: train at ρ=0.8 → test at 0.95 and on BurstGPT
- E6: specialisation (slack of accepted requests by server class)
- E7: sim vs real

## Phases
- S Setup: repo scaffold, docs, GitHub (private)
- M0 Data: Azure 2023 + BurstGPT download, EDA, normalisation constants
- M0.5 Profiling: llama-server benchmarks on M4 Pro → calibration.json (timebox 6h)
- M1 Simulator + heuristics: request/server/KV/prefix cache/cluster, metrics, all baselines, conservation test
- M2 Single-agent DDQN
- M3 Multi-agent: independent DDQN N=4, cooperation term, centralised reference
- M4 Experiments: E1–E6
- M5 Report + viva — course deliverable ends here
- M6 Real deploy on M4 Pro: FastAPI router, trace replay, E7 sim-vs-real
- M7 Showcase: Docker + compose, Gradio demo on Hugging Face Spaces (free CPU, simulator mode), 2-min demo video, README results table, repo public after grading
- M8 Kaggle 2×T4 + vLLM real-cluster validation (stretch)
Ordering rule: nothing from M6+ starts before M5's charts exist.

## Showcase spec (M7)
- Docker: image for router + replayer + simulator/eval. Compose profiles: (a) `cpu` — llama-server CPU containers + router + replay, runs anywhere; (b) `host` — router/replay in Docker, llama-servers run natively on the Mac (Docker on macOS cannot use the Metal GPU), reached via host.docker.internal.
- HF Space (Gradio, CPU): loads trained policy weights + calibration.json, runs the simulator live. Controls: λ, load ρ, visibility k, policy (SED / cache-aware / MARL). Shows: routing decisions per server, TTFT/cost time series, the policy's point on the precomputed Pareto frontier. No LLMs served.
- Demo video: real M6 router on the Mac, ≤ 2 min, linked in README.

## Tech stack
Python 3.11 · uv + pyproject.toml · PyTorch (mps→cpu) · numpy, pandas, scipy · YAML configs → dataclasses · CSV logs + matplotlib, tqdm · pytest, ruff · pettingzoo (dev, API test) · llama.cpp llama-server + Qwen2.5 GGUF Q4_K_M · FastAPI, uvicorn, httpx · Docker + compose · Gradio + Hugging Face Spaces · (stretch) vLLM on Kaggle.

## Ownership map
- Tier A (Arnav types; Claude Code teaches with faded worked examples): profiling/fit_calibration.py, sim/{server, kv_cache, prefix_cache, cluster, metrics}.py, policies/heuristics.py, agents/*, train/loop.py, eval/{stats, pareto}.py, router/{observation, policy_router}.py
- Tier B (Claude Code writes): config, utils, data/traces, sim/request, scripts, plotting, eval/evaluate, router/{app, server_client}, profiling/bench_server, tests, configs, docs, docker/*, demo/* (Gradio app)

## Working rules
Claude never runs commands (gives them instead) and never commits. Tier A default = faded worked examples: predict → explain → code part → Arnav types (no copy-paste) → explain-back → rebuild task. Repeated patterns = skeleton first. "challenge" = spec + skeleton + tests only. Viva-critical pieces (reward, DDQN update, SED, CI) rewritten once from memory.

## Interview-readiness (ADR-008)
- After every Tier A task: 3 questions (explain, break-it, justify), answered by Arnav in his own words in docs/viva.md before any answer is shown; Claude grades correct / partly / wrong; "wrong" goes to Revisit and is re-asked next session.
- Headline numbers live in docs/numbers.md, filled only from results/ files with the source path; never from memory.
- Break-it experiments at M2 and M3 with hypotheses written in docs/viva.md before the run.
- Reward, DDQN update, SED and CI calculation are rewritten from memory in a blank file, then diffed against the real one.
- Files: docs/viva.md (viva log, Revisit, Break-it log), docs/numbers.md (numbers table skeleton for the metrics and E1–E7).

## Constraints / out of scope
- Constraints: M4 Pro 24GB, ₹0 budget.
- Out of scope: training on real GPUs, public hosting of live LLMs, batching internals beyond t0 + k·B, prefill/decode disaggregation, CTDE (future work), RLHF.