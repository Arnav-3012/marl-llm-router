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
