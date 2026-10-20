#!/usr/bin/env bash
# ADR-035: one-fast-three-slow layout. Steps: (1) lambda_sat for the layout, (2) train the Reject agents for it
# (same recipe as e8_scratch), (3) tune the rewritten rule and compare on held-out traffic. Run once, from
# Terminal.app, alone:
#   cd /Users/arnav/marl-llm-router && unset VIRTUAL_ENV && nohup caffeinate -dimsu bash scripts/run_layout_test.sh > results/logs/layout_console.log 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/.."
unset VIRTUAL_ENV
export MARL_LAYOUT=fast_expensive,slow_cheap,slow_cheap,slow_cheap
export MARL_SAT_DIR=saturation_l13
mkdir -p results/logs
TS=$(date +%Y%m%d-%H%M%S)
echo "== 1/3 lambda_sat sweep for the layout ($(date +%H:%M:%S))"
uv run python -m scripts.saturation_sweep --config configs/saturation_l13.yaml --workers 10 2>&1 | tee "results/logs/layout_sat_$TS.log" || { echo "FAILED sweep"; exit 1; }
grep -q '"lambda_sat_rps": null' results/saturation_l13/lambda_sat_flat.json && { echo "FAILED: no lambda_sat found (whole grid passes)"; exit 1; }
echo "== 2/3 train Reject agents for the layout, 5 seeds ($(date +%H:%M:%S))"
uv run python -m scripts.run_experiment --exp l13_agents --reject --episodes 400 --eps-decay 200 --seeds 0-4 \
  --lam 1 --cost-credit shared --delay-cost 0.5 --k full --rho-train 0.5,0.8,0.95 --workers 5 \
  > "results/logs/layout_train_$TS.log" 2>&1 || { echo "FAILED training, see results/logs/layout_train_$TS.log"; exit 1; }
echo "== 3/3 tune the rewritten rule and compare on held-out traffic ($(date +%H:%M:%S))"
uv run python -m scripts.evaluate_layout --agents-exp l13_agents --tag l13 --workers 10 2>&1 | tee "results/logs/layout_eval_$TS.log" || exit 1
echo "DONE layout_test $(date +%Y-%m-%dT%H:%M:%S)"
