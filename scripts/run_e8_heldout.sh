#!/usr/bin/env bash
# E8 held-out run (ADR-029, Reject action). Decided "adopt" after the development probe (docs/logs.md).
#   bash scripts/run_e8_heldout.sh both      # ft + control, then from scratch (about 55 min)
#   bash scripts/run_e8_heldout.sh ft        # v2 agents fine-tuned with Reject + the no-Reject control, 150 episodes, 5 seeds (about 15 min)
#   bash scripts/run_e8_heldout.sh scratch   # trained from scratch with Reject, 400 episodes, 5 seeds (about 35 to 40 min)
# First evaluates the baselines again into results/baselines_e8 (35 s; same traffic, now incl. route_to_fast_shed).
# Results: results/e8_ft + results/e8_ft_ctrl, results/e8_scratch. Held-out, 5 seeds, rho 0.5/0.8/0.95.
set -uo pipefail
cd "$(dirname "$0")/.."
unset VIRTUAL_ENV
VARIANT="${1:?usage: run_e8_heldout.sh both|ft|scratch}"
mkdir -p results/logs
TS=$(date +%Y%m%d-%H%M%S)
common=(--seeds 0-4 --lam 1 --cost-credit shared --delay-cost 0.5 --k full --rho-train 0.5,0.8,0.95 --workers 5)
fail=0

run_ft() {
  echo "== E8: fine-tune with Reject (e8_ft) and without (e8_ft_ctrl), 5 processes each"
  local ft=(--init-from main_v2 --eps-start 0.3 --episodes 150 --eps-decay 75)
  uv run python -m scripts.run_experiment --exp e8_ft --reject "${ft[@]}" "${common[@]}" > "results/logs/e8_ft_$TS.log" 2>&1 & local p1=$!
  uv run python -m scripts.run_experiment --exp e8_ft_ctrl "${ft[@]}" "${common[@]}" > "results/logs/e8_ft_ctrl_$TS.log" 2>&1 & local p2=$!
  wait $p1 || fail=1
  wait $p2 || fail=1
}
run_scratch() {
  echo "== E8: from scratch with Reject (e8_scratch)"
  uv run python -m scripts.run_experiment --exp e8_scratch --reject --episodes 400 --eps-decay 200 "${common[@]}" > "results/logs/e8_scratch_$TS.log" 2>&1 || fail=1
}

echo "== E8 step 1: baselines_e8 (with route_to_fast_shed)"
uv run python -m scripts.evaluate --exp baselines_e8 --workers 10 2>&1 | tee "results/logs/e8_baselines_$TS.log" || exit 1
case "$VARIANT" in
  ft) run_ft ;;
  scratch) run_scratch ;;
  both) run_ft; run_scratch ;;
  *) echo "variant must be both, ft or scratch"; exit 1 ;;
esac
[ $fail -eq 0 ] || { echo "FAILED, see results/logs/e8_*_$TS.log"; exit 1; }
echo "DONE e8_heldout $VARIANT $(date +%Y-%m-%dT%H:%M:%S)"
