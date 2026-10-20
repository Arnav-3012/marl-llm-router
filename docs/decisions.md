# Decisions (ADRs)

Required before any change to state, actions, reward, metrics or experiment design (RULES.md #7).

## Template

```
## ADR-NNN: <title>
Status: proposed | accepted | superseded by ADR-XXX
Date: YYYY-MM-DD
What: the decision in one sentence (RULES.md #14)
Why: the reason in one or two sentences (RULES.md #14)
Context: why a decision is needed
Decision: what we chose
Alternatives considered: what else, and why not
Consequences: what this makes easy, hard, or risky
```

## ADR-001: Discrete-time ticks
Status: accepted · Date: 2026-10-03
Context: The simulator needs a clock. Request arrivals, service completion and agent decisions must be ordered deterministically and reproducibly.
Decision: Advance time in fixed ticks of length dt (set in configs/sim.yaml). All agents act once per tick on the requests currently held.
Alternatives considered: Discrete-event simulation (exact timing, but harder to align with synchronous per-agent step() and PettingZoo shape); continuous-time asynchronous agents (realistic, much harder to train and debug).
Consequences: Simple, seedable and easy to test conservation. Timing resolution is limited by dt, so dt must be small relative to t_step. Fits ParallelEnv. "Act once per tick on the requests currently held" is refined by ADR-013: each agent decides on at most one request per tick (its oldest).

## ADR-002: Independent Double DQN with centralised reference
Status: accepted · Date: 2026-10-03
Context: Several routing agents, one per server, with local partial observations. We need a learning method that is simple enough to build from scratch and an upper bound to measure the cost of decentralisation.
Decision: Each agent is an independent Double DQN (MLP 7-64-64-3, Huber, Adam, target net, replay). A centralised DQN with joint observation is the reference upper bound. VDN is future work.
Alternatives considered: CTDE methods (QMIX/VDN, out of scope); policy gradients (more tuning, less natural for discrete masked actions); tabular methods (state too large).
Consequences: Non-stationarity from simultaneous learners is accepted and discussed in the report. The k ablation (E4) quantifies the gap to the centralised bound.

## ADR-003: Two server classes calibrated from real llama-server
Status: accepted · Date: 2026-10-03
Context: The simulator must be credible without inventing parameters, and the cluster must be heterogeneous for routing to matter.
Decision: Two classes, fast-expensive and slow-cheap, with a, t0, k, cache speedup and interference fitted from real llama-server benchmarks into profiling/calibration.json. The simulator reads server parameters only from that file.
Alternatives considered: Hand-picked parameters (violates RULES.md #8); one homogeneous class (removes the cost-latency tradeoff); more than two classes (extra calibration work, little extra insight).
Consequences: M0.5 gates M1. Sim-to-real gap (E7) is measurable. The class split of N=4 servers and the prices still need an ADR in M1.

## ADR-004: Outcome credited at resolution with decision-time state
Status: accepted · Date: 2026-10-03 (amended 2026-10-03, S.8: Consequences note only; status unchanged)
What: A request's outcome reward is credited at resolution to the transition made at the decision, using the decision-time state.
Why: The outcome (SLA met or missed, cost) is only known when the request finishes, many ticks after the action; crediting with the resolution-time state would break the link between state and action.
Context: A routing action's outcome (SLA met or missed, cost) is only known when the request finishes, many ticks later, possibly on another server.
Decision: Store the decision-time observation and action; when the request resolves, credit the outcome reward to the transition made at that decision, using the stored state. A dropped request is charged to the last holder.
Alternatives considered: Immediate proxy rewards (biased, hides true SLA); crediting with the state at resolution (breaks the Markov link between state and action).
Consequences: Transitions complete with delay, so the training loop must keep pending transitions per request. Conservation of requests becomes critical and is tested. Refined by ADR-010 (S.8): "charged to the last holder" is kept for metrics only (the drop counts against that server in per-server stats); for the reward, a drop is an R_SLA outcome of −5 credited once to every agent that has a transition on that request.

## ADR-005: PettingZoo-style env API
Status: accepted · Date: 2026-10-03
Context: Multi-agent code needs a standard interface that tests and future libraries can use.
Decision: The cluster env follows the PettingZoo ParallelEnv shape: reset and step return per-agent dicts. pettingzoo is a dev dependency used only for an API-shape test.
Alternatives considered: Gymnasium single-agent wrapper (hides per-agent structure); a custom API (no tooling, harder to explain).
Consequences: Agents are addressed by name. We do not depend on pettingzoo at runtime.

## ADR-006: Learning rules (tiers, faded worked examples, no commands, no commits)
Status: accepted · Date: 2026-10-03
Context: The repo exists for Arnav to learn by writing the core himself; shipping is second.
Decision: Tier A code is taught with faded worked examples and typed by Arnav; Tier B may be written by Claude Code. Claude never runs shell commands and never commits; it gives commands and commit messages. Tasks are ticked only after Arnav pastes passing tests (RULES.md).
Alternatives considered: Claude writes everything (fast, no learning); no AI help (slow, no scaffolding).
Consequences: Slower delivery, deeper understanding for the viva. Tier boundaries must be kept current in docs/architecture.md.
Amended 2026-10-20 (deadline 2026-10-27): superseded in part. Claude Code now writes Tier A and Tier B code, runs commands and tests, and commits and pushes each task once its tests pass; Arnav reviews summaries. The learning-first teaching mode applies again only if Arnav asks. See RULES.md #1–#5 and CLAUDE.md.

## ADR-007: Showcase without hosted LLMs (Docker profiles + Gradio sim demo on HF Spaces)
Status: accepted · Date: 2026-10-03
Context: The project should be demo-able at no cost. Hosting live LLMs publicly is out of scope and Docker on macOS cannot use Metal.
Decision: Docker image with compose profiles `cpu` (llama-server CPU containers) and `host` (native llama-servers via host.docker.internal). A Gradio Space on free CPU runs the simulator with trained weights and calibration.json. A 2-minute video shows the real router on the Mac.
Alternatives considered: Paid GPU hosting (budget is zero); hosted API LLMs (not our servers, no calibration story); video only (not interactive).
Consequences: The public demo is simulator-only and must say so. Real-server evidence is the video plus E7 results.

## ADR-008: Interview-readiness process
Status: accepted · Date: 2026-10-03 (amended 2026-10-03)
What: For every task, Claude Code writes a docs/viva.md entry with the prerequisite, a bet prompt, the questions and reference answers; Arnav self-checks. There is no Claude grading step.
Why: Arnav wants a complete Q&A reference for the end of the project and interviews. Answers are collapsed so he attempts each one before reading it.
Context: The CV project must be defensible in an interview and in the course viva. Passing tests does not show that Arnav can explain, break or justify what he built.
Decision: For every task, Claude Code writes a docs/viva.md entry at the start of the task: prerequisite, bet prompt, questions and reference answers. Tier B tasks get prerequisite + bet + 1 question (explain or justify); Tier A tasks get prerequisite + bet + 3 questions (explain, break-it, justify). Each reference answer sits inside `<details><summary>Answer</summary> ... </details>`, is 3–6 lines, and ends with its source (file, ADR or Deep-Dive Guide section). Arnav attempts each question, then marks it himself: got it / partly / missed; anything not "got it" goes to a Revisit list. Reference answers must be correct for the current ADRs and code and never invent numbers (only cite results/ files or sources). Headline numbers live in docs/numbers.md and come only from results/. Break-it experiments in M2 and M3 have hypotheses written in docs/viva.md BEFORE the run. Viva-critical pieces (reward, DDQN update, SED, CI calculation) are rewritten from memory in a blank file and diffed against the real one.
Alternatives considered: A single viva prep at the end (late, answers forgotten, no debugging stories); a wiki only (reading is passive, answers would not be in his own voice).
Consequences: About 15 minutes extra per task. Real debugging stories from the break-it experiments. Bets, attempts and hypotheses stay in his own voice. Hypotheses are pre-registered, so a wrong prediction is kept as evidence of learning rather than hidden.
Amended 2026-10-20: Claude Code writes viva entries; Arnav's self-check is optional.

## ADR-009: Conversation source for the prefix cache
Status: accepted, Option B (accepted 2026-10-20, M0.3 close) · Date: 2026-10-03 (amended 2026-10-20, M0.3 findings and decision)
What: The conversation id for the prefix cache comes from synthetic sessions layered over Azure conv traffic (Option B), with session parameters taken from BurstGPT_3 and stored in configs/.
Why: Azure has no conversation id, and BurstGPT Session IDs cover only 4.37% of BurstGPT_3 rows and a different trace, so real session IDs cannot drive the main experiments; synthetic sessions keep the Azure arrival and length distributions while the session structure is an explicit, stated assumption.
Context: The prefix cache (sim/prefix_cache.py, cache-aware baseline, prefix-hit feature) needs a conversation id per request so that follow-up turns can reuse a server's cached prefix. Azure LLM Inference 2023 is believed to have only TIMESTAMP, ContextTokens and GeneratedTokens, so it carries no conversation id. BurstGPT has a Session ID, but only for conversation-mode rows, and it is not yet known whether Request tokens grow within a session (history included) or how long sessions are.
Findings (M0.3, drafted by Claude on 2026-10-20 at Arnav's instruction from his notebook output; Arnav to review):
- Azure conv and code raw files have only TIMESTAMP, ContextTokens and GeneratedTokens: no conversation id.
- BurstGPT_1 has no Session ID column. BurstGPT_3: 233,617 of 5,344,021 rows (4.37%) have a Session ID, and they are exactly the "Conversation log" rows (233,617 of 233,617; "API log" rows 0 of 5,110,404).
- 55,920 sessions; 35.5% have a single turn; turns per session p50/p90/p99/max = 2/9/31/436. Gap between consecutive turns p50/p90/p99 = 131 s / 2,340 s / 78,788 s. Session duration p50/p90/p99 = 121 s / 11,812 s / 312,894 s.
- History inclusion: of 177,697 turns that have a previous turn, the prompt grew in 77.8% and prompt ≥ previous prompt + previous output in 58.7%. diff = prompt − (previous prompt + previous output) has p10/p50/p90 = −457 / 15 / 119 tokens. So in the typical turn the prompt is the earlier conversation plus about 15 new tokens (history is re-sent), but about 41% of turns fall short, so history inclusion is common, not universal.
- Source: results/eda/trace_summary.json (sessions block) and the printed output of notebooks/01_trace_eda.ipynb cells (e), (f), (g), (h).
Decision: Option B, accepted 2026-10-20 (Arnav, M0.3 close). Synthetic sessions are generated over the Azure conv 2023 traffic (ADR-016). Every session parameter lives in configs/ (configs/sessions.yaml) and is set from the BurstGPT_3 statistics above:
- single-turn share 35.5% of sessions;
- turns-per-session distribution (p50/p90/p99/max = 2/9/31/436);
- inter-turn gap distribution (p50/p90/p99 = 131 s / 2,340 s / 78,788 s; median 131 s);
- probability that a turn re-sends the history (prompt ≥ previous prompt + previous output) = 0.587.
Assumption: inter-turn gaps are user think time. They are kept in simulated seconds and are NOT compressed when arrival rates are rescaled to reach ρ (ADR-011). The session generator itself is a later task; M0.4 does not touch sessions.
Limitation: the session structure is borrowed from a different trace (BurstGPT_3) and combined with Azure arrivals and lengths, so it is an assumption, not an observation of Azure users. The report states this wherever cache results appear.
Alternatives considered: (A) BurstGPT Session IDs for the cache experiments: real session structure, but only a subset of rows, and a different trace from the Azure traffic used elsewhere; rejected for the main experiments, usable later as a cache check on the 233,617 conversation rows. (B) synthetic sessions layered on Azure traffic: same arrival and length distributions as the main experiments, but session structure is invented and must be stated as an assumption (parameters in configs/, not in code); chosen.
Consequences: Cache experiments (E1 Cache-aware, cache hit rate) are claimed only under the synthetic-session assumption, never as validated on real conversation structure. Because gaps are not compressed, at the arrival rates needed for ρ ≈ 0.8–0.95 a session's turns are far apart relative to an episode, so the share of requests that are follow-ups within an episode must be measured when the generator is built (a possible threat to cache hit rate). The report states the source of the conversation id.

## ADR-010: Delayed-reward credit (s', discount)
Status: accepted (accepted 2026-10-03, S.8 review) · Date: 2026-10-03 (amended 2026-10-03, S.7; amended 2026-10-03, S.8)
What: Option (b): s' is the agent's next decision observation and the discount is γ per decision (not per tick); the delayed outcome is the reward of the decision that produced it; a drop is an R_SLA of −5 shared by every agent that acted on the request; cost and KV terms follow ADR-014.
Why: Option (a) (s' at the resolution tick, γ^Δ) is withdrawn because at resolution the agent may be idle or looking at a different request, and an agent's per-request transitions overlap during Δ, so a resolution-tick state is not the successor of that decision.
Context: ADR-004 credits an outcome to the decision-time state and action, but the outcome resolves Δ ticks later, possibly on another server. The DDQN target needs a defined next state s' and discount for such a transition, and the choice changes what the agent learns. Under ADR-013 an agent decides on at most one request per tick, so its decisions form a sequence of observations even when outcomes resolve out of order.
Decision: Option (b), accepted 2026-10-03, S.8 review.
- s' and discount: s' = the observation (and mask) the agent receives at its next decision after the one that produced the transition; the DDQN target uses γ once per decision, regardless of how many ticks passed. The reward is the outcome of that decision's request, known only at resolution, so a transition is pushed to the replay buffer when both its reward (resolution) and its s' (next decision) exist.
- Credit for a forwarded request: every agent that acted on the request (Accept, Forward or Defer) receives the shared R_SLA at resolution; only the serving agent pays the cost term and the KV term, both defined per request in ADR-014 (not here, and not per step).
- Drop attribution (S.8): a drop is an R_SLA outcome of −5, credited once to every agent that has a transition on that request. There is no extra charge. "Last holder" is kept only for metrics: the drop counts against that server in per-server stats. If no agent ever acted on the dropped request, no transition receives it; these are counted in the run log.
- Defer and Forward transitions: they carry their immediate per-action costs (values set in configs/ by a later ADR, not here) and receive the same shared R_SLA at resolution, with s' by the same rule.
- Episode end: arrivals stop at episode_ticks, then the cluster drains until empty, with a maximum drain horizon (set in configs/). The end is truncation, not termination: the target bootstraps. Requests still unresolved at the drain horizon are counted as dropped (assumption) so conservation holds. An agent's last transition(s) with no later decision have no s' and are discarded and counted in the run log. The fraction of transitions discarded at episode end is logged per run and reported; these skew toward slow requests, so the report flags it if the fraction is non-negligible.
- Transition record: (obs[7], mask[3], action, decision tick, reward, next obs[7], next mask[3], truncated flag). The decision tick is kept to compute Δ for logging and credit diagnostics, not for the discount.
- Δ: the typical Δ in ticks (decision to resolution) is measured in M1 and reported here. It no longer decides whether the outcome is visible through the discount; it affects credit-assignment noise (how many other decisions happen between action and outcome).
Alternatives considered: (a) SMDP, s' = the agent's observation at the resolution tick, γ^Δ: withdrawn for the reason in Why; (c) expected-outcome proxy reward at decision time: no delay, but biased and hides the true SLA outcome (the reason ADR-004 rejected proxy rewards).
Consequences: Pending transitions are held per request until resolution and per agent until the next decision, so the training loop keeps both. tests/test_reward.py and tests/test_train_loop.py assert s', next mask, the per-decision discount, shared R_SLA credit (including the shared −5 for drops) and the cost and KV terms charged to the serving agent only (ADR-014). Replay samples are noisier when Δ spans many decisions; Δ is reported so this is visible. The M1.18 and M2.9 implementations follow this ADR once approved.

## ADR-011: Definition of ρ
Status: accepted (criterion; accepted 2026-10-03, S.8 review) · Date: 2026-10-03 (amended 2026-10-03, S.7; amended 2026-10-03, S.8)
What: ρ = λ_arr / λ_sat, with λ_sat defined operationally as the smallest arrival rate at which the global-form SED cluster fails a completion-ratio, drop-rate or backlog-growth criterion over the arrival window.
Why: An unbounded-wait definition of saturation cannot be measured in a finite episode; thresholds on completion ratio, drop rate and backlog growth can, and they do not depend on the TTFT/TPOT targets, so capacity is not mixed up with SLA tuning.
Context: Every experiment is specified at load ρ ∈ {0.5, 0.8, 0.95}, but ρ has no operational meaning until the capacity it is measured against is fixed. A formula from per-server service rates ignores batching, KV limits, cache hits and routing losses.
Decision: ρ = λ_arr / λ_sat. λ_sat = the smallest arrival rate (req/s) at which, for the GLOBAL-form SED cluster (direct-assignment mode, ADR-012) over the arrival window, ANY of:
- completion ratio < 0.95, where completion ratio = requests completed during the arrival window ÷ requests arrived during it;
- drop rate > 1%;
- backlog growth: the in-system request count averaged over the last quarter of the arrival window exceeds 1.5× its average over the second quarter.
The thresholds 0.95, 1% and 1.5× are assumptions, stated as such in the report. None of the criteria uses SLA attainment, so λ_sat does not depend on the TTFT/TPOT targets.
- The episode must be long relative to typical service time; the in-flight fraction at the end of the window is recorded.
- SLA attainment is also recorded at a low-load reference (0.1 × λ_sat), to show the TTFT/TPOT targets are achievable at all. If attainment there is far below 1, the targets are revisited by ADR, not λ_sat.
- λ_sat is found by a sweep on train traffic with several seeds, plus a check that the sweep is monotone (completion ratio non-increasing, drop rate and backlog ratio non-decreasing in λ, within seed noise; if not monotone, refine the grid and report it). λ_sat is recorded per trace and per cache setting (cache on/off), in this ADR and in results/. λ_sat value: TBD, measured in M1.26–M1.28 and recorded later under this ADR as a measurement, not a new decision. The helper lives in data/load.py (Tier B).
Alternatives considered: ρ from nominal service rates in calibration.json (no sweep needed, but ignores batching, KV limits and cache effects, so ρ=0.95 may not mean near-saturation); saturation of the best heuristic over all policies (a fairer capacity, but more runs and the best policy changes with the configuration).
Consequences: ρ is defined relative to global-form SED, so a policy better than SED can run at ρ near or above 1 without saturating; the report says so. The 0.95 and 1% thresholds are assumptions, so ρ values shift if they change. The baseline evaluation (M1.29) comes after λ_sat is known. If server classes, calibration.json, trace or cache setting change, λ_sat must be re-measured. Report the maximum arrivals per agent per tick at λ_sat (λ_sat·dt/N with uniform entry, ADR-013). Because ADR-013 allows one decision per agent per tick, this must stay well below 1; otherwise the agent decision rate, not the servers, becomes the bottleneck, and global SED (which bypasses agents) would not reveal it.

## ADR-012: Heuristic baselines, local vs global
Status: accepted (accepted 2026-10-03, S.8 review) · Date: 2026-10-03 (amended 2026-10-03, S.7; amended 2026-10-03, S.8)
What: SED, JSQ, Po2 and Cache-aware each exist in a local form (only the 7 observation features, actions in {Accept, Forward, Defer}) and a global form (full cluster state, direct assignment); SED-local is an approximation of SED, not SED.
Why: Classical heuristics assume full state; a fair test of learning needs a baseline with the same information as the agents, and the global form stays as the information-advantaged reference. SED-local compares own expected wait with the neighbour MEAN wait and has no per-neighbour service estimate, so calling it plain SED would overstate it.
Context: The agents act in {Accept, Forward, Defer} on a local observation (own state plus neighbours within radius k). SED, JSQ, Po2 and Cache-aware are classically defined as direct assignment with full cluster state. Neither architecture.md nor ADR-005 says how they map onto the agent action space, and comparing agents against a baseline with more information is not a fair test of learning.
Decision: SED, JSQ, Po2 and Cache-aware each exist in two forms. Local: a LocalPolicy.act(obs[7], mask[3]) -> action in {Accept, Forward, Defer} that may use ONLY the 7 observation features, so only the neighbour MEAN wait, never per-neighbour values. Example, SED-local: Accept iff own expected wait ≤ neighbour mean wait, otherwise Forward; the environment picks the Forward target (ADR-013); with k=0 it always Accepts, which is equivalent to entry-rule routing (uniform random entry, ADR-013). SED-local is an approximation of SED, not SED: it has no per-neighbour service estimate. The report names it as such ("SED-local"); the name is not changed. Global: a GlobalPolicy.assign(cluster_state, request) -> server index, full cluster state, no Forward/Defer. The cluster exposes a direct-assignment mode for global policies, covered by the M1.11 tests. Random and Round-robin need no state. Local forms are the fair peers of the DQN agents and are used in M2.12, E1 and E4; global forms are information-advantaged references and define λ_sat (ADR-011).
Alternatives considered: Global only (the strongest classical baseline, but agents never see that information, so a gap would mix learning quality with information); local only (fair, but loses the reference for how much the information restriction costs).
Consequences: Tests (M1.22) and baseline runs (M1.29) cover both forms and run against the two interfaces in architecture.md. The exact local rules for JSQ, Po2 and Cache-aware (still limited to the 7 features, e.g. Cache-aware-local uses the prefix-hit feature) and the fallback when the preferred action is masked are fixed by an amendment of this ADR written in M1.21 and approved before the M1.22 tests are written. SED-local at k=0 behaves like entry-rule routing, which gives M1.30 a sanity check; it behaves like Random only because the entry rule is uniform random (ADR-013). With only the neighbour mean, local rules cannot pick the best neighbour, which is why the Forward target is chosen by the environment.

## ADR-013: Decision protocol and Forward target
Status: accepted (accepted 2026-10-03, S.8 review) · Date: 2026-10-03 (amended 2026-10-03, S.8)
What: Each agent decides on at most one request per tick (its oldest, FIFO, with deferred requests moved to the back); requests enter at a uniformly random entry agent; the environment picks the Forward target (visible neighbour minimising expected wait + this request's estimated service time); idle agents get a zero observation and an all-False mask.
Why: Without a fixed protocol the number of decisions per agent per tick, and what a transition's s' means, are undefined; having the environment pick the target keeps the action space at 3 and consistent with the 7-feature observation (which has only the neighbour mean). A deferred request at the back of the queue stops the oldest request being re-decided every tick and blocking the others.
Context: ADR-001 says agents act once per tick on the requests currently held, which is ambiguous when an agent holds several requests, and the action Forward has no stated target although the observation only carries a neighbour mean wait. ADR-010 needs one well-defined decision sequence per agent.
Decision: 
- One decision per agent per tick: the oldest request it holds (FIFO). Other held requests wait; their waiting time counts toward TTFT but is not a Defer and carries no cost.
- Queue discipline (S.8): a deferred request moves to the back of the agent's held queue, so the oldest request is never re-decided every tick and does not block others.
- Entry rule (S.8): each arriving request lands at an entry agent chosen uniformly at random (seeded). The rule is a config field in configs/sim.yaml (entry_rule: uniform). "SED-local at k=0 behaves like Random" (ADR-012, M1.30) relies on this.
- An agent with no request that tick receives a zero observation and an all-False mask; no action is taken and no transition is recorded.
- Forward target is chosen by the environment (S.8, SED-style): the visible neighbour (within radius k) minimising expected wait + this request's estimated service time on that neighbour, ties broken by lowest index. The environment has this information; the agent still only decides whether to forward.
- Masks: with k=0 Forward is masked; Forward is masked at the hop limit; Defer is masked at the defer limit. If no action is legal the request is dropped; the drop counts against the last holder in per-server metrics and is credited to agents per ADR-010.
Alternatives considered: Agent chooses the target (action space grows with N and k, and the observation has no per-neighbour values to choose from); all held requests decided every tick (variable number of decisions per tick, variable-size inputs, harder to define s'); random Forward target (adds noise unrelated to the learned decision).
Consequences: One transition per agent per tick at most, so s' per ADR-010 is well defined. A backlog of held requests can build up and shows as TTFT, not as a penalty on the agent; the report notes it. The environment's target rule uses true neighbour expected waits and service estimates that the agent only sees as a mean wait. Tests (M1.9, M1.11, M1.14) follow this ADR. Amends the Consequences of ADR-001. Report the maximum arrivals per agent per tick at λ_sat (ADR-011): it must stay well below 1 or the one-decision-per-tick rule makes the agents the bottleneck.

## ADR-014: Reward terms under per-decision transitions
Status: accepted (accepted 2026-10-03, S.8 review) · Date: 2026-10-03 (S.8)
What: Cost and KV penalty are per-request terms charged at resolution to the serving agent's Accept transition only; the cooperation term −β·B_t is charged to every transition at its decision tick.
Why: ADR-010 makes transitions per decision, so per-step terms (λ·C, −β·B_t, "−1 per step KV > 80%") have no transition to attach to; making them per-request keeps credit tied to the agent that actually caused them and keeps the cost metric consistent with the reward.
Context: context.md defined r = R_SLA − λ·C − β·B_t with the KV penalty and C accrued per step. Under ADR-010 (and ADR-013) a transition exists only at a decision, and an agent has no transition on ticks where it is idle or merely holds requests.
Decision: Option A, accepted 2026-10-03, S.8 review.
- Cost (per request): C_j is charged at resolution to the serving agent's Accept transition only. C_j = c_class(serving server) × service seconds attributed to j, where prefill seconds a·(P − P_cached) go fully to j and each decode step's t_step(B_i) is split equally across the B_i requests in that step. Invariant, tested in M1.17: Σ_j C_j = Σ_i c_i × busy_seconds_i over an episode (j over all requests with attributed service, including those dropped at the drain horizon, assumption; i over servers).
- KV term (per request): −w_kv × (fraction of j's resident ticks on the serving server with KV fullness > 80%), credited to the serving agent at resolution. w_kv lives in configs/, its value is set by a later ADR. This replaces the "−1 per step KV > 80%" wording in context.md and phase-plans.md. Whether its magnitude is sensible against R_SLA (±10) is checked in the M1.24 run.
- Cooperation term (built in M3.4): every transition receives −β·B_t, with B_t sampled once at that transition's decision tick (β and window W set by the M3.5 ADR).
- Transition reward therefore = shared R_SLA at resolution (ADR-010) − λ·C_j − KV term (serving agent only) − β·B_t (every transition) − the immediate Defer/Forward costs from ADR-010.
Alternatives considered: (B) accrue per-step terms into each agent's currently open transition: keeps the per-step definitions, but credits cost to whatever the agent last did (e.g. a Forward), so credit is noisy; (C) keep per-step rewards with dummy idle-tick transitions: breaks ADR-013's rule that an idle agent records no transition.
Consequences: The cost-per-request metric stays consistent with the reward through the invariant above. The server must track per-request attributed service seconds and per-request resident ticks above the KV threshold (sim.server / sim.cluster, Tier A). A request that is never served has C_j = 0. tests/test_reward.py covers the invariant and the per-request terms (M1.17). ADR-010 Decision text points here for the cost and KV terms.

## ADR-015: Interference model in the simulator
Status: proposed · Date: 2026-10-03
What: Whether, and how, the simulator slows a server down when other servers are busy at the same time is not yet decided; the choice is made in M0.5.4.1 from the profiling data, among options A, B and C below.
Why: ADR-003 and M0.5.4 fit an interference parameter, but the service-time model in context.md (T = a·(P − P_cached) + Σ t_step(B_i), t_step(B) = t0 + k·B) has no interference term, so M1.8 would have nothing to apply it to. The real servers share one M4 Pro chip, so the effect may be real, and it must be modelled or reported rather than silently dropped.
Context: Without an interference term, the fitted parameter has no home in the service-time formula (context.md Environment). The decision depends on how large the measured slowdown is and how it scales with the number of busy servers, which is only known after M0.5.2.
Decision: Not yet taken. Fixed in M0.5.4.1 from the M0.5.2 profiling data. Candidates:
- (A) t_step and a are multiplied by (1 + s_class × n_other_busy/(N−1)), with s_class fitted per server class. n_other_busy is the number of other servers with at least one request in service that tick.
- (B) A fixed multiplier on t_step and a whenever any other server is busy.
- (C) No interference term in the simulator; the measured slowdown is reported as a sim-to-real limitation (M5.3).
Alternatives considered: the three options above are the alternatives; none is rejected yet.
Consequences: M0.5.2 must measure decode and prefill slowdown with 0..N−1 other servers busy, so A can be fitted (a single "any other busy" point would only support B). M0.5.4 fits whatever the accepted option needs. The M1.7 tests and the M1.8 service-time code follow the accepted option, and configs/sim.yaml and calibration.json carry its parameters (no magic numbers). If C is chosen, E7 (sim-to-real gap) is expected to show the slowdown and M5.3 says so.

## ADR-016: Trace driving training and held-out evaluation
Status: accepted, Option A (accepted 2026-10-20, M0.3 close) · Date: 2026-10-03 (decision 2026-10-20)
What: Azure conv 2023 supplies both training and held-out traffic (80/20 by time, time-ordered: 16,495 train and 2,871 held-out requests, about 85/15 by count because the arrival rate is not uniform; held-out 11.7 min), and the burst test (E5) uses Azure code 2023 instead of BurstGPT_1.
Why: The sampler sets the arrival rate in req/s, so the trace's one-hour span limits distribution coverage, not the number of episodes; and BurstGPT is near-Poisson inside one-hour slices (median dispersion 1.06), so its whole-trace burstiness is rate drift, while Azure code stays dispersed inside slices (67.6 vs 72.6 whole-trace), which makes it the better burst test.
Context: M0.1 MANIFEST.json facts; M0.3 EDA findings (arrival rates, burstiness c_a, P/O distributions) to be recorded here by Arnav.
Findings (M0.3, drafted by Claude on 2026-10-20 at Arnav's instruction from his notebook output; Arnav to review):
- Duration: Azure conv 0.97 h, Azure code 0.95 h, BurstGPT_1 61.0 days, BurstGPT_3 110.0 days. Mean rate: 5.53, 2.567, 0.271, 0.562 req/s.
- 80/20 time split (by duration; the request counts are not 80/20 because the arrival rate varies, e.g. azure_conv is about 85/15), train / held-out requests: azure_conv 16,495 / 2,871 (held-out 11.7 min); azure_code 8,068 / 751 (11.5 min); burstgpt_1 1,120,335 / 309,402 (12.2 days); burstgpt_3 4,249,532 / 1,094,489 (22.0 days). Mean rate train vs held-out: azure_conv 5.89 vs 4.10, azure_code 2.94 vs 1.09, burstgpt_1 0.266 vs 0.294, burstgpt_3 0.559 vs 0.576 req/s. The BurstGPT held-out part is below the mid-trace peak but not below the mean of its training part.
- Burstiness: c_a over the whole trace = 1.09 / 13.15 / 13.28 / 17.75. IDC at 1 s = 1.39 / 13.19 / 3.84 / 8.28; at 60 s = 16.1 / 164 / 138 / 230; at 1 h (BurstGPT) = 5,321 / 10,606. Inside slices (10 s counts, 10 min slices for Azure, 1 h for BurstGPT) the median IDC is 2.12 (conv, whole 3.41), 67.6 (code, whole 72.6), 1.06 (BurstGPT_1, whole 24.76) and 1.06 (BurstGPT_3, whole 44.35). Reading: BurstGPT is close to Poisson locally and its burstiness is non-stationarity (hourly slice rates p10–p90: 0.002–0.767 and 0.004–1.583 req/s); azure_code is bursty inside the hour; azure_conv is in between. Timestamps: Azure has microsecond resolution; BurstGPT 1 s (45.6% and 68.3% of gaps are ties); BurstGPT has gaps of 4.2 h and 5.2 h in low-traffic hours.
- Tokens, p50 / p99: prompt 1020/4142 (conv), 1469/7436 (code), 251/3387 (BurstGPT_1), 327/3354 (BurstGPT_3); output 129/601, 13/251, 34/1491, 14/876. Azure prompts look capped (code: p95 7,303, p99 7,436, max 7,437). Spearman P–O: 0.073, −0.021, 0.429, 0.213 (0.012 without failure rows).
- Source: results/eda/trace_summary.json and the printed output of notebooks/01_trace_eda.ipynb.
Decision: Option A, accepted 2026-10-20 (Arnav, M0.3 close).
- Training and held-out traffic: Azure conv 2023, time-ordered 80/20-by-time split (16,495 train and 2,871 held-out requests, about 85/15 by count because the arrival rate is not uniform; held-out 11.7 min). The window limits distribution coverage (the P/O and burst patterns seen in one hour), not the number of episodes, because streams are sampled at a set arrival rate in req/s with seeds (M0.6).
- Burst test (E5): Azure code 2023 replaces BurstGPT_1. Evidence: BurstGPT is near-Poisson within one-hour slices (median IDC of 10 s counts 1.06 for BurstGPT_1 and BurstGPT_3), so its whole-trace burstiness (c_a 13.28 and 17.75, IDC 24.76 and 44.35) is rate drift between hours; Azure code stays dispersed inside slices (median 67.6 against 72.6 over the whole trace). BurstGPT's 1 s clock (45.6% and 68.3% of gaps are ties) and its multi-hour gaps would also need special handling. BurstGPT remains in use only as the source of the session parameters (ADR-009).
Limitations (stated in the report): the held-out part is small (2,871 requests, 11.7 min) and comes from one hour on one day (2023-11-16), so held-out results describe that traffic mix; train and held-out mean rates differ (5.89 vs 4.10 req/s), which is irrelevant once the sampler rescales the rate but shows the held-out hour is not a replica of the training hour.
Open points: how a stream longer than the 11.7 min held-out part is built (for example resampling blocks of gaps with a seed) is fixed in M0.6; whether the E5 stream uses the whole of Azure code or its time-ordered held-out part is fixed when M4.10 is specified (Azure code is not used for training, so either is leak-free).
Alternatives considered: (A) Azure 2023 for both, with the short window stated as a limitation: chosen; (B) BurstGPT_1 for training and held-out: rejected (near-Poisson locally, 1 s clock, multi-hour gaps, a different workload); (C) Azure P/O distributions with BurstGPT arrival times: rejected for now (mixes two traces and BurstGPT's arrival structure is rate drift).
Consequences: M0.4 (split) and M0.6 (sampler) depend on this. context.md "Sampled from Azure 2023" and the E5 lines are updated to match (E5 tests on Azure code, not BurstGPT). docs/numbers.md E5 rows and configs/experiments/load_generalization.yaml follow.

## ADR-017: Handling of BurstGPT failure rows (output_tokens == 0)
Status: accepted, Option B (accepted 2026-10-20, M0.3 close) · Date: 2026-10-03 (decision 2026-10-20)
What: Drop failure rows (output_tokens == 0) downstream with drop_failures=True and state it in the report.
Why: Failure rows have zero prompt tokens (99.94% of BurstGPT_1, 100% of BurstGPT_3) and zero output, so they carry no load; they also create a spurious P–O correlation (BurstGPT_3 Spearman 0.213, 0.012 without them). The earlier premise that they carry prefill load is withdrawn.
Context: They are about 1.8% of BurstGPT_1 and about 7.3% of BurstGPT_3 rows (M0.2 smoke run); Azure 2023 shows zero such rows. The question was whether dropping them understates load.
Findings (M0.3, drafted by Claude on 2026-10-20 at Arnav's instruction from his notebook output; Arnav to review):
- Failure rows: Azure conv 0, Azure code 0, BurstGPT_1 25,443 (1.78%), BurstGPT_3 387,963 (7.26%).
- They carry no prompt tokens: prompt_tokens == 0 in 99.94% (BurstGPT_1) and 100% (BurstGPT_3) of failure rows, and their share of all prompt tokens is 0.0 to four decimals. The earlier premise (non-zero prompt tokens, prefill consumed) does not hold and is withdrawn; they are empty requests with no prefill and no decode.
- By Log Type, failure share: BurstGPT_1 API log 1.33% (16,931/1,275,518), Conversation log 5.52% (8,512/154,219); BurstGPT_3 API log 7.56% (386,107/5,110,404), Conversation log 0.79% (1,856/233,617). By Model: BurstGPT_1 ChatGPT 1.73%, GPT-4 2.05%; BurstGPT_3 ChatGPT 7.74%, GPT-4 4.52%. The share-per-day plot is in notebook cell (k) and is not summarised here.
- Effect of keeping them: a spike of zeros pulls every output-token percentile down, and BurstGPT_3's Spearman P–O is 0.213 with them against 0.012 without. Dropping them thins the arrival count by 1.78% and 7.26%.
- Source: the printed output of notebooks/01_trace_eda.ipynb cells (k) and (d); results/eda/trace_summary.json (failure_rows, failure_share).
Decision: Option B, accepted 2026-10-20 (Arnav, M0.3 close): drop_failures=True everywhere downstream, stated in the report. They add no load, so dropping hides nothing; the thinning of arrivals is small and the sampler sets the rate in req/s anyway; M0.4's normalisation constants are computed after dropping.
Alternatives considered: (A) keep as prefill-only requests: rejected, the premise is false; (B) drop (drop_failures=True) and state it: chosen; (C) drop for P/O distributions but keep in arrival counts: rejected, since BurstGPT no longer drives E5 (ADR-016) and its arrival timing need not be exact.
Consequences: Affects normalisation constants (M0.4). Azure conv and Azure code have 0 failure rows, so for the Azure traffic that drives training, held-out and E5 the drop is a no-op, kept for consistency and for BurstGPT if it is ever used. The loaders keep reporting df.attrs["n_failures"] so the count stays visible.

## ADR-018: Stream sampler and session wiring (M0.6)
Status: proposed · Date: 2026-10-20
What: sample_stream rescales the clock of the Azure train or held-out part to a target mean rate in req/s with one factor, keeps the trace's own token counts, and layers ADR-009 conversations on top of it; the seed controls the conversation layer only.
Why: One factor keeps the relative burst structure that makes the Azure trace worth using, and drawing only the conversations from the seed keeps arrivals and lengths identical across seeds and policies (same traffic for every baseline), while still giving the prefix cache different but valid conversation structure per seed.
Context: ADR-009 (accepted) fixes the session parameters and says think-time gaps are not compressed; ADR-016 leaves "how a stream longer than the held-out part is built" open for M0.6. The sampler must turn those into code without changing Azure's arrival process.
Decision (proposed, implemented in src/marl_lb/data/traces.py; Arnav to accept or change):
- Rate: t' = (t − t_first) × ((n − 1) / span / target_rate); the mean rate is defined as (n − 1) / (last − first) = 1 / mean gap. The first arrival is moved to 0 (the held-out part starts at 0 too).
- Conversations: requests are walked in time order; an unused request starts a conversation whose plan (turn count, target think times, history flags) is drawn from a generator seeded by (seed, row index), so the plan does not depend on the rate. Turn k+1 is the unused later request whose arrival is nearest to (previous turn's arrival + think time). Turns whose target time falls after the stream end are dropped (conversation cut by the window).
- Distribution family (set in configs/sessions.yaml): inverse CDF linear in log(value) through the ADR-009 quantiles; turns rounded up; single-turn share as a point mass. It reproduces the listed quantiles by construction and fits nothing. Two anchors are not in ADR-009: the gap maximum 4,825,463 s (printed by the M0.3 notebook) and the gap minimum 1 s (an assumption: BurstGPT's clock resolution, not a measured minimum).
- Output record: StreamRequest(arrival_s, prompt_tokens, output_tokens, conversation_id, turn_index, history_included). history_included (Bernoulli, history_included_prob) says that the turn re-sends the previous turn; the prefix cache (M1.6) takes the cached prefix as min(prompt, previous prompt + previous output). prompt_tokens itself is not changed, so the length distribution and the normalisation constants stay as measured.
Measured consequence (printed output of sample_stream on data/raw Azure conv, seed 0; not yet in results/): the share of requests that are follow-up turns falls as the rate rises, because think times are not compressed and the stream gets shorter. Train part: 64.8% at 2 req/s, 57.4% at 5, 43.8% at 20. Held-out part: 51.3% at 2, 41.2% at 5, 29.2% at 20. So the cache has less to reuse at high ρ; this is the ADR-009 Consequences risk, now measured, and summarise_stream() reports it for any stream.
Alternatives considered: (A) seed also shifts or resamples arrivals and lengths (cyclic offset, block bootstrap): more traffic variety across seeds, but it changes the traffic each policy sees and is a larger design choice; not done. (B) generate sessions first and take their superposition as the arrivals: breaks Azure's arrival process and burst structure; rejected. (C) compress think times with the rate: rejected by ADR-009.
Open points: (1) A stream is one pass over the part: n requests lasting n / rate seconds (held-out: 2,871 requests, 143.5 s at 20 req/s). If an episode needs more requests or more seconds than that, a longer stream must be built (for example a seeded block bootstrap of gaps and requests, alternative A); that depends on episode_ticks and dt, which M1.2 sets, so it is deferred to M1.2 and needs its own ADR then. (2) Across seeds, arrivals and lengths do not vary, so the seed spread of any result measures conversation structure and learning noise, not traffic variability; the report must say so. (3) The gap minimum of 1 s is an assumption.
Consequences: M1.2 maps StreamRequest to Request; M1.6 reads history_included; M1.28 converts ρ to a rate and calls this sampler. Follow-up share is reported with any cache result.

