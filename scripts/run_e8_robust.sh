#!/usr/bin/env bash
# ADR-038: Reject agents trained on random server slowdowns (heavy-load calibration x {0, 0.5, 1, 1.5}),
# then the pre-set tests in the first-calibration world and in the heavy world.
# Run once, alone, from Terminal.app (nothing else running):
#   cd /Users/arnav/marl-llm-router && unset VIRTUAL_ENV && nohup caffeinate -dimsu bash scripts/run_e8_robust.sh > results/logs/e8_robust_console.log 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/.."
unset VIRTUAL_ENV
mkdir -p results/logs
TS=$(date +%Y%m%d-%H%M%S)
echo "== 1/3 train e8_robust (5 seeds, 400 episodes, conversation + code, random slowdowns)"
MARL_CALIBRATION=profiling/calibration_heavy.json uv run python -m scripts.run_experiment --exp e8_robust \
  --reject --mix-code --episodes 400 --eps-decay 200 --seeds 0-4 --lam 1 --cost-credit shared --delay-cost 0.5 \
  --k full --rho-train 0.15,0.3,0.5,0.8,0.95 --load-scales 0,0.5,1,1.5 --workers 5 \
  > "results/logs/e8_robust_$TS.log" 2>&1 || { echo "FAILED training, see results/logs/e8_robust_$TS.log"; exit 1; }
echo "== 2/3 first-calibration world (must not lose to e8_mix)"
uv run python -m scripts.evaluate_robust --tag firstcal --rhos 0.5,0.8,0.95 2>&1 | tee "results/logs/e8_robust_firstcal_$TS.log" || exit 1
echo "== 3/3 heavy world (0.10, 0.20, 0.30 req/s)"
MARL_CALIBRATION=profiling/calibration_heavy.json uv run python -m scripts.evaluate_robust --tag heavy --rhos 0.17,0.34,0.51 2>&1 | tee "results/logs/e8_robust_heavy_$TS.log" || exit 1
echo "DONE e8_robust $(date +%Y-%m-%dT%H:%M:%S)"
