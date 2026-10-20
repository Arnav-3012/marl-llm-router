#!/usr/bin/env bash
# ADR-034: Reject agents trained from scratch on mixed traffic (conversation + code), then the shift test.
# Run once, alone, from Terminal.app:
#   cd /Users/arnav/marl-llm-router && unset VIRTUAL_ENV && nohup caffeinate -dimsu bash scripts/run_e8_mix.sh > results/logs/e8_mix_console.log 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/.."
unset VIRTUAL_ENV
mkdir -p results/logs
TS=$(date +%Y%m%d-%H%M%S)
echo "== 1/2 train e8_mix (5 seeds, 400 episodes, conversation + code)"
uv run python -m scripts.run_experiment --exp e8_mix --reject --mix-code --episodes 400 --eps-decay 200 \
  --seeds 0-4 --lam 1 --cost-credit shared --delay-cost 0.5 --k full --rho-train 0.5,0.8,0.95 --workers 5 \
  > "results/logs/e8_mix_$TS.log" 2>&1 || { echo "FAILED training, see results/logs/e8_mix_$TS.log"; exit 1; }
echo "== 2/2 shift test (load ramp + code trace) on e8_mix"
uv run python -m scripts.evaluate_shift --agents-exp e8_mix --workers 6 2>&1 | tee "results/logs/e8_mix_shift_$TS.log" || exit 1
echo "DONE e8_mix $(date +%Y-%m-%dT%H:%M:%S)"
