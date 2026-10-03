# Decisions (ADRs)

Required before any change to state, actions, reward, metrics or experiment design (RULES.md #7).

## Template

```
## ADR-NNN: <title>
Status: proposed | accepted | superseded by ADR-XXX
Date: YYYY-MM-DD
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
Consequences: Simple, seedable and easy to test conservation. Timing resolution is limited by dt, so dt must be small relative to t_step. Fits ParallelEnv.

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
Status: accepted · Date: 2026-10-03
Context: A routing action's outcome (SLA met or missed, cost) is only known when the request finishes, many ticks later, possibly on another server.
Decision: Store the decision-time observation and action; when the request resolves, credit the outcome reward to the transition made at that decision, using the stored state. A dropped request is charged to the last holder.
Alternatives considered: Immediate proxy rewards (biased, hides true SLA); crediting with the state at resolution (breaks the Markov link between state and action).
Consequences: Transitions complete with delay, so the training loop must keep pending transitions per request. Conservation of requests becomes critical and is tested.

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
Status: proposed · Date: 2026-10-03
Context: ADR-004 credits an outcome to the decision-time state and action, but the outcome resolves Δ ticks later, possibly on another server. The DDQN target needs a defined next state s' and discount for such a transition, and the choice changes what the agent learns.
Decision: Recommended (a), SMDP: s' = the agent's own observation at the resolution tick, discount γ^Δ. Not yet approved. Boundary: if the typical Δ exceeds 1/(1−γ) ticks (100 ticks at γ=0.99), the discounted outcome is almost invisible at decision time, so dt must be shortened or γ raised. Typical Δ is measured in M1 and recorded here before approval.
Alternatives considered: (b) s' = the agent's next decision state with no Δ discount: simple, but the target ignores how long the outcome took and mixes unrelated states; (c) expected-outcome proxy reward at decision time: no delay, but biased and hides the true SLA outcome (the reason ADR-004 rejected proxy rewards).
Consequences: With (a), pending transitions store the decision tick so Δ and γ^Δ are computed at resolution, and tests/test_reward.py and tests/test_train_loop.py assert s', Δ and the discount. The M1.18 and M2.9 implementations follow whichever option is approved.

## ADR-011: Definition of ρ
Status: proposed · Date: 2026-10-03
Context: Every experiment is specified at load ρ ∈ {0.5, 0.8, 0.95}, but ρ has no operational meaning until the capacity it is measured against is fixed. A formula from per-server service rates ignores batching, KV limits, cache hits and routing losses.
Decision: ρ = λ_arr / λ_sat, where λ_sat is the arrival rate (req/s) at which waits grow without bound over an episode for an all-SED cluster, found by a saturation sweep on train traffic. λ_sat is measured in M1.24–M1.26 and recorded here and in results/. The helper lives in data/load.py (Tier B). Not yet approved.
Alternatives considered: ρ from nominal service rates in calibration.json (no sweep needed, but ignores batching, KV limits and cache effects, so ρ=0.95 may not mean near-saturation); saturation of the best heuristic over all policies (a fairer capacity, but more runs and the best policy changes with the configuration).
Consequences: ρ is defined relative to SED, so a policy better than SED can run at ρ near or above 1 without saturating; the report says so. The baseline evaluation (M1.27) comes after λ_sat is known. If server classes or calibration.json change, λ_sat must be re-measured.
