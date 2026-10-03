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
