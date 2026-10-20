#!/usr/bin/env bash
# Stage 4 (ADR-027): re-run of E1, E3, E4 with the reward fix (cost shared by every agent that acted on a
# request, 0.5 per wasted Forward or Defer). Results go to *_v2 folders; the v1 results stay untouched.
# Order: baselines_v2 (35 s, now with the route-to-fast rule), phase A (main_v2, k0_v2), phase B (lambda0_v2,
# lambda2_v2), then the paired evaluation of the head-to-head page. Resumable: finished seeds are skipped.
set -uo pipefail
cd "$(dirname "$0")/.."
unset VIRTUAL_ENV
W="${WORKERS:-$(( ( $(sysctl -n hw.ncpu) - 1 ) / 2 ))}"
SEEDS="${SEEDS:-0-4}"
FLAGS="--cost-credit shared --delay-cost 0.5"
mkdir -p results/logs
TS=$(date +%Y%m%d-%H%M%S)
run() {  # run <exp> <extra args...>
  local exp="$1"; shift
  uv run python -m scripts.run_experiment --exp "$exp" --seeds "$SEEDS" --workers "$W" $FLAGS "$@" > "results/logs/stage4_${exp}_$TS.log" 2>&1
}
fail=0
echo "== stage 4, step 1: baselines_v2 (with route_to_fast)"
uv run python -m scripts.evaluate --exp baselines_v2 --workers "$(( W * 2 ))" 2>&1 | tee "results/logs/stage4_baselines_$TS.log" || exit 1
echo "== stage 4, phase A: main_v2 (k=full, lambda=1) and k0_v2 in parallel (workers $W each)"
run main_v2 --k full --lam 1 & P1=$!
run k0_v2 --k 0 --lam 1 & P2=$!
wait $P1 || fail=1
wait $P2 || fail=1
[ $fail -eq 0 ] || { echo "FAILED phase A, see results/logs/stage4_*_$TS.log"; exit 1; }
echo "== stage 4, phase B: lambda0_v2 and lambda2_v2 in parallel"
run lambda0_v2 --k full --lam 0 & P3=$!
run lambda2_v2 --k full --lam 2 & P4=$!
wait $P3 || fail=1
wait $P4 || fail=1
[ $fail -eq 0 ] || { echo "FAILED phase B, see results/logs/stage4_*_$TS.log"; exit 1; }
echo "== stage 4: paired evaluation (learned agents = main_v2)"
uv run python -m scripts.evaluate_paired --agents-exp main_v2 --workers "$(( W * 2 ))" 2>&1 | tee "results/logs/stage4_paired_$TS.log" || exit 1
echo "DONE stage_4 $(date +%Y-%m-%dT%H:%M:%S)"
