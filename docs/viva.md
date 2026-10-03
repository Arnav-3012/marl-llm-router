# Viva log

Per-step Q&A reference (ADR-008, amended 2026-10-03). Claude Code writes each entry at the start of a task: prerequisite, bet prompt, questions and collapsed reference answers. Arnav writes the bets, his attempts and the self-checks in his own words. This file is the end-of-project and interview reference.

## How to use this file
1. Do the Prerequisite reading first (file and section locations are listed in each entry).
2. Write your Bet before looking at the data or the code. Fill in the Outcome after the task.
3. Attempt each question in the "Arnav:" line BEFORE expanding the answer. No notes, no looking at the code.
4. Expand the answer and mark yourself: got it / partly / missed.
5. Anything not "got it" goes to Revisit below and is re-asked at the start of the next session.
6. Break-it experiments (M2, M3) are logged in the Break-it log: the hypothesis is written BEFORE the run.
7. Numbers in answers come only from results/ files or cited sources; see docs/numbers.md.

Rules per entry: Tier B task = prerequisite + bet + 1 question (explain or justify). Tier A task = prerequisite + bet + 3 questions (explain, break-it, justify). Every answer is 3–6 lines and ends with its source.

## Entry template

```
## <task ID> <title> [Tier] <date>
Prerequisite: ... (file and section locations)
Bet (Arnav, before): ...   Outcome (after): ... ✔/✘
Q1 (explain|justify): ...
Arnav: ...   Self-check: got it / partly / missed
<details><summary>Answer</summary> ... Source: ... </details>
Q2 (break-it), Q3 (justify): Tier A only, same pattern.
```

## Log

## M0.1 Data download [B] 2026-10-03
Prerequisite: docs/context.md → Environment → the "Request:" and "conversation id:" bullets; docs/decisions.md ADR-009; Deep-Dive Guide Part B1.

Bet 1 (Arnav, before): the time span of the Azure 2023 trace (minutes, hours or days): _______
Outcome (after): _______ ✔/✘

Bet 2 (Arnav, before): the fraction of BurstGPT_3 rows that have a Session ID: _______
Outcome (after): _______ ✔/✘

Q1 (justify): Why does this project need BurstGPT_3 rather than the BurstGPT_1.csv in the repo's /data folder?
Arnav:   Self-check: got it / partly / missed

<details><summary>Answer</summary>

Session ID exists only in BurstGPT_3 (the v2.0 release), and only for conversation-mode rows; API-mode rows have none. Azure 2023 and BurstGPT_1 carry no conversation id at all. The prefix cache, the cache-aware baseline and the prefix-hit observation feature all need a conversation id so that a follow-up turn can be matched to a server holding its cached prefix (ADR-009).

Source: BurstGPT README and v2.0 release notes; docs/decisions.md ADR-009.

</details>

## M0.2 Trace loaders [B] 2026-10-03
Prerequisite: docs/architecture.md → Public interfaces → data.traces; docs/glossary.md → Data and traces → "failure row" and "canonical schema"; data/README.md.

Bet (Arnav, before): what share of rows have output_tokens == 0 in Azure conv 2023, and in BurstGPT_3 (higher, lower or similar to Azure)? _______
Outcome (after, from the smoke command's n_failures): _______ ✔/✘

Q1 (justify): The loaders keep failure rows (output_tokens == 0) by default and only report the count; dropping is decided in M0.3. Why not drop them inside the loader, and what could go wrong downstream if they were kept without anyone noticing?
Arnav:   Self-check: got it / partly / missed

<details><summary>Answer</summary>

Whether to drop them is an analysis decision, not a parsing one, so it belongs after the EDA (M0.3) and in one visible place. If the loader dropped them silently, the arrival process would lose requests that really reached the service, so the arrival rate and burstiness would be understated; the loader's job is to reproduce the file faithfully and make the choice explicit (`drop_failures`, with `df.attrs["n_failures"]` always reported). If they are kept unnoticed, a request with 0 output tokens has no decode phase, so it distorts the output-length distribution (a spike at 0), the 99th-percentile normalisation constant and mean service time. arrival_s also stays relative to the file's first request after dropping, so the time axis is the same either way.

Source: M0.2 task brief; src/marl_lb/data/traces.py `_finalise`; the share itself comes from the smoke command, not from this answer.

</details>

## Revisit
Questions marked partly or missed. Re-ask at the start of the next session; move a line to "cleared" once you get it.

| Date asked | Task ID | Question | Missing piece | Re-asked on | Status |
|---|---|---|---|---|---|
| | | | | | open |

## Break-it log
Rule: write the hypothesis in this file BEFORE running the experiment. Evaluate with ε = 0, held-out traffic, ≥ 5 seeds, mean ± 95% CI. Never edit a hypothesis after the run.

Template:

```
### <YYYY-MM-DD> — <experiment ID, e.g. M2.12 no target network>
Hypothesis (written before running): <what I expect to see in which metric, and why>
What actually happened: <observations, numbers only from results/>
Explanation: <why, in my own words>
Config used: <path to configs/ file or resolved config copied into the run>
Results path: results/<exp>/<timestamp>_seed<k>/
Hypothesis correct? yes | partly | no
```
