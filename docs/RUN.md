# RUN.md: heavy jobs that Arnav runs (demo track, ADR-020)

Rules: Claude Code writes the scripts and tests and smoke-tests them (under about 2 minutes); Arnav runs every
heavy job in his own terminal and pastes back the result. Never run two heavy jobs at once (profiling timings
and training speed are both distorted by other CPU load). Durations are estimates, not measurements.

Every command starts with `cd /Users/arnav/marl-llm-router && unset VIRTUAL_ENV &&`. Long ones use
`caffeinate -dimsu` so the Mac does not sleep. Every job prints `DONE <job> <timestamp>` on success and exits
non-zero on failure; results land in results/ with the resolved config copied beside them. Jobs are resumable:
run the same command again and finished seeds/points are skipped.

Paste back to claude.ai: the last 30 lines of the log and the results path.

## RUN ALL: the order (one line each; details in the numbered sections)

| Step | You run (in your terminal) | Then |
|---|---|---|
| 1 | §1 quick profile: DONE (finished 2026-10-20, 2610 s; fit, ADR-015 = A and calibration.json written by Claude) | nothing to do |
| 2 | `caffeinate -dimsu bash scripts/run_stage_1.sh` (λ_sat sweep, already run by Claude in 3 s, so it resumes instantly; then baselines) | paste last 30 lines of each log |
| 3 | `caffeinate -dimsu bash scripts/run_stage_2.sh` (M2.12 prototype + M3.12 timing) | Claude reads the timing and sets the episode budget (ADR-021) |
| 4 | `caffeinate -dimsu bash scripts/run_stage_3.sh` (main E1, E4 k=0, E3 λ=0 and λ=2, baselines) | paste last 30 lines of each stage3 log |
| 5 | `uv run python -m scripts.export_dashboard_data && uv run python -m scripts.fill_numbers && cd demo/site && npm ci && npm run build` | Claude checks the site, screenshots, final report |

---

## 1. Quick profile (M0.5.2, 5 repeats, no joint grid)  [STATUS: DONE 2026-10-20, run folder results/profiling/20261020-173822_seed0_quick, 2610 s]

A quick profile was started at 17:38 IST in the background before this protocol was introduced. **Do not start a
second one while it runs.** Check it: `ls results/profiling/` (a folder ending `_seed0_quick`), `pgrep -fl bench_server`.
It is finished when `results/profiling/<run>_quick/meta.json` exists and the log (scratchpad `quick_run.log`) prints `wall time`.

What it does: starts 4 llama-servers (2 fast on Metal, 2 slow CPU-only), measures prefill, batch/decode, prefix cache
and interference, writes raw CSVs + meta.json (machine, llama.cpp commit, models, flags). Needs no other load.

If you need to (re)start it yourself (only when `pgrep -fl bench_server` shows nothing):
```bash
cd /Users/arnav/marl-llm-router && unset VIRTUAL_ENV && caffeinate -dimsu uv run python -u -m profiling.bench_server --quick --only prefill,batch,cache,interference 2>&1 | tee results/profiling_quick.log
```
Expected duration: about 1 to 1.5 h (estimate). Output: `results/profiling/<timestamp>_seed0_quick/{prefill,batch,cache,interference}_{fast_expensive,slow_cheap}.csv`,
`meta.json`, `config_resolved.yaml`, llama-server logs. Finished when the last line is `wall time: ... s`.
Paste back: last 30 lines of the log + the run folder name.

## 2. λ_sat saturation sweep (M1.26 to M1.28)  [smoke-tested; ALREADY RUN by Claude Code (3 s): λ_sat = 0.591 req/s, results/saturation/lambda_sat.json]

What it does: finds λ_sat for the global-SED cluster on TRAIN traffic (cache on and cache off), 3 seeds, a
geometric rate grid plus bisection, with ADR-011's three criteria; records SLA attainment at 0.1 × λ_sat and the
maximum arrivals per agent per tick. Needs the calibrated simulator (profiling/calibration.json).
```bash
cd /Users/arnav/marl-llm-router && unset VIRTUAL_ENV && caffeinate -dimsu uv run python -m scripts.saturation_sweep 2>&1 | tee results/logs/sweep.log
```
Measured: 3 s for the whole sweep on 11 workers (the simulator is fast). Re-running resumes: finished points are skipped (a point counts only if its window length and start match the config). Writes `results/saturation/{points.csv, lambda_sat.json, lambda_sat_flat.json, config_*.yaml}`.
Finished when the last line is `DONE saturation_sweep <timestamp>`. Resumable (finished points are skipped).
Paste back: last 30 lines + `results/saturation/lambda_sat.json`.

## 3. Baseline evaluation (M1.29)  [smoke-tested (1 seed, 1 load, 7 s); YOU RUN THIS FIRST]

What it does: all baselines (random, SED local k=0/1/full, cache-aware local, round-robin, JSQ, Po2, SED global,
cache-aware global) on held-out traffic at ρ ∈ {0.5, 0.8, 0.95}, 5 seeds; same traffic as the learned policies.
Needs §2 done.
```bash
cd /Users/arnav/marl-llm-router && unset VIRTUAL_ENV && caffeinate -dimsu uv run python -m scripts.evaluate 2>&1 | tee results/logs/baselines.log
```
Expected: a few minutes (estimate). Writes `results/baselines/<timestamp>_seed<k>/{metrics.json, config.yaml, DONE}` (+ replay events for seed 0).
Finished when `DONE evaluate <timestamp>`. Paste back: last 30 lines + the folder list.

