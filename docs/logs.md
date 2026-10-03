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

## 2026-10-03 — Phase S: S.7 plan fixes round 4
Done: Added ADR-013 (decision protocol and Forward target, Proposed) and amended ADR-001 consequences, ADR-010 (now option (b): s' = next decision observation, γ per decision; credit, Defer/Forward, episode end and Transition record specified; 100-tick boundary replaced by "measure Δ in M1"), ADR-011 (operational λ_sat criterion on global SED: goodput/offered < 0.95 or drop > 1%, several seeds, monotone check, per trace and cache setting) and ADR-012 (local rules use only the 7 features; LocalPolicy/GlobalPolicy; direct-assignment mode). architecture.md: two policy interfaces, Transition record, idle-agent and Forward-target rules, direct-assignment mode. phase-plans.md: new M1.8.1, M1.9/M1.11/M1.14 follow ADR-013, M1.16–M1.18, M1.21, M1.22, M1.26, M1.27, M1.30(i) and M2.8 updated, S.7 added, header note updated; no IDs renumbered. RULES.md: new rule 14 (every new or amended ADR carries What and Why lines); the ADR template carries them. context.md needed no change.
Learned: A resolution-tick s' is not the successor of the deciding action when agents may be idle or hold several requests, so the decision protocol (ADR-013) had to come first.
Blockers: ADR-013 must be approved (M1.8.1) before M1.9; ADR-010 before M1.17; ADR-012 before M1.22; ADR-011 stays Proposed until λ_sat is measured in M1.26; ADR-009 waits on M0.3. Existing ADRs 001–009 have no What/Why lines (rule 14 applies from now on; backfill only if Arnav asks).
Next: Arnav reviews the diff, runs ruff, pytest if needed, and commits; then M0.1.

## 2026-10-03 — Phase S: S.8 plan fixes round 5
Done: Added ADR-014 (reward terms under per-decision transitions, Proposed: per-request cost at resolution with the invariant Σ_j C_j = Σ_i c_i × busy_seconds_i, per-request KV term, −β·B_t at each decision tick; alternatives B and C recorded). Amended ADR-010 (drop = shared −5 to acting agents only, last holder for metrics only, discarded-transition fraction logged, cost/KV point to ADR-014), ADR-004 (Consequences note and What/Why), ADR-011 (λ_sat by completion ratio, drop rate and backlog growth; low-load SLA attainment; max arrivals per agent per tick), ADR-012 (SED-local is an approximation of SED) and ADR-013 (deferred to back of queue, uniform random entry, SED-style Forward target). phase-plans.md: M1.8.1 now approves ADR-012 and ADR-013, M1.16 ADR-010 and ADR-014, new M1.25.1 approves ADR-011's criterion, M1.21 now only the ADR-012 local-rules amendment; M1.9, M1.11, M1.13, M1.17, M1.18, M1.24, M1.26, M1.27, M2.8 and M3.4 text updated; S.1–S.7 ticked (Arnav confirmed uv sync and ruff check), S.8 added unticked; no IDs renumbered. context.md: deadline 2026-10-27, Reward and Entry bullets. architecture.md: entry, deferred-to-back, Forward target, cost attribution note. New docs/guide-errata.md. CLAUDE.md: What/Why line in the end-of-session section.
Learned: Per-step reward terms have no transition to attach to once transitions are per decision; making cost and KV per request keeps credit with the agent that caused it.
Blockers: ADR-012/013 approved at M1.8.1, ADR-010/014 at M1.16, ADR-011 criterion at M1.25.1; ADR-009 waits on M0.3. The guide-errata list is limited to the items in the brief because the guide was not available.
Next: Arnav reviews the diff and commits; then M0.1.

## 2026-10-03 — Phase S: S.8 review
Done: S.8 review: ADR-010..014 accepted (ADR-011 criterion only; λ_sat value TBD, measured in M1.26–M1.28 and recorded under the ADR as a measurement). Fixes: duplicated M1.21 sentence removed from ADR-012; M1.8.1, M1.16, M1.25.1 and S.8 ticked; Δ measurement moved from M1.16 to M1.24; M1.28 and M1.21 done-when reworded; M3.4b formula is now the full ADR-014 transition reward; four lines added to guide-errata.md (F3, C2/F3, G4, H4).
Learned: Approval tasks can be ticked on Arnav's approval; implementation tasks still wait for passing tests (RULES.md #10).
Blockers: ADR-009 still proposed (waits on M0.3); the M1.21 ADR-012 amendment needs approval before M1.22.
Next: Arnav commits; then M0.1.

## 2026-10-03 — Phase M0: plan change, M0.3 and M0.4 to Tier A
Done: context.md and architecture.md ownership maps now list notebooks/01_trace_eda.ipynb (analysis cells) and data/processed.py (normalisation, split) as Tier A; data/traces.py loaders, download script and stream sampler stay B; architecture.md has a data.processed entry and module-map rows. phase-plans.md: M0.3 and M0.4 are [A]; added M0.3a, M0.3.1 (tests before M0.4), M0.4a, M0.6a; header note added; no IDs changed. notebooks/01_trace_eda.skeleton.ipynb written (the 0-byte placeholder 01_trace_eda.ipynb cannot be read or edited by the tools; Arnav renames the skeleton over it) with: imports, a loader TODO, questions (a)-(j) with empty code cells, and a Bets cell.
Learned: The M0.1 bets are not in docs/viva.md yet, so the Bets cell points to a section that does not exist until M0.1 is done.
Blockers: None. M0.3 is Tier A: Arnav writes the cells and ADR-009 text. ADR-009 stays Proposed until then.
Next: Arnav reviews, stages, commits; then M0.1 (write the bets in docs/viva.md before looking at the data).

## 2026-10-03 — M0.1: download raw traces
Done: configs/data.yaml (4 sources, URLs from the official pages), scripts/download_data.py (streaming, resume, sha256, manifest, --only, --dry-run), data/README.md, .gitignore now tracks data/raw/MANIFEST.json. Run output of the script:

```
<Arnav pastes the printed table here>
```

Learned: <Arnav>
Blockers: sha256 fields in configs/data.yaml are null until Arnav pins them from MANIFEST.json (optional). Azure and BurstGPT_1 URLs track a branch, not a tag, so the files could change upstream; the manifest sha256 is the record.
Next: M0.2 once the manifest is committed.

## 2026-10-03 — Process change: viva.md becomes a Q&A reference (ADR-008 amended)
Done: ADR-008 amended (What/Why added; Claude grading removed; every task gets a viva.md entry written by Claude Code, Arnav self-checks; Tier B = 1 question, Tier A = 3). docs/viva.md rewritten with "How to use this file", entry template, the M0.1 entry (bets: Azure 2023 time span, BurstGPT_3 Session ID fraction; Arnav's lines empty; Q1 justify with collapsed answer), Revisit and Break-it log kept. context.md Interview-readiness, phase-plans.md (every `a` task wording, header note, line 7) and CLAUDE.md Interview-readiness section updated. No task IDs changed.
Learned: CLAUDE.md's Interview-readiness steps 1–3 also described Claude grading, so they were rewritten rather than adding a single line, to avoid a contradiction.
Blockers: None.
Next: Arnav answers the M0.1 bets, then continues M0.1/M0.2.
