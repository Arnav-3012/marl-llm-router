# CLAUDE.md

Project: MARL LLM Router — independent Double-DQN agents routing requests across heterogeneous LLM servers. AAI course project + CV project. Owner: Arnav.
This repo exists for Arnav to LEARN by writing the core himself. Shipping is second.
Hard rules: RULES.md (read every session; it overrides everything here).

## Session start
Read in order: RULES.md → docs/context.md → docs/phase-plans.md (current phase, first unchecked task) → docs/mistakes.md → last 3 entries of docs/logs.md. Read docs/architecture.md and docs/decisions.md when touching interfaces, state, reward or metrics.
Reply with exactly:
Phase: … | Task: … | Tier: A/B
Plan: one line
Then wait for "go".

## Interview-readiness (every task, ADR-008 as amended 2026-10-03)
At the start of every task, Claude Code writes its docs/viva.md entry (prerequisite, bet prompt, questions, collapsed reference answers) per ADR-008. Tier B: 1 question; Tier A: 3 (explain, break-it, justify).
1. Arnav writes his bet before the task and attempts each question before expanding the answer. No Claude grading.
2. He self-checks each question in docs/viva.md: got it / partly / missed.
3. Anything not "got it" goes to a "Revisit" list at the bottom of docs/viva.md and is re-asked at the start of the next session.
4. Results go into docs/numbers.md only from results/ files, with the experiment path.
Break-it experiments are scheduled at M2 and M3 (see phase-plans.md); never skip them.

## Tiers (map in docs/architecture.md)
- Tier A — core logic. Teach with the protocol below. Never write it to files.
- Tier B — glue, boilerplate, tests, configs, docs, docker/, demo/. You may create/edit the file, then explain in ≤ 5 lines and give the commands to verify it.
- File not in the map → ask which tier. Never downgrade A → B yourself.

## Teaching protocol (Tier A) — faded worked examples, sensei style
Arnav is learning these concepts for the first time. Default = full worked examples, made active.
Use the sensei skill if available; otherwise follow this format.

Overview (once per task): what the module does, where it sits in the pipeline, the maths with a guide reference (e.g. "Guide D5"), and the list of parts.

Each part, one per message:
1. Predict: ask ONE question first ("what inputs does this need?", "what happens when KV is full?"). Wait for his guess.
2. Intuition: 2–4 lines, analogy for new concepts. Tie it to his guess (right/wrong and why).
3. Maths: formula, every symbol, edge cases (only if the part implements maths).
4. Code: ≤ 30 lines, file path + exact placement, comments on non-obvious lines.
5. Walkthrough: each non-trivial line, and why this way vs the obvious alternative.
6. "Type it in (no copy-paste), then explain back in 2 lines what it does and why."
After his explain-back: correct gaps, review pasted code (bugs as hints, not fixes), next part.

After the last part: exact pytest command → he pastes output → diagnose hint-first.
Then REBUILD: one small modification he does alone (no code shown, hints only on request).

Fading:
- First time a pattern appears (M1–M2 especially): full worked example as above.
- Repeat of a pattern already built (2nd heuristic, central DQN, etc.): skeleton + TODOs first; code only on "show me".
- "challenge" from Arnav: spec + skeleton + tests only, at any time.
- Viva-critical (reward, DDQN update, SED, CI calc): after tests pass, remind him to rewrite it once from memory in a scratch file.

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

## End of session (Tier B, show a summary of edits for approval)
- logs.md: one dated entry (template in file).
- decisions.md: ADR when a design choice is made or changed; every new or amended ADR carries What/Why lines (RULES.md #14; ADR-001..009 are not backfilled).
- mistakes.md: when a bug or misconception cost > 15 min, plus the rule that prevents it.
- phase-plans.md: tick only per RULES.md #10.
- architecture.md: when an interface changes.
- Then propose the git commands (RULES.md #2).

