#!/usr/bin/env bash
# One command after the layout test and the live test: refresh everything that shows results.
#   bash scripts/finalize_results.sh
# 1. export the dashboard data from results/ (adds the layout and real-server sections),
# 2. fill the README and docs/numbers.md tables, 3. fill docs/presentation-prompt.md, 4. rebuild the site.
set -euo pipefail
cd "$(dirname "$0")/.."
unset VIRTUAL_ENV
uv run python -m scripts.export_dashboard_data --suffix _v2
uv run python -m scripts.fill_numbers
uv run python -m scripts.fill_presentation
(cd demo/site && npm run build)
echo "DONE finalize_results $(date +%Y-%m-%dT%H:%M:%S)"
