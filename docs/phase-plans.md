# Phase plans

**If time is short, cut in this order: E6, E5, central reference in E4. Never cut baselines or seeds.**
**Before implementing any Tier A task, Arnav reads the test file and states in one line what each test checks.**
**Every task, Tier A or B, has a docs/viva.md entry per amended ADR-008 (written by Claude Code, self-checked by Arnav).**

**Ordering rule (RULES.md #13): nothing from M6 onward starts before M5's charts exist in results/.**
Tick a task only after Arnav pastes passing test output (RULES.md #10). Each task ≤ 4h. Every Tier A task is followed by a [B] "viva check" task (suffix `a`): 3 questions per ADR-008, self-checked by Arnav in docs/viva.md. Rewrite-from-memory tasks use suffix `b`. [B] test tasks come before the [A] task they cover. One task = one commit: "<phase>: <what> (<metric if any>)".
Task IDs in M1–M3 were renumbered in S.4, and M1 IDs again in S.5 (old M1.9 ρ helper moved after SED; old M1.12 split into three; ADR task inserted before reward tests) and in S.6 (ADR-012 task inserted at M1.21 and prototype run at M1.24; everything from the old M1.21 on shifted, so the S.5 log entry's M1.24–M1.27 are now M1.26–M1.29); M2 and M3 IDs unchanged. S.7 renumbered nothing: it adds one dotted task (M1.8.1) and edits task text only. S.8 renumbers nothing either: it adds M1.25.1 (ADR-011 approved), changes what M1.8.1 and M1.16 approve (M1.8.1 now ADR-012 and ADR-013; M1.16 now ADR-010 and ADR-014), removes the ADR-012 approval from M1.21, and edits task text; the IDs above are unchanged. Dotted suffixes (M1.8.1, M1.25.1) are used for new tasks from now on. M0 plan change (after S.8): M0.3 and M0.4 moved from Tier B to Tier A; added M0.3a, M0.3.1, M0.4a, M0.6a; no IDs changed. No other file references them.

## Phase S — Setup
- [x] S.1 [B] Repo scaffold: folder tree, module docstrings, pyproject, .gitignore — done when: `uv sync` succeeds and `ruff check .` is clean (Arnav confirmed both)
- [x] S.2 [B] Configs and docs (architecture, ADR-001..007, templates, README) — done when: files reviewed and approved by Arnav
- [x] S.2b [B] Interview-readiness patch (docs/viva.md, docs/numbers.md, ADR-008, viva/break-it/rewrite tasks below) — done when: files reviewed and approved by Arnav
- [x] S.3 [B] Git init, commit "S: repo scaffold", private GitHub repo pushed — done when: `git log` shows the commit and the remote exists
- [x] S.4 [B] Plan fixes (reward order, observation, conversation source, learning gates, ADR-009) — done when: files reviewed and approved by Arnav
- [x] S.5 [B] Plan fixes round 2 (delayed-reward credit ADR-010, ρ definition ADR-011, M1.12 split, break-it and gate wording) — done when: files reviewed and approved by Arnav
- [x] S.6 [B] Plan fixes round 3 (ADR-012 heuristic local vs global, first prototype milestone, M3.4 reference) — done when: files reviewed and approved by Arnav
- [x] S.7 [B] Plan fixes round 4 (ADR-013 decision protocol, ADR-010 delayed credit, ADR-011 λ_sat criterion, ADR-012 heuristic interfaces, RULES.md #14) — done when: files reviewed and approved by Arnav
- [x] S.8 [B] Plan fixes round 5 (ADR-014 reward terms, ADR-010 drop attribution, ADR-011 λ_sat criterion, ADR-012 and ADR-013 amendments, approval ordering, deadline, guide errata) — done when: files reviewed and approved by Arnav

## Phase M0 — Data
- [x] M0.1 [B] Download Azure LLM Inference 2023 and BurstGPT into data/raw (read-only) — done when: files present, row counts printed
- [ ] M0.2 [B] data/traces.py loaders — done when: tests/test_traces.py passes
- [ ] M0.3 [A] Notebook 01_trace_eda (Arnav writes the analysis cells; skeleton with questions provided): arrival rates, P/O distributions, burstiness; also the fraction of BurstGPT rows with a Session ID, whether Request tokens grow within a session (is history included?), the session length distribution, and confirm Azure 2023 has only TIMESTAMP, ContextTokens, GeneratedTokens — done when: notebook runs top to bottom and findings are recorded in ADR-009, written by Arnav in his own words
- [ ] M0.3a [B] Viva check for M0.3 (trace EDA) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
- [ ] M0.3.1 [B] Tests for normalisation and split in tests/test_processed.py: constants are the 99th percentile per feature, values clipped to [0,1]; train/held-out split is time-ordered, has no overlap, and reports both sizes — done when: tests written and failing as expected
- [ ] M0.4 [A] data/processed.py: normalisation constants to data/processed/normalisation.json, time-ordered train/held-out split — done when: the M0.3.1 tests pass
- [ ] M0.4a [B] Viva check for M0.4 (normalisation and split) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
- [ ] M0.6 [B] Seeded stream sampler taking an arrival rate in req/s (not ρ; ρ is converted in M1.28) — done when: same seed gives identical stream (test passes)
- [ ] M0.6a [B] Viva check for M0.6 (arrival-rate rescaling) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md

## Phase M0.5 — Profiling (timebox 6h)
- [ ] M0.5.0 [B] Learning gate L1 (before profiling): Deep-Dive Guide videos 1–5, Parts A–B — done when: Arnav answers the relevant self-check questions from the Deep-Dive Guide into docs/viva.md
- [ ] M0.5.1 [B] Install llama.cpp, fetch Qwen2.5-3B Q4_K_M and a slow-class model — done when: llama-server answers a request
- [ ] M0.5.2 [B] profiling/bench_server.py: TTFT, TPOT at varying prompt length and batch size, prefix-cache reuse — done when: raw CSV written for both classes; also measure decode and prefill slowdown with 0..N−1 other servers busy (ADR-015)
- [ ] M0.5.3 [B] Tests for the fitting maths on synthetic data (known a, t0, k recovered) — done when: tests/test_fit_calibration.py passes
- [ ] M0.5.4 [A] profiling/fit_calibration.py: fit a, t0, k, cache speedup, interference — done when: tests/test_fit_calibration.py passes
- [ ] M0.5.4a [B] Viva check for M0.5.4 (fit_calibration) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
- [ ] M0.5.4.1 [B] ADR-015 (interference model: options A/B/C) accepted from the M0.5.2 slowdown data, before M1.7 — done when: ADR-015 status accepted
- [ ] M0.5.5 [B] Write calibration.json, plot fit vs measured in notebook 02 — done when: fit residuals plotted and reviewed
- [ ] M0.5.6 [B] ADR: server class split, class prices, KV budgets; the class prices are labelled "synthetic price per busy second (rough real GPU price ratios)" wherever they appear — done when: ADR approved

## Phase M1 — Simulator + heuristics
- [ ] M1.1 [B] config.py + utils (seeding, logging, io) with tests — done when: tests/test_config.py and tests/test_utils.py pass
- [ ] M1.2 [B] sim/request.py + fill dt, episode_ticks, targets and max_defers (D) in configs via ADR — done when: tests/test_request.py passes
- [ ] M1.3 [B] tests/test_kv_cache.py (admit, release, full, fullness) — done when: tests written and failing as expected
- [ ] M1.4 [A] sim/kv_cache.py — done when: tests/test_kv_cache.py passes
- [ ] M1.4a [B] Viva check for M1.4 (kv_cache) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
- [ ] M1.5 [B] tests/test_prefix_cache.py (hit, miss, eviction, speedup) — done when: tests written
- [ ] M1.6 [A] sim/prefix_cache.py — done when: tests/test_prefix_cache.py passes
- [ ] M1.6a [B] Viva check for M1.6 (prefix_cache) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
- [ ] M1.7 [B] tests/test_server.py (service time formula, batching, queue order) — done when: tests written
- [ ] M1.8 [A] sim/server.py service time + batching — done when: tests/test_server.py passes
- [ ] M1.8a [B] Viva check for M1.8 (server service time + batching) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
- [x] M1.8.1 [B] ADR-012 (heuristic baselines, local vs global; M1.11 builds its direct-assignment mode) and ADR-013 (decision protocol, entry rule, Forward target) approved — done when: ADR-012 and ADR-013 status accepted
- [ ] M1.9 [B] tests/test_cluster.py (reset/step shapes, masks, hops/defers limits, drop attribution: assert which agents receive the drop and which server it counts against, not reward values) + PettingZoo API-shape test; tests follow ADR-013 (one oldest request per agent per tick, a deferred request goes to the back of the queue, uniform random entry agent (seeded), idle agent gets zero observation and all-False mask) and ADR-010 (a drop is credited only to agents that acted on the request; a drop with no acting agent is counted in the run log) — done when: tests written
- [ ] M1.10 [B] tests/test_conservation.py (no request lost or double-counted) — done when: test written and failing as expected
- [ ] M1.11 [A] sim/cluster.py (i): entry rule (uniform random entry agent, seeded, entry_rule in configs/sim.yaml), Accept/Forward/Defer routing, hop and defer limits, FIFO one-decision-per-tick with deferred requests to the back of the queue, environment-chosen SED-style Forward target (visible neighbour minimising expected wait + this request's estimated service time, ties to lowest index), and the direct-assignment mode for global policies (tests follow ADR-013 and ADR-012) — done when: the routing, limit, Forward-target and direct-assignment tests in tests/test_cluster.py pass
- [ ] M1.11a [B] Viva check for M1.11 (entry rule, routing, hop/defer limits) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
- [ ] M1.12 [A] sim/cluster.py (ii): tick loop, completions, time advance — done when: the tick and completion tests in tests/test_cluster.py pass
- [ ] M1.12a [B] Viva check for M1.12 (tick loop, completions, time advance) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
- [ ] M1.13 [A] sim/cluster.py (iii): action masks and drops (no legal action → drop, counted against the last holder in per-server metrics; reward credit per ADR-010) — done when: tests/test_cluster.py and tests/test_conservation.py pass (conservation: no request lost or double-counted; it must pass at the end of this task)
- [ ] M1.13a [B] Viva check for M1.13 (masks, drops, conservation) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
- [ ] M1.14 [B] tests/test_observation_builder.py (features 1–5 and 7, normalisation with data/processed/normalisation.json, clipping to [0,1], feature 6 = 0 when k=0, idle agent gives a zero observation per ADR-013) — done when: tests written
- [ ] M1.15 [A] Observation construction in sim/cluster.py — done when: tests/test_observation_builder.py passes
- [ ] M1.15a [B] Viva check for M1.15 (observation construction) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
- [x] M1.16 [B] ADR-010 and ADR-014 approved. ADR-010: delayed-reward credit; recommended option (b): s' = the agent's next decision observation, discount γ per decision; (a) SMDP at the resolution tick withdrawn; (c) proxy reward rejected; shared R_SLA credit to every agent that acted on a request, a drop is a shared −5 to acting agents only (no extra charge), Defer/Forward immediate costs, episode end as truncation (drain until empty, max drain horizon), fraction of discarded end-of-episode transitions logged, the Transition record. ADR-014: cost per request at resolution to the serving agent's Accept transition, KV term per request, −β·B_t at each transition's decision tick, cost invariant Σ_j C_j = Σ_i c_i × busy_seconds_i. The Δ measurement moved to M1.24 — done when: ADR-010 and ADR-014 status accepted (M1.17 tests need both)
- [ ] M1.17 [B] tests/test_reward.py for R_SLA (+10 met, −10 missed, −5 dropped, shared by acting agents only), the ADR-014 terms (per-request cost C_j = class price × attributed service seconds, prefill to j and each decode step split equally across the B_i requests in the step, scaled by λ and charged to the serving agent's Accept transition only; per-request KV term −w_kv × fraction of resident ticks with KV > 80%, credited at resolution; the cost invariant Σ_j C_j = Σ_i c_i × busy_seconds_i on a hand-computed episode), and, per the approved ADR-010, the Transition record (obs, mask, action, decision tick, reward, next obs, next mask, truncated), s' = the next decision observation, γ per decision, shared R_SLA credit, and truncation at episode end — done when: tests written
- [ ] M1.18 [A] R_SLA, per-request cost term and per-request KV term in sim/cluster.py (per-request attributed service seconds and resident-tick counters), credited at resolution (ADR-004) with the Transition record, s' and per-decision discount as set by the approved ADR-010 and ADR-014 — done when: tests/test_reward.py passes (including the cost invariant)
- [ ] M1.18a [B] Viva check for M1.18 (R_SLA, cost term, delayed credit) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
- [ ] M1.19 [B] tests/test_metrics.py (goodput, percentiles, Jain's index on hand-computed cases) — done when: tests written
- [ ] M1.20 [A] sim/metrics.py — done when: tests/test_metrics.py passes
- [ ] M1.20a [B] Viva check for M1.20 (metrics) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
- [ ] M1.21 [B] ADR-012 amendment (approval is in M1.8.1): write the local rules for JSQ, Po2 and Cache-aware (7 observation features only, e.g. Cache-aware-local uses the prefix-hit feature) and the masked-action fallback (what each rule does when its preferred action is masked). SED-local is named as an approximation of SED (neighbour mean only) — done when: ADR-012 amendment written with What/Why and approved by Arnav before M1.22
- [ ] M1.22 [B] tests/test_heuristics.py against the interfaces in architecture.md (LocalPolicy.act, GlobalPolicy.assign): each policy on hand-built states, in both local and global forms where applicable, including SED-local with k=0 always Accepting — done when: tests written
- [ ] M1.23 [A] policies/heuristics.py: Random, Round-robin, JSQ, Po2, local and global forms per ADR-012 — done when: tests for these pass
- [ ] M1.23a [B] Viva check for M1.23 (Random, Round-robin, JSQ, Po2; local vs global) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
- [ ] M1.24 [B] First end-to-end run (first working prototype): Random, Round-robin, JSQ, Po2 for one episode on train traffic at a fixed arrival rate in req/s (ρ is defined later in M1.28); print goodput, TTFT/TPOT p50/p95 and drop rate, and the typical magnitude of the per-request KV term against R_SLA (ADR-014, to inform the later w_kv ADR), and the typical Δ in ticks from decision to resolution (recorded as a measurement under ADR-010); paste the output into docs/logs.md — done when: numbers printed and logged. Celebrate: this is Milestone 2, the working prototype.
- [ ] M1.25 [A] policies/heuristics.py: SED, Cache-aware, local and global forms per ADR-012 — done when: tests/test_heuristics.py passes (viva: rewrite SED from memory)
- [ ] M1.25a [B] Viva check for M1.25 (SED, Cache-aware; local vs global) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
- [ ] M1.25b [A] Rewrite SED from memory: blank scratch file, no references, then diff against policies/heuristics.py — done when: diff reviewed and gaps noted in docs/viva.md
- [x] M1.25.1 [B] ADR-011 approved (criterion only; λ_sat value filled in M1.28) — done when: ADR-011 criterion approved by Arnav
- [ ] M1.26 [B] Saturation sweep script: finds λ_sat for the global-form SED cluster (ADR-011: smallest arrival rate where completion ratio over the arrival window < 0.95, OR drop rate > 1%, OR last-quarter in-system count > 1.5× second-quarter count; thresholds are assumptions), on train traffic with several seeds, with a monotonicity check, recorded per trace and per cache setting; also records the in-flight fraction at the end of the window, SLA attainment at 0.1 × λ_sat, and max arrivals per agent per tick at λ_sat (λ_sat·dt/N, must stay well below 1) — done when: script written and a run's output is in results/
- [ ] M1.27 [B] tests/test_load.py: sweep logic on synthetic sweeps, one per criterion (known λ_sat recovered under the completion-ratio, drop-rate and backlog-growth criteria separately), plus a non-monotone sweep that is flagged — done when: tests written and passing
- [ ] M1.28 [B] ρ helper in data/load.py: ρ = λ_arr / λ_sat, returning the arrival rate in req/s (data/load.py is Tier B in the architecture.md map) — done when: λ_sat recorded in ADR-011 "Definition of ρ" and in results/ (a measurement; no status change)
- [ ] M1.29 [B] eval/evaluate.py + scripts/evaluate.py baseline run on held-out traffic, all baselines in local and global forms where applicable (after M1.28, so ρ is defined) — done when: results/baselines/ written with config copied
- [ ] M1.30 [B] Sanity checks (M2 gate): (i) SED-local at k=full and SED-global each beat Random at ρ=0.8, plus a test or check that SED-local at k=0 behaves like Random (it always Accepts, so it is entry-rule routing, ADR-012); (ii) Little's law L ≈ λ_arr·W at ρ = 0.5 and 0.8; (iii) heuristic ordering matches the prediction written in docs/viva.md before the run, and any violation is explained rather than tuned away; (iv) headroom check: SED-global vs SED-local (k=full and k=0) vs Random at ρ = 0.8 and 0.95, 5 seeds, mean ± 95% CI — done when: numbers in results/ reviewed with Arnav, the gaps are recorded in docs/logs.md, and if SED-local and SED-global overlap in CI, an ADR is written before M2 deciding whether the headline shifts to the cost frontier (E3) or the workload changes (e.g. BurstGPT bursts)

## Phase M2 — Single-agent DDQN
- [ ] M2.0 [B] Learning gate L2 (before M2): Deep-Dive Guide videos 6–10, Parts C–D — done when: Arnav answers the relevant self-check questions from the Deep-Dive Guide into docs/viva.md
- [ ] M2.1 [B] tests/test_networks.py (shapes, masked argmax) — done when: tests written
- [ ] M2.2 [A] agents/networks.py — done when: tests/test_networks.py passes
- [ ] M2.2a [B] Viva check for M2.2 (networks) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
- [ ] M2.3 [B] tests/test_replay_buffer.py (capacity, overwrite, sample shapes) — done when: tests written
- [ ] M2.4 [A] agents/replay_buffer.py — done when: tests/test_replay_buffer.py passes
- [ ] M2.4a [B] Viva check for M2.4 (replay buffer) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
- [ ] M2.5 [B] tests/test_dqn_agent.py (DDQN target on a hand-computed batch, masked ε-greedy, target sync) — done when: tests written
- [ ] M2.6 [A] agents/dqn_agent.py act + epsilon — done when: act tests pass
- [ ] M2.6a [B] Viva check for M2.6 (act + epsilon) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
- [ ] M2.7 [A] agents/dqn_agent.py DDQN update + target network — done when: tests/test_dqn_agent.py passes (viva: rewrite update from memory)
- [ ] M2.7a [B] Viva check for M2.7 (DDQN update + target network) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
- [ ] M2.7b [A] Rewrite the DDQN update from memory: blank scratch file, no references, then diff against agents/dqn_agent.py — done when: diff reviewed and gaps noted in docs/viva.md
- [ ] M2.8 [B] tests/test_train_loop.py (pending transitions credited at resolution, ADR-004; assert the Transition record, s' = next decision observation, per-decision discount, shared R_SLA credit including the shared drop −5 to acting agents only, the ADR-014 per-request cost and KV terms on the serving agent's Accept transition, and truncation at episode end per the approved ADR-010) — done when: tests written
- [ ] M2.9 [A] train/loop.py single-agent episodes — done when: tests/test_train_loop.py passes
- [ ] M2.9a [B] Viva check for M2.9 (single-agent train loop) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
- [ ] M2.10 [B] scripts/train.py plus per-episode CSV logging (return, TD loss, mean Q, ε, action histogram) into results/<exp>/<timestamp>_seed<k>/ with config copied — done when: a short smoke run (values via a temporary override config, not committed to dqn.yaml) writes the CSV with all five columns
- [ ] M2.11 [B] ADR: fill lr, batch size, target update, warmup, ε decay in dqn.yaml. Protocol: tune on train traffic, one seed only; held-out untouched until M4; protocol recorded in the ADR — done when: ADR approved
- [ ] M2.12 [B] Train one DDQN agent replacing one SED-local agent in an otherwise all-SED-local cluster; plot return, TD loss, mean Q, ε, action histogram — done when: over 5 seeds, cluster goodput is within the all-SED-local 95% CI or better AND the action histogram shows more than one action in use (development gate on train traffic, not a reported result)

Break-its (M2). Rule for all: write the hypothesis in docs/viva.md (Break-it log) first; ablation switches are config flags, 3 seeds (diagnostic runs, not reported in docs/numbers.md), results under results/break_it/. Arnav types any change inside Tier A files; Claude may add the config entries and gives the commands to run; Arnav runs them (RULES.md #1).
- [ ] M2.13 [A+B] Break-it (a) no target network (online net bootstraps itself): hypothesis in docs/viva.md first — done when: TD loss, mean Q and return curves compared with M2.12 and explained
- [ ] M2.14 [A+B] Break-it (b) no replay buffer, train on consecutive transitions: hypothesis in docs/viva.md first — done when: curves compared with M2.12 and the correlation effect explained
- [ ] M2.15 [A+B] Break-it (c) γ ∈ {0, 0.9, 0.99}: hypothesis in docs/viva.md first — done when: three runs compared and the role of delayed outcomes (ADR-004) explained
- [ ] M2.16 [A+B] Break-it (d) no action masking: hypothesis in docs/viva.md first — done when: illegal-action rate, drops and return compared with M2.12 and explained

## Phase M3 — Multi-agent
- [ ] M3.0 [B] Learning gate L3 (before M3): Deep-Dive Guide videos 11–12, Part E — done when: Arnav answers the relevant self-check questions from the Deep-Dive Guide into docs/viva.md
- [ ] M3.1 [B] tests for independent training (N=4 agents, per-agent buffers and rewards) — done when: tests written
- [ ] M3.2 [A] train/loop.py independent DDQN N=4 — done when: tests pass
- [ ] M3.2a [B] Viva check for M3.2 (independent DDQN N=4) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
- [ ] M3.3 [B] tests for the cooperation term only (β, breach window W, cluster breach rate B_t), added to tests/test_reward.py — done when: tests written
- [ ] M3.4 [A] Cooperation term −β·B_t in cluster, applied to every transition with B_t sampled at its decision tick (ADR-014; R_SLA, cost and KV terms already built in M1.18) — done when: tests/test_reward.py passes (viva: rewrite reward from memory)
- [ ] M3.4a [B] Viva check for M3.4 (cooperation term) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
- [ ] M3.4b [A] Rewrite the full reward from memory (per ADR-014, the full transition reward: shared R_SLA − λ·C_j − KV term (serving agent) − β·B_t − immediate Defer/Forward costs): blank scratch file, no references, then diff against the real one in cluster — done when: diff reviewed and gaps noted in docs/viva.md
- [ ] M3.5 [B] ADR: β value and breach window W — done when: ADR approved
- [ ] M3.6 [B] tests for neighbour observation with k ∈ {0, 1, full} — done when: tests written
- [ ] M3.7 [A] Neighbour-wait observation in cluster — done when: tests pass
- [ ] M3.7a [B] Viva check for M3.7 (neighbour-wait observation) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
- [ ] M3.8 [B] ADR: joint-action design for the central DQN (one network with 3^N = 81 outputs vs factored), status Proposed — done when: ADR written and reviewed
- [ ] M3.9 [B] tests/test_central_dqn.py — done when: tests written
- [ ] M3.10 [A] agents/central_dqn.py — done when: tests/test_central_dqn.py passes
- [ ] M3.10a [B] Viva check for M3.10 (central DQN) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
- [ ] M3.11 [B] Smoke run: 5 seeds, N=4, no NaNs, conservation holds — done when: results/ written for all seeds
- [ ] M3.12 [B] Time one full training run and extrapolate total wall time for all experiments (run budget: E1 up to 15 if trained per ρ, E2 10, E3 25, E4 20, plus break-its 30 at 3 seeds; about 100 runs total if nothing is reused); set episode counts by ADR — done when: ADR approved with the wall-time estimate

Break-its (M3). Same rule: hypothesis in docs/viva.md (Break-it log) first; config flags only; 3 seeds (diagnostic runs, not reported in docs/numbers.md); results under results/break_it/. Claude may add the config entries and gives the commands to run; Arnav runs them (RULES.md #1).
- [ ] M3.13 [A+B] Break-it (e) β = 0, smoke scale (links to E2 in M4.7, which is the formal run): hypothesis in docs/viva.md first — done when: breach rate and goodput vs β > 0 compared and explained
- [ ] M3.14 [A+B] Break-it (f) replay buffer 500k vs 20k to expose non-stationarity: hypothesis in docs/viva.md first — done when: curves compared and stale-data effect explained
- [ ] M3.15 [A+B] Break-it (g) freeze one agent's learning mid-training and observe the others: hypothesis in docs/viva.md first — done when: the other agents' return and action histograms before/after the freeze compared and explained

## Phase M4 — Experiments E1–E6
- [ ] M4.1 [B] tests/test_stats.py (mean, 95% CI against known values) — done when: tests written
- [ ] M4.2 [A] eval/stats.py — done when: tests/test_stats.py passes (viva: rewrite CI calc from memory)
- [ ] M4.2a [B] Viva check for M4.2 (stats) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
- [ ] M4.2b [A] Rewrite the CI calculation from memory: blank scratch file, no references, then diff against eval/stats.py — done when: diff reviewed and gaps noted in docs/viva.md
- [ ] M4.3 [B] tests/test_pareto.py (dominated points, ties, single point) — done when: tests written
- [ ] M4.4 [A] eval/pareto.py — done when: tests/test_pareto.py passes
- [ ] M4.4a [B] Viva check for M4.4 (pareto) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
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
- [ ] M5.1a [B] Fill docs/numbers.md from results/ only, source path on every row — done when: no empty row has a results/ file available and no value lacks a path
- [ ] M5.2 [B] Report draft: method, experiments, answers to the 3 questions — done when: draft reviewed
- [ ] M5.3 [B] Limitations and threats (non-stationarity, sim fidelity, N=4, shared-chip contention: servers coupled on one M4 Pro, not a real cluster; decentralisation as a design choice, "what if routing is decentralised", with the central DQN as reference; synthetic prices) — done when: section reviewed
- [ ] M5.4 [B] Compile final viva bank from docs/viva.md — done when: bank covers every viva check and every Revisit item
- [ ] M5.4a [B] Strict mock viva (run in claude.ai); results into docs/viva.md Revisit list — done when: every wrong answer is listed in Revisit with its missing piece
- [ ] M5.4b [B] Run the codebase-wiki skill to generate docs/wiki/ — done when: docs/wiki/ exists and Arnav has skimmed it
- [ ] M5.5 [B] Final report to reports/final_report.md and slides if required — done when: submitted
- [ ] M5.6 [B] Gate check: M5 charts exist in results/ and reports/figures/ — done when: Arnav confirms (unlocks M6)

## Phase M6 — Real deploy (blocked until M5.6)
- [ ] M6.1 [B] Start N=4 llama-servers on the M4 Pro per configs/servers.yaml — done when: all health endpoints respond
- [ ] M6.2 [B] router/server_client.py with tests against a mock server — done when: tests/test_server_client.py passes
- [ ] M6.3 [B] tests/test_observation.py (live state equals sim observation for the same state) — done when: tests written
- [ ] M6.4 [A] router/observation.py — done when: tests/test_observation.py passes
- [ ] M6.4a [B] Viva check for M6.4 (observation) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
- [ ] M6.5 [B] tests/test_policy_router.py (masking, hops, defers) — done when: tests written
- [ ] M6.6 [A] router/policy_router.py — done when: tests/test_policy_router.py passes
- [ ] M6.6a [B] Viva check for M6.6 (policy_router) — done when: entry written by Claude Code and self-checked by Arnav in docs/viva.md
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
- [ ] M7.9a [B] README "Results" table generated from docs/numbers.md only — done when: every README number matches a row in docs/numbers.md with a results/ source path
- [ ] M7.10 [B] Make repo public after grading — done when: Arnav confirms

## Phase M8 — Kaggle 2×T4 + vLLM validation (stretch)
- [ ] M8.1 [B] Kaggle notebook launching vLLM on 2×T4 — done when: both servers respond
- [ ] M8.2 [B] Profile vLLM servers into a second calibration file — done when: calibration written
- [ ] M8.3 [B] Replay trace through the router on vLLM — done when: metrics logged
- [ ] M8.4 [B] Compare sim vs vLLM real — done when: gap table written
