# RULES.md — non-negotiable. Conflict with any request → refuse and cite the rule number.

1. Claude never executes shell commands. When something must run (install, test, train, git, docker, download), give the exact commands in one bash block, each with a one-line purpose, and ask Arnav to paste the output.
2. Claude never commits, pushes, branches, tags, or edits git config. At task end it proposes files to stage and a commit message; Arnav runs them.
3. Claude writes all code, including the files marked Tier A in docs/architecture.md, with comments that explain what each non-obvious part does (Arnav's explicit instruction, 2026-10-20, replacing the earlier "Arnav types Tier A" rule; reason: time before the 2026-10-27 deadline). Arnav runs it and pastes output (rule 1). The tier labels stay only to mark which pieces need a viva self-check later; the understanding work (docs/viva.md self-checks, rewrite-from-memory tasks, ADR findings in his own words) is deferred, not dropped.
4. Code comes with comments, not a per-line lecture: no more "one part per message" or 30-line limit. Explain in at most a few lines after the code, and give the command to verify it.
5. Teaching protocol (faded worked examples, "challenge", hints) is suspended; it applies again only if Arnav asks for it ("teach me", "challenge").
6. No new dependencies without Arnav's approval.
7. No change to state, actions, reward, metrics or experiment design without an ADR in docs/decisions.md and Arnav's approval.
8. Never invent numbers. Server parameters come only from profiling/calibration.json; results only from results/.
9. data/raw/ is read-only.
10. A task is ticked in docs/phase-plans.md only after Arnav pastes passing test output.
11. Be honest. If Arnav's code or idea is wrong, say so plainly with the reason and a hint. No flattery.
12. Unsure about tier, scope or intent → ask; never assume.
13. Nothing from M6 onward starts before M5's charts exist in results/.
14. Every new or amended ADR in docs/decisions.md carries a "What:" line (the decision in one sentence) and a "Why:" line (the reason, in one or two sentences), directly under Status/Date.
15. Every teaching chunk or part opens with a plain-language "what we are doing and why" (before any maths or code), then the code. Code for beginners stays simple (plain loops and prints, no clever one-liners), and the chunk's variable names match what Arnav already typed. (Suspended 2026-10-20 while rule 3 applies; back in force if Arnav asks for teaching.)
16. Every chunk or part carries an intuition test: a predict-before-run question (direction, rough size or ranking) that Arnav answers in one line BEFORE he runs the cell. After the run he compares prediction and output and notes any surprise in his own words. Claude does not grade it; a wrong prediction is useful evidence, not a failure. (Suspended 2026-10-20 while rule 3 applies; back in force if Arnav asks for teaching.)