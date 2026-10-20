# CLAUDE.md

Project: MARL LLM Router — independent Double-DQN agents routing requests across heterogeneous LLM servers. AAI course project + CV project. Owner: Arnav.
Shipping before the 2026-10-27 deadline comes first; Arnav's understanding work (viva self-checks, ADR findings in his own words) is deferred, not dropped.
Hard rules: RULES.md (read every session; it overrides everything here).

## Mode (changed 2026-10-20; replaces the earlier teaching mode)
Claude Code does Arnav's part too: it writes Tier A and Tier B code with explanatory comments, runs commands and tests, checks the results, and commits and pushes each task once its tests pass (RULES.md #1–#5). Arnav reviews summaries in claude.ai. The Tier A teaching protocol ("Arnav types it", faded worked examples, one part per message, the "never run / never commit" rules) is removed; it applies again only if Arnav asks for teaching ("teach me", "challenge"). Kept unchanged: never invent numbers, an ADR for any change to state, actions, reward, metrics or experiments, tick only when the done-when is met, tests/ruff/conservation test, config-only values, seeds, the end-of-session steps.

## Session start
Read in order: RULES.md → docs/context.md → docs/phase-plans.md (current phase, first unchecked task) → docs/mistakes.md → last 3 entries of docs/logs.md. Read docs/architecture.md and docs/decisions.md when touching interfaces, state, reward or metrics.
If Arnav's message names the tasks, start them (that is the "go"). Otherwise reply with exactly:
Phase: … | Task: … | Tier: A/B
Plan: one line
and wait for "go".

## Interview-readiness (every task, ADR-008 as amended 2026-10-20)
At the start of every task, Claude Code writes its docs/viva.md entry (prerequisite, bet prompt, questions, collapsed reference answers) per ADR-008. Tier B: 1 question; Tier A: 3 (explain, break-it, justify).
Every task also adds any new term it introduces to docs/glossary.md, in the same edit as its docs/viva.md entry; never state an undecided value there, name the ADR or task that sets it.
1. Arnav's self-check is optional: when he does it, he writes his bet before the task, attempts each question before expanding the answer, and marks it got it / partly / missed. No Claude grading.
2. Anything not "got it" goes to a "Revisit" list at the bottom of docs/viva.md and is re-asked when he next does a session of self-checks.
3. Results go into docs/numbers.md only from results/ files, with the experiment path.
Break-it experiments are scheduled at M2 and M3 (see phase-plans.md); never skip them.

## Tiers (map in docs/architecture.md)
- Tier A — core logic. Claude Code writes it with explanatory comments. The tier marks the pieces that matter most for the viva (reward, DDQN update, SED, CI calc: rewrite-from-memory tasks are deferred, not dropped).
- Tier B — glue, boilerplate, tests, configs, docs, docker/, demo/. Claude Code writes it.
- File not in the map → ask which tier. Never downgrade A → B yourself.

## Engineering rules
- Python 3.11, uv, src layout, package marl_lb. Torch device: mps, else cpu.
- Reproducible: config YAML + seed → identical output. No magic numbers in code; values live in configs/.
- Simulator server parameters only from profiling/calibration.json.
- Env follows the PettingZoo ParallelEnv API shape (reset/step return per-agent dicts).
- Tests: pytest -q green before any commit. Conservation test (no request lost or double-counted) is mandatory.
- ruff check + ruff format.
- Every run writes to results/<exp>/<timestamp>_seed<k>/ with the resolved config copied in.
- Evaluation: ε = 0, held-out traffic, ≥ 5 seeds, mean ± 95% CI. Never report one seed; never pick the best seed.
- Baselines run on the exact same traffic as RL policies.
- Docker on macOS has no Metal GPU: compose profile `cpu` = all containers; profile `host` = llama-servers native on the Mac via host.docker.internal.
- Demo (Gradio, HF Spaces CPU) runs the simulator with trained weights; it never serves LLMs.
- One task = one commit: "<phase>: <what> (<metric if any>)".

## End of each task
- logs.md: one dated entry (template in file); only numbers from your own run output or results/.
- decisions.md: ADR when a design choice is made or changed; every new or amended ADR carries What/Why lines (RULES.md #14; ADR-001..009 are not backfilled).
- mistakes.md: when a bug or misconception cost > 15 min, plus the rule that prevents it.
- phase-plans.md: tick only per RULES.md #10.
- architecture.md: when an interface changes.
- Then commit and push the task (RULES.md #2) and give Arnav a summary (what changed, test output, commit hash).
