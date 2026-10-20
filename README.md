# MARL LLM Router

Independent Double-DQN agents, one per heterogeneous LLM server, learn Accept / Forward / Defer routing in a simulator calibrated on real llama.cpp servers. We measure goodput against strong heuristics (SED, cache-aware), the cost-latency Pareto frontier, the price of partial observability, and the sim-to-real gap, then ship it as a reproducible, demo-able project. Built as an AAI (RL & Multi-Agent Systems) course project and a CV project.

## Pipeline

Profile (real) → Calibrate (`profiling/calibration.json`) → Train (sim) → Deploy (FastAPI router on real servers) → Compare (metrics + sim-to-real gap) → Showcase (Docker, HF Space demo, video)

## Repo structure

```
configs/      YAML configs (servers, sim, dqn, experiments/)
data/         raw/ and processed/ traces (git-ignored)
profiling/    llama-server benchmarks and calibration fit
src/marl_lb/  config, utils, data, sim, policies, agents, train, eval, router
scripts/      CLI entry points (train, evaluate, run_experiment, plot, replay_trace)
docker/       image + compose profiles (cpu, host)
demo/         Gradio Hugging Face Space (simulator mode)
notebooks/    EDA and profiling notebooks
tests/        pytest suite (conservation test is mandatory)
results/      run outputs (git-ignored)
reports/      report and figures
docs/         context, architecture, phase plans, decisions, mistakes, logs
```

## Results

_Placeholder. Filled after M4/M5 from `results/` only._

## Demo

_Placeholder. Hugging Face Space link and 2-minute video after M7._

## Reproduce

_Placeholder. Commands added as phases land. Every run is config YAML + seed → identical output._

<!-- AUTO:results -->
### Demo track results (generated from results/; do not edit by hand)

| Policy | goodput ρ=0.5 | goodput ρ=0.8 | goodput ρ=0.95 | SLA attainment ρ=0.8 | cost/request ρ=0.8 | drop rate ρ=0.95 | seeds | Source (results/ files, config hash) |
|---|---|---|---|---|---|---|---|---|
| DDQN agents (k=full, λ=1) | 0.28 ± 0.00 | 0.41 ± 0.01 | 0.15 ± 0.06 | 0.86 ± 0.03 | 14.65 ± 0.85 | 0.18 ± 0.08 | 5 | `results/main_v2/20261020-215708-271951_seed0/config.yaml (+9)` · fcc655fbc615 |
| DDQN + Reject (final: conversation + code training) | 0.28 ± 0.00 | 0.43 ± 0.00 | 0.50 ± 0.01 | 0.91 ± 0.01 | 15.17 ± 0.39 | 0.07 ± 0.02 | 5 | `results/e8_mix/20261021-014456-612243_seed0/config.yaml (+9)` · 18e0488eab9c |
| DDQN + Reject (v2 agents fine-tuned) | 0.28 ± 0.01 | 0.41 ± 0.02 | 0.47 ± 0.03 | 0.87 ± 0.04 | 13.44 ± 2.25 | 0.11 ± 0.06 | 5 | `results/e8_ft/20261021-003848-508418_seed1/config.yaml (+9)` · 560d49f7295a |
| DDQN + Reject (conversation traffic only) | 0.28 ± 0.01 | 0.43 ± 0.01 | 0.49 ± 0.01 | 0.91 ± 0.02 | 15.15 ± 0.31 | 0.06 ± 0.02 | 5 | `results/e8_scratch/20261021-005237-632285_seed0/config.yaml (+9)` · 63ff6121f7df |
| DDQN fine-tuned without Reject (control) | 0.28 ± 0.00 | 0.26 ± 0.12 | 0.19 ± 0.04 | 0.55 ± 0.26 | 19.38 ± 3.49 | 0.15 ± 0.02 | 5 | `results/e8_ft_ctrl/20261021-003848-463662_seed0/config.yaml (+9)` · eed202d8b0fa |
| Cache-aware global | 0.24 ± 0.00 | 0.16 ± 0.01 | 0.01 ± 0.00 | 0.33 ± 0.02 | 20.83 ± 0.05 | 0.08 ± 0.00 | 5 | `results/baselines_v2/20261020-215629-618717_seed0/config.yaml (+9)` · 13417f43f7af |
| Cache-aware local | 0.22 ± 0.00 | 0.13 ± 0.01 | 0.01 ± 0.00 | 0.27 ± 0.01 | 20.77 ± 0.07 | 0.08 ± 0.00 | 5 | `results/baselines_v2/20261020-215629-618717_seed0/config.yaml (+9)` · 13417f43f7af |
| JSQ global | 0.24 ± 0.00 | 0.15 ± 0.01 | 0.01 ± 0.00 | 0.31 ± 0.01 | 20.89 ± 0.01 | 0.08 ± 0.00 | 5 | `results/baselines_v2/20261020-215629-618717_seed0/config.yaml (+9)` · 13417f43f7af |
| Po2 global | 0.22 ± 0.00 | 0.11 ± 0.00 | 0.01 ± 0.00 | 0.24 ± 0.01 | 21.14 ± 0.04 | 0.09 ± 0.00 | 5 | `results/baselines_v2/20261020-215629-618717_seed0/config.yaml (+9)` · 13417f43f7af |
| Random | 0.22 ± 0.00 | 0.11 ± 0.00 | 0.01 ± 0.00 | 0.23 ± 0.01 | 20.98 ± 0.07 | 0.09 ± 0.00 | 5 | `results/baselines_v2/20261020-215629-618717_seed0/config.yaml (+9)` · 13417f43f7af |
| Round-robin | 0.23 ± 0.00 | 0.12 ± 0.00 | 0.01 ± 0.00 | 0.25 ± 0.01 | 21.13 ± 0.05 | 0.10 ± 0.00 | 5 | `results/baselines_v2/20261020-215629-618717_seed0/config.yaml (+9)` · 13417f43f7af |
| Route-to-fast rule (class-aware, local) | 0.28 ± 0.00 | 0.41 ± 0.00 | 0.25 ± 0.28 | 0.86 ± 0.01 | 14.82 ± 0.14 | 0.03 ± 0.05 | 5 | `results/baselines_v2/20261020-215629-618717_seed0/config.yaml (+9)` · 13417f43f7af |
| SED global | 0.29 ± 0.00 | 0.40 ± 0.03 | 0.01 ± 0.00 | 0.84 ± 0.05 | 15.00 ± 0.24 | 0.08 ± 0.00 | 5 | `results/baselines_v2/20261020-215629-618717_seed0/config.yaml (+9)` · 13417f43f7af |
| SED local k=full | 0.23 ± 0.00 | 0.12 ± 0.00 | 0.01 ± 0.00 | 0.26 ± 0.01 | 20.76 ± 0.06 | 0.08 ± 0.00 | 5 | `results/baselines_v2/20261020-215629-618717_seed0/config.yaml (+9)` · 13417f43f7af |
| SED local k=0 | 0.13 ± 0.00 | 0.19 ± 0.00 | 0.21 ± 0.01 | 0.40 ± 0.01 | 32.64 ± 0.28 | 0.46 ± 0.01 | 5 | `results/baselines_v2/20261020-215629-618717_seed0/config.yaml (+9)` · 13417f43f7af |
| SED local k=1 | 0.23 ± 0.00 | 0.13 ± 0.01 | 0.01 ± 0.00 | 0.27 ± 0.01 | 20.75 ± 0.07 | 0.08 ± 0.00 | 5 | `results/baselines_v2/20261020-215629-618717_seed0/config.yaml (+9)` · 13417f43f7af |
| Route-to-fast + shed rule (class-aware, local, drops requests) | 0.28 ± 0.00 | 0.43 ± 0.00 | 0.50 ± 0.00 | 0.92 ± 0.00 | 15.28 ± 0.17 | 0.07 ± 0.01 | 5 | `results/baselines_e8/20261021-002734-942879_seed0/config.yaml (+9)` · 13417f43f7af |

