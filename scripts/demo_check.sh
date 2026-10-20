#!/usr/bin/env bash
# Sh.L6: rehearsal check; prints READY or NOT READY with the reason (exit 0 only for READY).
#   bash scripts/demo_check.sh [--api http://127.0.0.1:8000] [--seconds 60] [--rho 0.5]
cd "$(dirname "$0")/.." && unset VIRTUAL_ENV && exec uv run python -m scripts.demo_check "$@"
