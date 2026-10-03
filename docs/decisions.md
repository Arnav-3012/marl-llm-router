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

## ADR-007: Showcase without hosted LLMs (Docker profiles + Gradio sim demo on HF Spaces)
Status: accepted · Date: 2026-10-03
Context: The project should be demo-able at no cost. Hosting live LLMs publicly is out of scope and Docker on macOS cannot use Metal.
Decision: Docker image with compose profiles `cpu` (llama-server CPU containers) and `host` (native llama-servers via host.docker.internal). A Gradio Space on free CPU runs the simulator with trained weights and calibration.json. A 2-minute video shows the real router on the Mac.
Alternatives considered: Paid GPU hosting (budget is zero); hosted API LLMs (not our servers, no calibration story); video only (not interactive).
Consequences: The public demo is simulator-only and must say so. Real-server evidence is the video plus E7 results.

## ADR-008: Interview-readiness process
Status: accepted · Date: 2026-10-03
Context: The CV project must be defensible in an interview and in the course viva. Passing tests does not show that Arnav can explain, break or justify what he built.
Decision: After every Tier A task, a viva check (3 questions: explain, break-it, justify) is answered in Arnav's own words in docs/viva.md before any answer is shown, and graded by Claude; "wrong" items go to a Revisit list. Headline numbers live in docs/numbers.md and come only from results/. Break-it experiments in M2 and M3 have hypotheses written in docs/viva.md BEFORE the run. Viva-critical pieces (reward, DDQN update, SED, CI calculation) are rewritten from memory in a blank file and diffed against the real one.
Alternatives considered: A single viva prep at the end (late, answers forgotten, no debugging stories); a wiki only (reading is passive, answers would not be in his own voice).
Consequences: About 15 minutes extra per task. Real debugging stories from the break-it experiments. Answers in his own voice. Hypotheses are pre-registered, so a wrong prediction is kept as evidence of learning rather than hidden.

## ADR-009: Conversation source for the prefix cache
Status: proposed · Date: 2026-10-03
Context: The prefix cache (sim/prefix_cache.py, cache-aware baseline, prefix-hit feature) needs a conversation id per request so that follow-up turns can reuse a server's cached prefix. Azure LLM Inference 2023 is believed to have only TIMESTAMP, ContextTokens and GeneratedTokens, so it carries no conversation id. BurstGPT has a Session ID, but only for conversation-mode rows, and it is not yet known whether Request tokens grow within a session (history included) or how long sessions are.
Decision: Not yet taken. Decide after the M0.3 findings (Session ID coverage, token growth within a session, session length distribution, Azure columns confirmed). The M0.3 findings are recorded in this ADR.
Alternatives considered: (A) BurstGPT Session IDs for the cache experiments: real session structure, but only a subset of rows, and a different trace from the Azure traffic used elsewhere; (B) synthetic sessions layered on Azure traffic: same arrival and length distributions as the main experiments, but session structure is invented and must be stated as an assumption (parameters in configs/, not in code).
Consequences: Until decided, cache experiments (E1 Cache-aware, cache hit rate) are not claimed as validated on real conversation structure. Whichever option is chosen, the report states the source of the conversation id.