Goodput in requests/s that met both targets; mean ± 95% interval over seeds (Student t). A policy that rejects requests is judged by its drop rate next to its goodput. The agents are the v2 agents (ADR-027).

**v1 agents (stage 3, cost paid by the serving agent only; kept for comparison, ADR-027)**

| Policy | goodput ρ=0.5 | goodput ρ=0.8 | goodput ρ=0.95 | seeds | Source |
|---|---|---|---|---|---|
| DDQN v1 | 0.26 ± 0.01 | 0.28 ± 0.11 | 0.16 ± 0.06 | 5 | `results/main/20261020-185829-362786_seed0/config.yaml` · 94fa58940f24 |

**E3 (λ sweep, ρ = 0.8)**

| Point | cost/request | TTFT p95 (s) | goodput | on frontier |
|---|---|---|---|---|
| DDQN lambda=0.0 | 19.24 ± 4.91 | 112.02 ± 193.71 | 0.27 ± 0.15 | no |
| DDQN lambda=1.0 | 14.65 ± 0.85 | 7.22 ± 0.26 | 0.41 ± 0.01 | yes |
| DDQN lambda=2.0 | 19.36 ± 4.93 | 376.86 ± 480.55 | 0.25 ± 0.18 | no |
| sed_global | 15.00 ± 0.24 | 10.48 ± 8.34 | 0.40 ± 0.03 | no |
| route_to_fast | 14.82 ± 0.14 | 7.20 ± 0.30 | 0.41 ± 0.00 | yes |
| sed_local_full | 20.76 ± 0.06 | 30.40 ± 1.35 | 0.12 ± 0.00 | no |
| cache_aware_global | 20.83 ± 0.05 | 41.61 ± 2.48 | 0.16 ± 0.01 | no |
| random | 20.98 ± 0.07 | 510.16 ± 332.54 | 0.11 ± 0.00 | no |
| jsq_global | 20.89 ± 0.01 | 85.47 ± 16.24 | 0.15 ± 0.01 | no |

**E4 (k=0 vs k=full), goodput**

| Policy | ρ=0.5 | ρ=0.8 | ρ=0.95 |
|---|---|---|---|
| DDQN k=0 | 0.13 ± 0.00 | 0.19 ± 0.00 | 0.21 ± 0.01 |
| DDQN k=full | 0.28 ± 0.00 | 0.41 ± 0.01 | 0.15 ± 0.06 |

**Balance by server class, ρ = 0.8 (ADR-030)**

| Policy | utilisation fast servers | utilisation slow servers | Jain over the fast servers | Jain over all servers (not a routing-quality measure) |
|---|---|---|---|---|
| DDQN agents (k=full, λ=1) | 0.86 ± 0.05 | 0.02 ± 0.02 | 0.99 ± 0.02 | 0.52 ± 0.01 |
| SED global | 0.86 ± 0.01 | 0.09 ± 0.06 | 1.00 ± 0.00 | 0.60 ± 0.06 |
| Route-to-fast rule (class-aware, local) | 0.87 ± 0.01 | 0.01 ± 0.01 | 1.00 ± 0.00 | 0.51 ± 0.01 |
| SED local k=full | 0.97 ± 0.00 | 1.00 ± 0.00 | 1.00 ± 0.00 | 1.00 ± 0.00 |
| Random | 0.95 ± 0.00 | 1.00 ± 0.00 | 1.00 ± 0.00 | 1.00 ± 0.00 |
<!-- /AUTO:results -->
