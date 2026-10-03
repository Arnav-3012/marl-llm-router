# Logs

One dated entry per session.

## Template

```
## YYYY-MM-DD — <phase/task>
Done:
Learned:
Blockers:
Next:
```

## Entries

## 2026-10-03 — Phase S: repo scaffold
Done: Created folder tree, docstring-only module stubs (tier marked), pyproject.toml, .gitignore, config YAMLs with sweep values from context.md, docs (architecture, phase-plans, decisions ADR-001..007, mistakes, logs), README, docker/ and demo/ placeholders.
Learned: Unspecified values (dt, prices, KV budget, lr, batch size, targets) are left null with TODOs rather than invented.
Blockers: None beyond the nulls above, which are filled in their phases via ADRs.
Next: Arnav runs the venv, ruff and pytest commands, then confirms Phase S ticks; then M0.1.

## 2026-10-03 — Phase S: S.2b interview-readiness patch
Done: Created docs/viva.md and docs/numbers.md; added ADR-008 and an Interview-readiness section in context.md; added viva-check, rewrite-from-memory and break-it tasks to phase-plans.md (existing tasks and numbering kept); added .claude/settings.local.json to .gitignore.
Learned: The existing S.2 in phase-plans.md is "Configs and docs", so this patch is tracked as S.2b to avoid renumbering. Inserted tasks use letter suffixes (e.g. M2.7a) for the same reason.
Blockers: None. docs/numbers.md source paths for E6 and E7 are TBD until those experiments define their results/ folders.
Next: Arnav reviews the new docs, runs ruff and pytest, and commits; then M0.1.

## 2026-10-03 — Phase S: S.4 plan fixes
Done: Applied the plan fixes to phase-plans.md (cut order and read-the-tests rule at the top; M0.5 sampler renamed M0.6 and takes req/s; M0.3 extended for Session ID checks; ρ → rate helper; conservation test moved before the cluster task and the conservation-fixes task removed; observation-builder and reward (R_SLA, cost) tests and implementations moved into M1; M3 reward reduced to the cooperation term; Little's law and ordering checks; train.py and CSV logging; hyperparameter protocol; M2 gate acceptance; joint-action ADR and wall-time task in M3; learning gates L1–L3). Added ADR-009 (Proposed) and the conversation-id line in context.md. M1–M3 renumbered; no other file referenced those IDs.
Learned: Several viva/break-it/rewrite tasks, ADR-008, viva.md and numbers.md already existed, so nothing was added for them.
Blockers: ADR-009 stays Proposed until M0.3. The joint-action ADR will take the next free number when written in M3.
Next: Arnav reviews the diff, runs ruff, pytest, and commits; then M0.1.

## 2026-10-03 — Phase S: S.5 plan fixes round 2
Done: phase-plans.md: added the delayed-reward credit ADR task (M1.16) before the reward tests, with reward and train-loop tests asserting s', Δ and the discount; moved the ρ helper after SED as a saturation sweep, sweep tests and helper (M1.24–M1.26) so baselines (M1.27) follow it; split the cluster task into three Tier A tasks with viva checks (M1.11–M1.13, conservation at the end of M1.13); cluster tests assert drop attribution, not reward values; M2.12 gate now 5 seeds plus an action-histogram check; break-its use 3 seeds, diagnostic only, Arnav runs the commands; M3.12 run budget about 100; M5.4 replaced by compiling the viva bank. Added ADR-010 and ADR-011 (Proposed), data/load.py to the architecture.md map (Tier B), and the "source: next line" note in context.md. M1 IDs renumbered (note in the phase-plans.md header); M2 and M3 IDs unchanged.
Learned: ρ cannot be defined before SED exists, so baseline evaluation had to move after the saturation sweep.
Blockers (S.5): ADR-010 must be approved before M1.17; ADR-011 stays Proposed until λ_sat is measured in M1.26. ADR-009 still waits on M0.3.
Next: Arnav reviews the diff, runs ruff, pytest, and commits; then M0.1.

## 2026-10-03 — Phase S: S.6 plan fixes round 3
Done: phase-plans.md: M3.4 now points to M1.18; inserted ADR-012 task (heuristics local vs global) at M1.21; heuristic tests and implementation tasks cover both forms; added the first end-to-end prototype run (M1.24, "Milestone 2, the working prototype") after the Random/Round-robin/JSQ/Po2 viva check; sanity check (i) compares SED-local and SED-global with Random; M2.12 uses SED-local. Added ADR-012 (Proposed); context.md Baselines line updated. architecture.md and ADR-005 did not define the heuristic-to-action mapping, hence the ADR. M1 IDs from the old M1.21 on shifted: ρ pieces are now M1.26–M1.28, baseline evaluation M1.29, sanity checks M1.30 (ADR-011 references updated; the S.5 entry above uses the old numbers).
Learned: Classical heuristics assume full state and direct assignment, so a fair comparison with partially observing agents needs a local form.
Blockers: ADR-012 must be approved before M1.22; the local rules for JSQ, Po2 and Cache-aware and the policy signature are open until then. ADR-010 before M1.17; ADR-009 waits on M0.3.
Next: Arnav reviews the diff, runs ruff, pytest, and commits; then M0.1.