## ADR-010: Delayed-reward credit (s', discount)
Status: proposed · Date: 2026-10-03 (amended 2026-10-03, S.7; amended 2026-10-03, S.8)
What: Recommended option (b): s' is the agent's next decision observation and the discount is γ per decision (not per tick); the delayed outcome is the reward of the decision that produced it; a drop is an R_SLA of −5 shared by every agent that acted on the request; cost and KV terms follow ADR-014.
Why: Option (a) (s' at the resolution tick, γ^Δ) is withdrawn because at resolution the agent may be idle or looking at a different request, and an agent's per-request transitions overlap during Δ, so a resolution-tick state is not the successor of that decision.
Context: ADR-004 credits an outcome to the decision-time state and action, but the outcome resolves Δ ticks later, possibly on another server. The DDQN target needs a defined next state s' and discount for such a transition, and the choice changes what the agent learns. Under ADR-013 an agent decides on at most one request per tick, so its decisions form a sequence of observations even when outcomes resolve out of order.
Decision: Recommended (b). Not yet approved.
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
Status: proposed · Date: 2026-10-03 (amended 2026-10-03, S.7; amended 2026-10-03, S.8)
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
- λ_sat is found by a sweep on train traffic with several seeds, plus a check that the sweep is monotone (completion ratio non-increasing, drop rate and backlog ratio non-decreasing in λ, within seed noise; if not monotone, refine the grid and report it). λ_sat is recorded per trace and per cache setting (cache on/off), in this ADR and in results/. It is measured in M1.26–M1.28 (criterion approved in M1.25.1, value filled in M1.28). The helper lives in data/load.py (Tier B). Not yet approved.
Alternatives considered: ρ from nominal service rates in calibration.json (no sweep needed, but ignores batching, KV limits and cache effects, so ρ=0.95 may not mean near-saturation); saturation of the best heuristic over all policies (a fairer capacity, but more runs and the best policy changes with the configuration).
Consequences: ρ is defined relative to global-form SED, so a policy better than SED can run at ρ near or above 1 without saturating; the report says so. The 0.95 and 1% thresholds are assumptions, so ρ values shift if they change. The baseline evaluation (M1.29) comes after λ_sat is known. If server classes, calibration.json, trace or cache setting change, λ_sat must be re-measured. Report the maximum arrivals per agent per tick at λ_sat (λ_sat·dt/N with uniform entry, ADR-013). Because ADR-013 allows one decision per agent per tick, this must stay well below 1; otherwise the agent decision rate, not the servers, becomes the bottleneck, and global SED (which bypasses agents) would not reveal it.

## ADR-012: Heuristic baselines, local vs global
Status: proposed · Date: 2026-10-03 (amended 2026-10-03, S.7; amended 2026-10-03, S.8)
What: SED, JSQ, Po2 and Cache-aware each exist in a local form (only the 7 observation features, actions in {Accept, Forward, Defer}) and a global form (full cluster state, direct assignment); SED-local is an approximation of SED, not SED.
Why: Classical heuristics assume full state; a fair test of learning needs a baseline with the same information as the agents, and the global form stays as the information-advantaged reference. SED-local compares own expected wait with the neighbour MEAN wait and has no per-neighbour service estimate, so calling it plain SED would overstate it.
Context: The agents act in {Accept, Forward, Defer} on a local observation (own state plus neighbours within radius k). SED, JSQ, Po2 and Cache-aware are classically defined as direct assignment with full cluster state. Neither architecture.md nor ADR-005 says how they map onto the agent action space, and comparing agents against a baseline with more information is not a fair test of learning.
Decision: SED, JSQ, Po2 and Cache-aware each exist in two forms. Local: a LocalPolicy.act(obs[7], mask[3]) -> action in {Accept, Forward, Defer} that may use ONLY the 7 observation features, so only the neighbour MEAN wait, never per-neighbour values. Example, SED-local: Accept iff own expected wait ≤ neighbour mean wait, otherwise Forward; the environment picks the Forward target (ADR-013); with k=0 it always Accepts, which is equivalent to entry-rule routing (uniform random entry, ADR-013). SED-local is an approximation of SED, not SED: it has no per-neighbour service estimate. The report names it as such ("SED-local"); the name is not changed. Global: a GlobalPolicy.assign(cluster_state, request) -> server index, full cluster state, no Forward/Defer. The cluster exposes a direct-assignment mode for global policies, covered by the M1.11 tests. Random and Round-robin need no state. Local forms are the fair peers of the DQN agents and are used in M2.12, E1 and E4; global forms are information-advantaged references and define λ_sat (ADR-011). Not yet approved.
Alternatives considered: Global only (the strongest classical baseline, but agents never see that information, so a gap would mix learning quality with information); local only (fair, but loses the reference for how much the information restriction costs).
Consequences: Tests (M1.22) and baseline runs (M1.29) cover both forms and run against the two interfaces in architecture.md. The exact local rules for JSQ, Po2 and Cache-aware (still limited to the 7 features, e.g. Cache-aware-local uses the prefix-hit feature) and the fallback when the preferred action is masked are fixed by the M1.21 amendment, before the M1.22 tests are written. SED-local at k=0 behaves like entry-rule routing, which gives M1.30 a sanity check; it behaves like Random only because the entry rule is uniform random (ADR-013). The exact local rules for JSQ, Po2 and Cache-aware are an amendment of this ADR written in M1.21 (which was previously where this ADR was approved; approval now happens in M1.8.1 because M1.11 builds the direct-assignment mode). With only the neighbour mean, local rules cannot pick the best neighbour, which is why the Forward target is chosen by the environment.

## ADR-013: Decision protocol and Forward target
Status: proposed · Date: 2026-10-03 (amended 2026-10-03, S.8)
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
Status: proposed · Date: 2026-10-03 (S.8)
What: Cost and KV penalty are per-request terms charged at resolution to the serving agent's Accept transition only; the cooperation term −β·B_t is charged to every transition at its decision tick.
Why: ADR-010 makes transitions per decision, so per-step terms (λ·C, −β·B_t, "−1 per step KV > 80%") have no transition to attach to; making them per-request keeps credit tied to the agent that actually caused them and keeps the cost metric consistent with the reward.
Context: context.md defined r = R_SLA − λ·C − β·B_t with the KV penalty and C accrued per step. Under ADR-010 (and ADR-013) a transition exists only at a decision, and an agent has no transition on ticks where it is idle or merely holds requests.
Decision: Recommended option A. Not yet approved.
- Cost (per request): C_j is charged at resolution to the serving agent's Accept transition only. C_j = c_class(serving server) × service seconds attributed to j, where prefill seconds a·(P − P_cached) go fully to j and each decode step's t_step(B_i) is split equally across the B_i requests in that step. Invariant, tested in M1.17: Σ_j C_j = Σ_i c_i × busy_seconds_i over an episode (j over all requests with attributed service, including those dropped at the drain horizon, assumption; i over servers).
- KV term (per request): −w_kv × (fraction of j's resident ticks on the serving server with KV fullness > 80%), credited to the serving agent at resolution. w_kv lives in configs/, its value is set by a later ADR. This replaces the "−1 per step KV > 80%" wording in context.md and phase-plans.md. Whether its magnitude is sensible against R_SLA (±10) is checked in the M1.24 run.
- Cooperation term (built in M3.4): every transition receives −β·B_t, with B_t sampled once at that transition's decision tick (β and window W set by the M3.5 ADR).
- Transition reward therefore = shared R_SLA at resolution (ADR-010) − λ·C_j − KV term (serving agent only) − β·B_t (every transition) − the immediate Defer/Forward costs from ADR-010.
Alternatives considered: (B) accrue per-step terms into each agent's currently open transition: keeps the per-step definitions, but credits cost to whatever the agent last did (e.g. a Forward), so credit is noisy; (C) keep per-step rewards with dummy idle-tick transitions: breaks ADR-013's rule that an idle agent records no transition.
Consequences: The cost-per-request metric stays consistent with the reward through the invariant above. The server must track per-request attributed service seconds and per-request resident ticks above the KV threshold (sim.server / sim.cluster, Tier A). A request that is never served has C_j = 0. tests/test_reward.py covers the invariant and the per-request terms (M1.17). ADR-010 Decision text points here for the cost and KV terms.
