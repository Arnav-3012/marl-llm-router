#!/usr/bin/env bash
# Stage 3: the experiments. Phase A: main configuration (E1, E3 lambda=1, E4 k=full) and E4 k=0, in parallel.
# Phase B: E3 lambda=0 and lambda=2, in parallel. Then the baselines if they are not finished. Resumable.
set -uo pipefail
cd "$(dirname "$0")/.."
unset VIRTUAL_ENV
W="${WORKERS:-$(( ( $(sysctl -n hw.ncpu) - 1 ) / 2 ))}"
SEEDS="${SEEDS:-0-4}"
mkdir -p results/logs
TS=$(date +%Y%m%d-%H%M%S)
run() {  # run <exp> <extra args...>
  local exp="$1"; shift
  uv run python -m scripts.run_experiment --exp "$exp" --seeds "$SEEDS" --workers "$W" "$@" > "results/logs/stage3_${exp}_$TS.log" 2>&1
}
fail=0
echo "== stage 3, phase A: main (k=full, lambda=1) and k0 in parallel (workers $W each)"
run main --k full --lam 1 & P1=$!
run k0 --k 0 --lam 1 & P2=$!
wait $P1 || fail=1
wait $P2 || fail=1
[ $fail -eq 0 ] || { echo "FAILED phase A, see results/logs/stage3_*_$TS.log"; exit 1; }
echo "== stage 3, phase B: lambda=0 and lambda=2 in parallel"
run lambda0 --k full --lam 0 & P3=$!
run lambda2 --k full --lam 2 & P4=$!
wait $P3 || fail=1
wait $P4 || fail=1
[ $fail -eq 0 ] || { echo "FAILED phase B, see results/logs/stage3_*_$TS.log"; exit 1; }
echo "== stage 3: baselines (skips finished seeds)"
uv run python -m scripts.evaluate --workers "$W" 2>&1 | tee "results/logs/stage3_baselines_$TS.log" || exit 1
echo "DONE stage_3 $(date +%Y-%m-%dT%H:%M:%S)"