**Stage 1 = §2 then §3 in one go:** `cd /Users/arnav/marl-llm-router && caffeinate -dimsu bash scripts/run_stage_1.sh`

## 4. M2.12 prototype and M3.12 timing run (stage 2)  [scripts written, not yet smoke-tested]

What it does: (a) M2.12: one DDQN (agent 0) among SED-local agents, 5 seeds, evaluated on TRAIN traffic only (a
development gate, not a result), against the all-SED-local cluster on the same traffic; (b) M3.12: one full
independent-DDQN N=4 training run alone, to time it. The timing sets the episode budget (ADR-021).
```bash
cd /Users/arnav/marl-llm-router && caffeinate -dimsu bash scripts/run_stage_2.sh
```
Expected: prototype 10 to 30 min, timing 5 to 15 min (estimates; the timing run IS the measurement).
Writes `results/prototype/*/` and `results/timing/*/{train_log.csv, timing.json, eval_metrics.json}`. Finished when `DONE stage_2 <timestamp>`.
Paste back: last 30 lines + `results/timing/*/timing.json`.

## 5. Main configuration E1 (β on, k=full, λ=1), also E3 and E4 (stage 3)  [script written, not yet smoke-tested]

What it does: trains 5 seeds of the main configuration (this is E1's learned policy, E3's λ=1 point, E4's k=full
point), plus k=0 (E4), then λ=0 and λ=2 (E3), evaluates each on held-out traffic at ρ ∈ {0.5, 0.8, 0.95}, and
finishes the baselines if they are not done. Episode counts come from ADR-021 (after the §4 timing).
```bash
cd /Users/arnav/marl-llm-router && caffeinate -dimsu bash scripts/run_stage_3.sh
```
Options: `SEEDS=0-2` for 3 seeds, `WORKERS=5` per experiment. Expected: unknown until §4 (estimate to be written there).
Writes `results/{main,k0,lambda0,lambda2,baselines}/<timestamp>_seed<k>/` and logs in `results/logs/stage3_*.log`.
Finished when `DONE stage_3 <timestamp>`. Resumable. Paste back: last 30 lines of each stage3 log + `ls results/*`.

## 6. E3: three λ values  [included in §5 phase B; standalone command below]

What it does: trains the cost dial λ ∈ {0, 1, 2} (λ=1 is the main configuration from §5) and evaluates each on held-out
traffic; the dashboard's Pareto page plots cost per request against TTFT p95 from these, next to the baselines.
You do NOT need this command if you ran stage 3 (phase B does it). Only to re-run it alone (needs §2 and the §4 timing):
```bash
cd /Users/arnav/marl-llm-router && unset VIRTUAL_ENV && caffeinate -dimsu bash -c 'for L in 0 2; do uv run python -m scripts.run_experiment --exp lambda$L --k full --lam $L --seeds 0-4 2>&1 | tee results/logs/e3_lambda$L.log; done'
```
Expected: about the same as the main run per λ (unknown until §4). Writes `results/lambda0/` and `results/lambda2/` (and `results/main/` is λ=1).
Finished when each log ends `DONE lambda<L> <timestamp>`. Paste back: last 30 lines of each log.

## 7. E4: k=0 against k=full  [included in §5 phase A; standalone command below]

What it does: trains the agents with no neighbour visibility (k=0, only their own server) and evaluates on held-out traffic; compared
with the main run (k=full) and with SED-local at k=0 and k=full. Only to re-run it alone:
```bash
cd /Users/arnav/marl-llm-router && unset VIRTUAL_ENV && caffeinate -dimsu uv run python -m scripts.run_experiment --exp k0 --k 0 --lam 1 --seeds 0-4 2>&1 | tee results/logs/e4_k0.log
```
Writes `results/k0/<timestamp>_seed<k>/`. Finished when the log ends `DONE k0 <timestamp>`. Paste back: last 30 lines.

## 8. Final evaluation  [no separate command: every run evaluates itself]

Each training run (§5, §6, §7) evaluates its trained agents greedily (ε = 0) on the held-out stream at ρ ∈ {0.5, 0.8, 0.95} and writes
`eval_metrics.json`; the baselines (§3) use exactly the same held-out streams for the same seeds. To re-run only the baselines
(for example after a bug fix) use §3's command; finished seeds are skipped, delete a seed's folder to redo it.
Check completeness before exporting: `ls results/baselines results/main results/k0 results/lambda0 results/lambda2` should show five `*_seed<k>` folders each with a DONE file.

## 9. Dashboard data export and build  [script and site written; run after stage 3]

What it does: (1) turns results/ into the JSON the site reads (a missing result becomes a labelled "not run"), (2) fills the results tables in
docs/numbers.md and README.md from that JSON, (3) installs the site's dependencies and builds it.
```bash
cd /Users/arnav/marl-llm-router && unset VIRTUAL_ENV && uv run python -m scripts.export_dashboard_data 2>&1 | tee results/logs/export.log && uv run python -m scripts.fill_numbers && cd demo/site && npm ci && npm run build 2>&1 | tee ../../results/logs/site_build.log
```
Expected: export under a minute; `npm ci` and the build 1 to 3 min (estimate). Writes `demo/site/public/data/*.json` and `demo/site/dist/`.
Finished when the export log ends `DONE export_dashboard_data <timestamp>` and the build log ends with the vite "built in" line.
To look at it: `cd demo/site && npm run preview` and open the URL it prints. Paste back: last 30 lines of both logs.
(Claude Code also does this itself at the verification step; the long-running parts are yours.)
