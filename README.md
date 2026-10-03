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
