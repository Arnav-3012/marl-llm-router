#!/usr/bin/env bash
# ADR-032: the three "are the agents smarter than the rules?" tests, one after the other (evaluation only,
# nothing is trained): (1) feature shuffling, (2) fine load sweep, (3) server degradation.
# Run it alone (no training at the same time), from a terminal outside VS Code:
#   cd /Users/arnav/marl-llm-router && unset VIRTUAL_ENV && nohup caffeinate -dimsu bash scripts/run_smarter_tests.sh > results/logs/smarter_console.log 2>&1 &
# Results: results/shuffle/main_v2.json, results/paired_sweep/<timestamp>/, results/degradation/main_v2.json.
set -uo pipefail
cd "$(dirname "$0")/.."
unset VIRTUAL_ENV
mkdir -p results/logs
W="${WORKERS:-6}"
fail=0
echo "== 1/3 feature shuffling"
uv run python -m scripts.shuffle_features --workers "$W" 2>&1 | tee results/logs/shuffle_console.log || fail=1
echo "== 2/3 fine load sweep"
uv run python -m scripts.evaluate_paired --agents-exp main_v2 --policies ddqn_agents,route_to_fast,sed_global \
  --rhos 0.3,0.4,0.5,0.6,0.7,0.8,0.9,0.95,1.0 --out-name paired_sweep --no-events --workers "$W" \
  2>&1 | tee results/logs/sweep_console.log || fail=1
echo "== 3/3 server degradation"
uv run python -m scripts.evaluate_degradation --workers "$W" 2>&1 | tee results/logs/degradation_console.log || fail=1
[ $fail -eq 0 ] || { echo "FAILED, see results/logs/*_console.log"; exit 1; }
echo "DONE smarter_tests $(date +%Y-%m-%dT%H:%M:%S)"
