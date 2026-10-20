#!/usr/bin/env bash
# Read-only environment check (ENV.1): prints what Claude Code needs to know before running tasks.
# It changes nothing: no installs, no writes, no git operations other than `git status --short`.
# Usage: bash scripts/verify_env.sh   (run from anywhere; it moves to the repo root first)

cd "$(dirname "$0")/.." || exit 1

echo "== working directory =="
pwd

echo "== uv =="
uv --version 2>&1

echo "== python =="
python --version 2>&1

echo "== git status --short =="
git status --short

echo "== ruff =="
ruff --version 2>&1

echo "== pytest =="
pytest --version 2>&1

echo "== llama-server =="
which llama-server || echo "llama-server: not installed"

echo "== free disk space =="
df -h .

echo "== cpu =="
sysctl -n machdep.cpu.brand_string 2>&1
