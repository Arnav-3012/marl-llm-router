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
Source: data/raw/MANIFEST.json (raw facts only; analysis is M0.3)
name              rows       bytes      first -> last timestamp
azure_conv_2023   19366      719188     2023-11-16 18:15:46.68 -> 2023-11-16 19:14:08.40  (span 3501.722 s)
azure_code_2023   8819       320117     2023-11-16 18:17:03.98 -> 2023-11-16 19:14:19.93  (span 3435.948 s)
burstgpt_1        1429737    50853373   5 -> 5269973  (no Session ID column)
burstgpt_3        5344021    231682327  19440110.0 -> 28943983.0
                  non-empty Session ID: 233617 of 5344021 (4.3716%)
All four: timestamps non-decreasing in file order. sha256 values are in MANIFEST.json.
```

Learned: <Arnav>
Blockers: sha256 fields in configs/data.yaml are null until Arnav pins them from MANIFEST.json (optional). Azure and BurstGPT_1 URLs track a branch, not a tag, so the files could change upstream; the manifest sha256 is the record.
Next: M0.2 once the manifest is committed.

## 2026-10-03 — Housekeeping: align config and interfaces with accepted ADRs; tick M0.1
Done: architecture.md data.traces sample_stream takes arrival_rate_rps (req/s), ρ → rate conversion noted in data/load.py (ADR-011, M1.28). configs/sim.yaml: r_drop comment per ADR-010, kv_penalty_per_step replaced by w_kv: null (ADR-014), entry_rule: uniform added (ADR-013), max_defers comment points to M1.2. phase-plans.md: M1.2 also fills max_defers (D) via ADR; M0.1 ticked. glossary.md: D / max_defers points to M1.2. No null value was set.
Learned: Stale config comments outlive the ADRs that replace them; grep configs/ after each ADR amendment.
Blockers: evaluate(... rho ...) in architecture.md and traffic.rho in sim.yaml still use ρ (not in this task's scope; the ρ → rate conversion happens before sample_stream). kv_threshold in sim.yaml may also be stale under ADR-014, unchecked.
Next: M0.2.

## 2026-10-03 — Process change: viva.md becomes a Q&A reference (ADR-008 amended)
Done: ADR-008 amended (What/Why added; Claude grading removed; every task gets a viva.md entry written by Claude Code, Arnav self-checks; Tier B = 1 question, Tier A = 3). docs/viva.md rewritten with "How to use this file", entry template, the M0.1 entry (bets: Azure 2023 time span, BurstGPT_3 Session ID fraction; Arnav's lines empty; Q1 justify with collapsed answer), Revisit and Break-it log kept. context.md Interview-readiness, phase-plans.md (every `a` task wording, header note, line 7) and CLAUDE.md Interview-readiness section updated. No task IDs changed.
Learned: CLAUDE.md's Interview-readiness steps 1–3 also described Claude grading, so they were rewritten rather than adding a single line, to avoid a contradiction.
Blockers: None.
Next: Arnav answers the M0.1 bets, then continues M0.1/M0.2.

## 2026-10-03 — Docs: docs/glossary.md
Done: Created docs/glossary.md (Tier B, docs only): 7 sections (LLM serving, Queueing, Data and traces, RL, Multi-agent, Metrics, Project-specific), alphabetical within each; every entry has plain meaning, project meaning and a "More" pointer (docs file, ADR, and guide part where the repo names one). Seeded with the Environment, Agent and Metrics terms of context.md plus the full list in the task brief. CLAUDE.md: one line under Interview-readiness says every task adds new terms to the glossary in the same edit as its viva.md entry.
Learned: Many values the brief named are not decided; the glossary names the owner instead: dt, TTFT/TPOT targets and episode_ticks (M1.2), D / max_defers (set in M1; no task names it, to confirm), class prices, class split and KV budgets (M0.5.6), β and W (M3.5), w_kv and Defer/Forward costs (later ADR), λ_sat (M1.26–M1.28), lr, batch size, warmup, ε decay, target sync (M2.11). Goodput, Jain's quantity, utilisation, slack and expected-wait formulas are not fixed in the docs, so those entries point to the task that fixes them. The Deep-Dive Guide is not in the repo, so guide pointers use only part letters the repo's own docs name.
Blockers: configs/sim.yaml is stale against ADR-010/014: `r_drop` comment says "charged to the last holder" and `kv_penalty_per_step: -1` is the per-step KV penalty that ADR-014 replaced with w_kv. Not changed here (outside this task); needs a config fix. No docs/viva.md entry was written for this task because it was not in the task's file list and has no phase-plans ID; the glossary rule applies from the next task.
Next: Arnav reviews docs/glossary.md and fills guide part letters when the guide is next opened; then continues M0.1/M0.2.

## 2026-10-03 — Plan fixes: external review gaps (interference, headroom gate, framing, errata)
Done: docs/decisions.md: ADR-015 "Interference model in the simulator", status proposed, What/Why, options A (t_step and a × (1 + s_class × n_other_busy/(N−1))), B (fixed multiplier when any other server is busy), C (no term, report as sim-to-real limitation). phase-plans.md (no renumbering): M0.5.2 also measures slowdown with 0..N−1 other servers busy; new M0.5.4.1 (ADR-015 accepted before M1.7); M1.30 gains (iv) headroom check (SED-global vs SED-local k=full and k=0 vs Random at ρ = 0.8 and 0.95, 5 seeds, CIs) with the ADR-before-M2 condition; M5.3 limitations add shared-chip contention, decentralisation as a design choice and synthetic prices; M0.5.6 labels class prices "synthetic price per busy second (rough real GPU price ratios)". context.md Positioning: framing line; header: Deep-Dive Guide v2 (2026-10-03) link as source of truth for concepts (ADR wins on conflict). guide-errata.md: top line "Superseded by Deep-Dive Guide v2 (2026-10-03), which folds in every item below; kept for history." (the earlier §0 errata line from the first draft of this brief was dropped, since v2 supersedes the file).
Learned: ADR-003 promised an interference parameter that no formula used; a fitted parameter needs a place in the service-time model before it is measured.
Blockers: ADR-015 is undecided, so M1.7/M1.8 cannot start until M0.5.4.1. No docs/viva.md or glossary entry was added (docs-only plan fix with no new task ID needing a check; "interference" is already a project term). The M1.30 (iv) 0.95 point may sit above λ_sat for some policies; check against ADR-011 when M1.26–M1.28 are done.
Next: M0.2.

## 2026-10-03 — M0.2: trace loaders (canonical schema)
Done: src/marl_lb/data/traces.py (load_azure_2023, load_burstgpt, both with drop_failures=False, df.attrs["n_failures"], validation with file-naming ValueError, explicit dtypes and usecols; sample_stream stub raising NotImplementedError for M0.6). tests/test_traces.py and three fixtures in tests/fixtures/ (Azure, BurstGPT_1-style, BurstGPT_3-style). docs/viva.md M0.2 entry, glossary (arrival_s, canonical schema, failure row, nullable string; stale sample_stream signature fixed), architecture.md data.traces signatures. Verified by Arnav's pasted output: pytest tests/test_traces.py 22 passed (first run had 2 failures, both a wrong expected value in my tests: ".68" vs ".6805900" is 1.99941 s, not 2.0; the loader was right); ruff check clean after wrapping one over-long docstring line and one ruff-format fix. Smoke on the 4 real files: rows and first/last arrival_s match MANIFEST.json for all four; failure rows: Azure conv 0, Azure code 0, BurstGPT_1 25443, BurstGPT_3 387963 (about 1.8% and 7.3% of rows; derived from the smoke output, not yet recorded under results/); BurstGPT_3 non-null session_id 233617 (matches manifest); BurstGPT_3 loads in 0.89 GB. M0.2 ticked in phase-plans.md.
Learned: <Arnav>
Blockers: Choices to confirm: "Total tokens" is dropped (it is Request + Response); Model and Log Type are read as category dtype for memory. Final ruff check/format re-run after the last fix not yet pasted.
Next: Arnav fills the viva bet/outcome (viva.md M0.2) and "Learned", re-runs ruff, commits; then M0.3 (Tier A trace EDA notebook, deciding what to do with the failure rows).

## 2026-10-04 — M0.3 (in progress): trace EDA notebook, chunks 1–8 of 21 (started 2026-10-03)
Done:
- Tier B, before chunk 1: ADR-016 (trace for training and held-out) and ADR-017 (BurstGPT failure rows) appended to docs/decisions.md, status proposed, Decision sections left empty for Arnav. phase-plans.md: M0.3 done-when now "notebook runs top to bottom; findings recorded by Arnav in ADR-009, ADR-016 and ADR-017 in his own words; results/eda/trace_summary.json written", with a note in the header plan-change log (no IDs renumbered). context.md Request bullet: "(trace choice: ADR-016)" added.
- Process: RULES.md gained rule 15 (every chunk opens with what we are doing and why; beginner-simple code; Arnav's variable names) and rule 16 (intuition test: predict before running, compare after, ungraded).
- Plan: 21 chunks (load; Azure columns; rows and duration; arrival rate; per-minute counts; per hour and day for BurstGPT; inter-arrival gaps and ties; c_a; dispersion of counts; window and non-stationarity; P/O percentiles, histograms, Spearman; failure rows; sessions; history inclusion; held-out size; summary JSON).
- Arnav typed chunks 1–8 in notebooks/01_trace_eda.ipynb (looped version with a `traces` dict). Cells were moved by Claude to the right headings at Arnav's request: Azure columns now under (h), rows and duration under (a), arrival rate under (b). Still to tidy by Arnav: the stale "# TODO" line in the loader cell, spacing, and the pathlib import into the imports cell.
- Numbers Arnav pasted:
  - Rows / failure rows: azure_conv 19,366 / 0; azure_code 8,819 / 0; burstgpt_1 1,429,737 / 25,443; burstgpt_3 5,344,021 / 387,963.
  - Azure raw columns, both files: TIMESTAMP, ContextTokens, GeneratedTokens.
  - Duration (s, hours, days): azure_conv 3502, 0.97; azure_code 3436, 0.95; burstgpt_1 5,269,968, 61.0 days; burstgpt_3 9,503,873, 110.0 days.
  - Mean req/s: azure_conv 5.53; azure_code 2.567; burstgpt_1 0.271; burstgpt_3 0.562.
  - Gaps (zero gaps share; smallest non-zero gap; mean / median gap; largest gap): azure_conv 0; 2e-06 s; 0.181 / 0.118; 4.31 s. azure_code 0; 6e-06 s; 0.39 / 0.064; 217.17 s (row 8100). burstgpt_1 0.4563; 1.0 s; 3.686 / 1.0; 15,240 s (row 1,176,664). burstgpt_3 0.6833; 1.0 s; 1.778 / 0.0; 18,872 s (row 2,182,742).
  - Rows around the two BurstGPT gaps: arrival_s 4,507,654 then 4,522,894 (burstgpt_1) and 3,294,165 then 3,313,037 (burstgpt_3); tokens non-zero on both sides, neighbouring gaps 7 to 92 s.
  - c_a raw / after tie fix (random jitter in [0,1), seed 0): azure_conv 1.094 / 1.094; azure_code 13.151 / 13.151; burstgpt_1 13.282 / 13.282; burstgpt_3 17.75 / 17.75. Tie diagnostic: zero gaps 652,442 → 0 (burstgpt_1) and 3,651,379 → 0 (burstgpt_3); gap std 48.9573 → 48.9563 and 31.5661 → 31.5625.
- Arnav's readings (his words, from the plots; not yet in a results/ file): BurstGPT_1 and _3 show similar daily patterns, with a quiet stretch around hours 4–10 since trace start (a bit busier in _3); a slow rise then decay, peak around day 10 (_1) and day 20 (_3), a small peak near the end, random day-to-day swings; azure_code has the widest per-minute spread. The per-minute min/mean/max lines and the plots were not pasted.
- Concepts discussed (no files): why a random k-fold split leaks for time-ordered traffic, and the alternatives (chronological split, embargo gap, walk-forward folds, group split by session, whole-cycle hold-out); the tie-fix assumption (arrivals uniform within a second).
Learned: <Arnav>
Blockers: M0.3 is not ticked (RULES.md #10): chunks 9–21 are open, ADR-009/016/017 findings are not written, results/eda/trace_summary.json does not exist. The nature of the two 4–5 hour BurstGPT gaps (quiet lull vs logging outage) is not confirmed. The M0.3a viva entry, glossary terms (c_a, index of dispersion, heavy tail, percentile, Spearman, history inclusion, non-stationarity) and the final M0.3 log entry come after the last chunk.
Next: chunk 9 (index of dispersion of counts at 1 s, 10 s, 60 s, plus 1 h for BurstGPT), then chunk 10 (why c_a and dispersion depend on the window and on non-stationarity, Guide B5 / Kingman). Arnav also tidies the loader cell and writes his markdown notes under (b).

## 2026-10-20 — M0.3: rule exception, notebook cells 9–21 written by Claude
Done: At Arnav's explicit instruction (time pressure before the 2026-10-27 deadline) RULES.md #3 got a temporary exception: Claude writes the remaining analysis cells of notebooks/01_trace_eda.ipynb, with explanatory comments; scope is that notebook only; rules 15 and 16 suspended for those cells; the understanding work (viva.md M0.3a self-check, ADR-009/016/017 findings in his own words) is deferred, not dropped. docs/architecture.md ownership row notes the exception. Notebook cells written, not yet run (Claude does not run code): corrected c_a cell (the typed version computed ca_fixed from the old `gap` variable and tested a stale `gaps`, so "fixed" always equalled "raw"; the tie diagnostic cell is correct and showed the fix changes the std by 0.002% and 0.011%); index of dispersion at 1/10/60 s (+1 h for BurstGPT); whole-trace vs per-slice IDC plus a markdown note on window dependence and Kingman; P/O percentile table and log-scale histograms with the p99 line; Spearman P–O; new section (k) BurstGPT failure rows (count and share, prompt tokens of failure rows, share per day, by Model / Log Type); Session ID coverage; history-inclusion test; session length, turn gaps and duration; time-split sizes (80/20 by duration); summary cell writing results/eda/trace_summary.json.
Learned: <Arnav>
Blockers: None of the new cells has been run, so there are no new numbers to record. M0.3 is not ticked: Arnav must confirm the notebook runs top to bottom, results/eda/trace_summary.json exists, and ADR-009/016/017 findings are written (his words).
Next: Arnav runs Kernel → Restart and Run All, pastes any error or the printed output, and writes the ADR findings; M0.3a viva entry, glossary terms and the final M0.3 log entry follow once the notebook has run.

## 2026-10-20 — M0.3: notebook ran; rule 3 widened; trace_summary.json checked
Done: Arnav ran the notebook; results/eda/trace_summary.json exists (checked field by field against the chunk-21 spec: rows, duration, mean rate, c_a, IDC per window with 3600 s for BurstGPT only, P/O p50/p90/p95/p99/max, failure rows and share, sessions block for burstgpt_3 only; values match the numbers Arnav pasted earlier). Arnav then asked to remove his own coding role entirely: RULES.md #3 now says Claude writes all code with explanatory comments (#4 and #5 reworded, #15 and #16 suspended), and CLAUDE.md has a 2026-10-20 override section at the top. Viva self-checks, rewrite-from-memory tasks and ADR findings in his own words are deferred, not dropped.
Learned: <Arnav>
Blockers: M0.3 not ticked until Arnav confirms the notebook ran top to bottom without errors and the ADR-009/016/017 findings are filled. The printed notebook output (history-inclusion diff quantiles, failure-row prompt tokens, Spearman, held-out sizes) has not been pasted, so those findings are not recorded.
Next: Arnav pastes the printed output of the (k), (f), (d) and (i) cells; Claude drafts the ADR-009/016/017 findings from it for Arnav to approve, then M0.3a viva entry and glossary terms; then M0.3.1 and M0.4.

## 2026-10-20 — M0.3 closed: notebook outputs read, ADR findings drafted
Done: Read the saved outputs of notebooks/01_trace_eda.ipynb and results/eda/trace_summary.json (no new run). Key numbers (all from those two files): c_a fixed vs raw: burstgpt_1 13.2818 vs 13.2821, burstgpt_3 17.7476 vs 17.7496 (tie fix negligible; the earlier identical values were a bug in the typed cell, now fixed). IDC whole trace vs per-slice median (10 s counts): azure_conv 3.41 vs 2.12, azure_code 72.61 vs 67.57, burstgpt_1 24.76 vs 1.06, burstgpt_3 44.35 vs 1.06. Spearman P–O: 0.073, −0.021, 0.429 (0.398 without failures), 0.213 (0.012 without). Failure rows have P == 0 (99.94% in BurstGPT_1, 100% in BurstGPT_3), so they carry no prefill load. Sessions (BurstGPT_3): 233,617 rows with a Session ID (4.37%), all of them Conversation-log rows; 55,920 sessions; history inclusion in 58.7% of 177,697 tested turns. 80/20 time split: held-out 2,871 / 751 requests (Azure conv / code, about 11.6 min), 309,402 / 1,094,489 (BurstGPT_1 / _3). Written: ADR-009, ADR-016 and ADR-017 Findings plus a suggested decision each (status still proposed; Arnav accepts or changes); ADR-009 got What/Why lines; docs/viva.md M0.3a entry; six glossary terms (heavy tail, history inclusion, index of dispersion of counts, non-stationarity, percentile, Spearman correlation; c_a already existed); M0.3 ticked in phase-plans.md at Arnav's request (notebook ran, JSON written, findings recorded; drafted by Claude under the 2026-10-20 rule change).
Learned: <Arnav>
Blockers: ADR-009, ADR-016 and ADR-017 decisions are not taken, M0.4 depends on ADR-016 and ADR-017. One reading from the plots (BurstGPT_1 and _3 last 20% quieter than the start) is only true relative to the mid-trace peak: the mean rate of the held-out part is above the training part's mean (0.294 vs 0.266 and 0.576 vs 0.559 req/s). M0.3a self-check is Arnav's, not done. The loader cell still has its stale TODO comment.
Next: Arnav accepts or edits the three suggested decisions (or says "accept all suggestions"), then M0.3.1 (tests for normalisation and split) and M0.4 (data/processed.py).

## 2026-10-20 — M0 close: mode change, ADR-009/016/017 accepted, M0.3.1 tests, M0.4 code, M0.4a viva (NOT RUN)
Done:
- Mode change: RULES.md #1, #2, #3, #4, #10 and CLAUDE.md rewritten (Claude Code runs commands, commits and pushes each task once tests pass; teaching mode only on request); ownership notes in context.md and architecture.md, ADR-006 and phase-plans.md headers and break-it lines updated; ADR-008 got "Amended 2026-10-20: Claude Code writes viva entries; Arnav's self-check is optional." and the `a`-task done-when wording follows it. Kept: never invent numbers, ADR for state/actions/reward/metrics/experiments, tick only when done-when is met. Kept as safety limits in #2: no git config edits, no force-push, no history rewrite.
- ADR-017 accepted (drop failure rows; Why rewritten, prefill-load premise withdrawn). ADR-016 accepted (Azure conv for train and held-out; E5 burst test on Azure code; limitations and open points stated). ADR-009 accepted, Option B (parameters in new configs/sessions.yaml, think-time gaps not compressed, limitation stated). E5 references updated in context.md, phase-plans.md (M4.10, M1.30), numbers.md, glossary.md, configs/sim.yaml, configs/experiments/load_generalization.yaml. Stale TODO line removed from notebook cell c02 (outputs of that one cell may be cleared when the notebook is next opened; nothing else in the notebook changed).
- M0.3.1: tests/test_processed.py written (constants = percentile per feature, clipping, time-ordered split with no overlap and both sizes, same-instant ties, failure rows excluded, train-only constants, files written).
- M0.4: src/marl_lb/data/processed.py (time_split, fit_normalisation, normalise, build_processed, CLI), `processed` block in configs/data.yaml (train_fraction 0.8, percentile 99, features prompt_tokens/output_tokens), architecture.md data.processed signatures, glossary terms (data leakage, synthetic sessions; failure row and train/held-out split entries refreshed).
- M0.4a: docs/viva.md entry (3 questions). M0.3a ticked as well: its done-when (entry written) was already met under the amended ADR-008.
Not done, and why: **Bash is disabled in this session, so nothing was executed.** No pytest, ruff, `python -m marl_lb.data.processed`, git commit or push was run. Consequently: no test output (the "failing before the code exists" check for M0.3.1 was not observed), data/processed/normalisation.json, train.csv, heldout.csv and split.json do not exist, there are no constants or split sizes to report (the sizes in ADR-016, 16,495 / 2,871, come from the notebook run, not from processed.py), and M0.3.1 and M0.4 are NOT ticked (RULES.md #10). Nothing is committed.
Learned: ADR-016's split sizes come from `cut = 0.8 × t.max()` in the notebook; time_split uses t_min + f × (t_max − t_min), identical when t_min = 0 (Azure), so the run should reproduce 16,495 / 2,871 — to be confirmed, not assumed.
Blockers: a session with shell access to run `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run python -m marl_lb.data.processed`, then commit and push as three commits.
Next: run the checks above; fix whatever fails; tick M0.3.1 and M0.4; record the actual constants and sizes in this log; then stop (M0.6 not started).

## 2026-10-20 — M0.3.1 and M0.4: checks run by Arnav, ticked
Done: Arnav ran the checks and pasted the output. `uv run pytest -q`: all tests passed (36 dots, no failures; the full suite including tests/test_traces.py). `uv run ruff check .`: one error, E501 line too long (101 > 100) at tests/test_processed.py:151; Arnav chose to leave it for now (deadline priority), so ruff check is NOT clean and `ruff format --check` did not run after it. `uv run python -m marl_lb.data.processed` printed: source AzureLLMInferenceTrace_conv, train_fraction 0.8, cutoff_s 2801.3775496, n_train 16,495, n_heldout 2,871, n_failures_dropped 0, constants prompt_tokens 4143.0 and output_tokens 598.0 (fitted on the train part only). The sizes match the ADR-016 notebook figures. Files written to data/processed/ (gitignored): normalisation.json, train.csv, heldout.csv, split.json. M0.3.1 and M0.4 ticked (done-when: tests pass); the "failing before the code existed" check for M0.3.1 was never observed.
Learned: the train-only p99 of prompt tokens (4143.0) is close to the whole-trace p99 in trace_summary.json (4142.0); output p99 is 598.0 against 601.0 whole-trace.
Blockers: the E501 lint error (acceptance criterion "ruff check clean" not met); fix is wrapping the comment on tests/test_processed.py line 151.
Next: commit and push; then M0.6 (not started).
