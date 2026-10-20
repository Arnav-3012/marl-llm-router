#!/usr/bin/env bash
# E8 development probe (ADR-029): agents WITH the Reject action, trained on TRAIN traffic and scored on
# TRAIN windows (6000 s, start 1800 s). Three variants at once, 3 seeds each (9 processes):
#   probe_rej_ft   : the v2 agents (results/main_v2) fine-tuned WITH Reject, 150 episodes at rho 0.5/0.8/0.95
#   probe_ft_ctrl  : the same fine-tuning WITHOUT Reject (control: separates "more training at mixed loads" from "Reject")
#   probe_rej_mix  : trained from scratch with Reject, 300 episodes at rho 0.5/0.8/0.95
# Settings otherwise as the earlier overload probes (shared cost credit, delay cost 0.5, lambda 1).
set -euo pipefail
cd "$(dirname "$0")/.."
unset VIRTUAL_ENV
mkdir -p results/logs
common=(--seeds 0-2 --lam 1 --cost-credit shared --delay-cost 0.5 --k full
        --rho-train 0.5,0.8,0.95 --eval-split train --eval-window-s 6000 --workers 3)
ft=(--init-from main_v2 --eps-start 0.3 --episodes 150 --eps-decay 75)
uv run python -m scripts.run_experiment --exp probe_rej_ft --reject "${ft[@]}" "${common[@]}" \
  > results/logs/probe_rej_ft.log 2>&1 &
uv run python -m scripts.run_experiment --exp probe_ft_ctrl "${ft[@]}" "${common[@]}" \
  > results/logs/probe_ft_ctrl.log 2>&1 &
uv run python -m scripts.run_experiment --exp probe_rej_mix --reject --episodes 300 --eps-decay 150 "${common[@]}" \
  > results/logs/probe_rej_mix.log 2>&1 &
wait
grep -h "^DONE\|FAILED" results/logs/probe_rej_ft.log results/logs/probe_ft_ctrl.log results/logs/probe_rej_mix.log
echo "DONE e8_probe $(date -Iseconds)"
