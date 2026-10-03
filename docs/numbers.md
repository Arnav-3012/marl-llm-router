# Numbers

**Rule: values only from results/ files; never from memory.** Every filled value needs its results/ path in the Source column. A row without a source path stays empty. This file feeds the report (M5.1) and the README Results table (M7.9a). Evaluation: ε = 0, held-out traffic, ≥ 5 seeds, mean ± 95% CI.

Cells use `value ± CI`. Experiment folder names follow docs/phase-plans.md; rows marked TBD get their path when the experiment is run.

## E1 — Baselines vs MARL (ρ ∈ {0.5, 0.8, 0.95})
Headline: goodput. Policies: Random, Round-robin, JSQ, Po2, SED, Cache-aware, MARL.

| Metric | Condition | Value ± 95% CI | Source path |
|---|---|---|---|
| Goodput | Random, ρ=0.5 | | |
| Goodput | Random, ρ=0.8 | | |
| Goodput | Random, ρ=0.95 | | |
| Goodput | Round-robin, ρ=0.5 | | |
| Goodput | Round-robin, ρ=0.8 | | |
| Goodput | Round-robin, ρ=0.95 | | |
| Goodput | JSQ, ρ=0.5 | | |
| Goodput | JSQ, ρ=0.8 | | |
| Goodput | JSQ, ρ=0.95 | | |
| Goodput | Po2, ρ=0.5 | | |
| Goodput | Po2, ρ=0.8 | | |
| Goodput | Po2, ρ=0.95 | | |
| Goodput | SED, ρ=0.5 | | |
| Goodput | SED, ρ=0.8 | | |
| Goodput | SED, ρ=0.95 | | |
| Goodput | Cache-aware, ρ=0.5 | | |
| Goodput | Cache-aware, ρ=0.8 | | |
| Goodput | Cache-aware, ρ=0.95 | | |
| Goodput | MARL, ρ=0.5 | | |
| Goodput | MARL, ρ=0.8 | | |
| Goodput | MARL, ρ=0.95 | | |

### E1 secondary metrics
One row per metric; expand to one value per policy × ρ cell (7 policies × 3 loads) when filling, with the same source folder.

| Metric | Condition | Value ± 95% CI | Source path |
|---|---|---|---|
| TTFT p50 | E1, each policy × ρ | | |
| TTFT p95 | E1, each policy × ρ | | |
| TTFT p99 (only if enough requests) | E1, each policy × ρ | | |
| TPOT p50 | E1, each policy × ρ | | |
| TPOT p95 | E1, each policy × ρ | | |
| TPOT p99 (only if enough requests) | E1, each policy × ρ | | |
| E2E latency | E1, each policy × ρ | | |
| SLA attainment | E1, each policy × ρ | | |
| Breach rate | E1, each policy × ρ | | |
| Drop rate | E1, each policy × ρ | | |
| Cost per request | E1, each policy × ρ | | |
| Cache hit rate | E1, each policy × ρ | | |
| Utilisation | E1, each policy × ρ | | |
| Jain's index | E1, each policy × ρ | | |

## E2 — Cooperation term on/off

| Metric | Condition | Value ± 95% CI | Source path |
|---|---|---|---|
| Goodput | cooperation on (β > 0) | | |
| Goodput | cooperation off (β = 0) | | |
| Breach rate | cooperation on | | |
| Breach rate | cooperation off | | |
| SLA attainment | cooperation on | | |
| SLA attainment | cooperation off | | |

## E3 — λ sweep (Pareto frontier)

| Metric | Condition | Value ± 95% CI | Source path |
|---|---|---|---|
| Goodput | λ=0 | | |
| Goodput | λ=0.25 | | |
| Goodput | λ=0.5 | | |
| Goodput | λ=1 | | |
| Goodput | λ=2 | | |
| Cost per request | λ=0 | | |
| Cost per request | λ=0.25 | | |
| Cost per request | λ=0.5 | | |
| Cost per request | λ=1 | | |
| Cost per request | λ=2 | | |
| TTFT p95 | λ=0 | | |
| TTFT p95 | λ=0.25 | | |
| TTFT p95 | λ=0.5 | | |
| TTFT p95 | λ=1 | | |
| TTFT p95 | λ=2 | | |
| Pareto-optimal λ values (list) | MARL vs SED vs Cache-aware | | |

## E4 — Visibility k vs centralised DQN

| Metric | Condition | Value ± 95% CI | Source path |
|---|---|---|---|
| Goodput | k=0 | | |
| Goodput | k=1 | | |
| Goodput | k=full | | |
| Goodput | centralised DQN | | |
| Price of partial observability (centralised − decentralised goodput) | k=0 | | |
| Price of partial observability | k=1 | | |
| Price of partial observability | k=full | | |

## E5 — Load and trace generalisation (train ρ=0.8)

| Metric | Condition | Value ± 95% CI | Source path |
|---|---|---|---|
| Goodput | MARL, test ρ=0.95 | | |
| Goodput | MARL, test BurstGPT | | |
| Goodput | SED, test ρ=0.95 | | |
| Goodput | SED, test BurstGPT | | |
| Goodput | Cache-aware, test ρ=0.95 | | |
| Goodput | Cache-aware, test BurstGPT | | |

## E6 — Specialisation

| Metric | Condition | Value ± 95% CI | Source path |
|---|---|---|---|
| Mean slack of accepted requests | fast-expensive class | | |
| Mean slack of accepted requests | slow-cheap class | | |
| Accept share | fast-expensive class | | |
| Accept share | slow-cheap class | | |

## E7 — Sim vs real (gap = |sim − real| / real)

| Metric | Condition | Value ± 95% CI | Source path |
|---|---|---|---|
| Goodput (sim) | SED | | |
| Goodput (real) | SED | | |
| Sim-to-real gap | SED | | |
| Sim-to-real gap | learned policy | | |
| Sim-to-real gap | Cache-aware | | |
| TTFT p95 gap | SED | | |
| TPOT p95 gap | SED | | |
