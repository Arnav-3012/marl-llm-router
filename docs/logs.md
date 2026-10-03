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
