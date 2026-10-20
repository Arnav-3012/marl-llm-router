#!/usr/bin/env bash
# Stage 2: M2.12 prototype (5 seeds, train traffic only), then the M3.12 timing run (1 seed, alone, so the timing is clean).
set -euo pipefail
cd "$(dirname "$0")/.."
unset VIRTUAL_ENV
W="${WORKERS:-$(( $(sysctl -n hw.ncpu) - 1 ))}"
mkdir -p results/logs
TS=$(date +%Y%m%d-%H%M%S)
echo "== stage 2, step 1/2: M2.12 prototype, one DDQN among SED-local agents (workers $W)"
uv run python -m scripts.run_experiment --exp prototype --solo 0 --seeds 0-4 --episodes "${PROTO_EPISODES:-150}" \
  --eval-split train --eval-window-s 300 --workers "$W" 2>&1 | tee "results/logs/stage2_prototype_$TS.log"
echo "== stage 2, step 2/2: M3.12 timing run, independent DDQN N=4, 1 seed, alone"
uv run python -m scripts.run_experiment --exp timing --seeds 0 --episodes "${TIMING_EPISODES:-20}" \
  --eval-split train --eval-window-s 300 --workers 1 2>&1 | tee "results/logs/stage2_timing_$TS.log"
echo "DONE stage_2 $(date +%Y-%m-%dT%H:%M:%S)"
