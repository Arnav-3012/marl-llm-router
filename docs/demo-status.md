# Demo status (ADR-020)

Hard stop: 2026-10-21 13:00 IST. Updated at every gate; newest first. Times are IST.

## 2026-10-20 18:45 — Gate 1 passed: profile fitted, calibration.json written, λ_sat measured
- Quick profile finished (2610 s, 5 repeats, no joint grid). pytest all passed, ruff check and format clean. Fit, residual plots (results/profiling/20261020-173822_seed0_quick/plots/), ADR-015 accepted as option A, profiling/calibration.json written, SLA targets set (ADR-022), class split/prices/KV (ADR-024), ADR-018 accepted.
- Finding that changed the plan: prefill TTFT curves up with prompt length, so the simulator now prices prefill as a*E + q*E^2 (ADR-022). The first λ_sat sweep (window from t = 0) gave 0.14 req/s, an artefact of the stream's session ramp-up; with windows starting at 1800 s λ_sat = 0.591 req/s (results/saturation/lambda_sat.json). The monotonicity check is not clean (noise), stated in ADR-022.
- Smoke runs (saturation 0.7 s, evaluate 7 s, run_experiment 3 s) work end to end; smoke output goes to *_smoke folders only.
- WAITING FOR ARNAV: run `caffeinate -dimsu bash scripts/run_stage_1.sh` (docs/RUN.md §2-§3; the sweep part resumes instantly, the baselines part is the real work). Paste back the last 30 lines.
- Claude meanwhile: agent/training smoke at realistic window lengths (a 60 s window holds only ~28 requests at ρ = 0.8, so the training window needs lengthening, ADR-021/023), then dashboard.
- Blockers: none.

## 2026-10-20 17:50 — Protocol change: Arnav runs heavy jobs
- Heavy jobs (profiling, λ_sat sweep, all training, final evaluation, big exports) are run by Arnav; commands are in docs/RUN.md. Claude Code runs only pytest, ruff, type checks and smoke runs under about 2 minutes.
- The quick profile (5 repeats) was started by Claude Code at 17:38, before this change, and is still running. WAITING FOR: it to finish (docs/RUN.md §1). Do not start another copy.
- Meanwhile (write-only): M1 simulator code and tests (config, utils, request, kv_cache, prefix_cache, server, cluster, metrics, heuristics, evaluate), DDQN agent + train loop, written but NOT yet run. Next to write: saturation sweep script, train/eval scripts, stage scripts, dashboard data contract.
- Blockers: none.

## 2026-10-20 17:50 — Gate 0: started
- Quick profile (5 repeats, no joint grid) running since ~17:39; write-only until it finishes (no pytest, ruff or training).
- Written meanwhile: ADR-020, [demo-deferred] markers, M1 code and tests (not yet run).
- Done and pushed: ruff fix, M0.6 sampler (+ M0.6a viva), M0.5.0 viva, M0.5.1 install. Not pushed: ENV.1 files, profiling code (M0.5.2 to M0.5.4a).
- Next: Gate 1 (~18:45): pytest + ruff, commit, fit, ADR-015, calibration.json.
- Blockers: none.
