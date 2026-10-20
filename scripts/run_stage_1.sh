#!/usr/bin/env bash
# Stage 1: lambda_sat sweep, then baseline evaluation (docs/RUN.md sections 2 and 3). Stops at the first failure.
set -euo pipefail
cd "$(dirname "$0")/.."
unset VIRTUAL_ENV
W="${WORKERS:-$(( $(sysctl -n hw.ncpu) - 1 ))}"
mkdir -p results/logs
TS=$(date +%Y%m%d-%H%M%S)
echo "== stage 1, step 1/2: lambda_sat sweep (workers $W)"
uv run python -m scripts.saturation_sweep --workers "$W" 2>&1 | tee "results/logs/stage1_sweep_$TS.log"
echo "== stage 1, step 2/2: baselines on held-out traffic (workers $W)"
uv run python -m scripts.evaluate --workers "$W" 2>&1 | tee "results/logs/stage1_baselines_$TS.log"
echo "DONE stage_1 $(date +%Y-%m-%dT%H:%M:%S)"
