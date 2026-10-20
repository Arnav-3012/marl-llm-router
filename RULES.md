# RULES.md — non-negotiable. Conflict with any request → refuse and cite the rule number.

1. Claude Code runs the commands a task needs (install, tests, ruff, scripts, training, downloads, git) and reads the output itself (Arnav's instruction, 2026-10-20, replacing "Claude never executes shell commands"). It reports real output only; if a command cannot be run, it says so and does not claim the result.
2. Claude Code commits and pushes each task once its done-when check passes (pytest -q green and ruff clean). One task = one commit, message "<phase>: <what> (<metric if any>)". It does not edit git config, force-push, rewrite history, or commit failing code. Arnav reviews summaries in claude.ai.
3. Claude writes all code, including the files marked Tier A in docs/architecture.md, with comments that explain what each non-obvious part does (Arnav's explicit instruction, 2026-10-20, replacing the earlier "Arnav types Tier A" rule; reason: time before the 2026-10-27 deadline). Claude Code runs it (rule 1). The tier labels stay only to mark which pieces matter most for the viva; the understanding work (optional self-checks in docs/viva.md, rewrite-from-memory tasks, ADR findings in his own words) is deferred, not dropped.
4. Code comes with comments, not a per-line lecture: no "one part per message" or 30-line limit. After the code, explain in at most a few lines and state the command that verifies it (and its real result, rule 1).
5. Teaching protocol (faded worked examples, "challenge", hints) is suspended; it applies again only if Arnav asks for it ("teach me", "challenge").
6. No new dependencies without Arnav's approval.
7. No change to state, actions, reward, metrics or experiment design without an ADR in docs/decisions.md and Arnav's approval.
8. Never invent numbers. Server parameters come only from profiling/calibration.json; results only from results/.
9. data/raw/ is read-only.
10. A task is ticked in docs/phase-plans.md only when its done-when is met, shown by passing output that Claude Code itself ran (no run, no tick).
11. Be honest. If Arnav's code or idea is wrong, say so plainly with the reason and a hint. No flattery.
12. Unsure about tier, scope or intent → ask; never assume.
13. Nothing from M6 onward starts before M5's charts exist in results/.
14. Every new or amended ADR in docs/decisions.md carries a "What:" line (the decision in one sentence) and a "Why:" line (the reason, in one or two sentences), directly under Status/Date.
15. Every teaching chunk or part opens with a plain-language "what we are doing and why" (before any maths or code), then the code. Code for beginners stays simple (plain loops and prints, no clever one-liners), and the chunk's variable names match what Arnav already typed. (Suspended 2026-10-20 while rule 3 applies; back in force if Arnav asks for teaching.)
16. Every chunk or part carries an intuition test: a predict-before-run question (direction, rough size or ranking) that Arnav answers in one line BEFORE he runs the cell. After the run he compares prediction and output and notes any surprise in his own words. Claude does not grade it; a wrong prediction is useful evidence, not a failure. (Suspended 2026-10-20 while rule 3 applies; back in force if Arnav asks for teaching.)