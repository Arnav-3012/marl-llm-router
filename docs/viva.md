# Viva log

Interview-readiness record (ADR-008). Everything in the Log, Revisit and Break-it sections is in Arnav's own words.

## How to use
1. After each task, Claude Code asks 3 interview-style questions on what was just built:
   - Q1 explain: "walk me through how X works and why it is there"
   - Q2 break-it: "what if we removed X? what would you see in the metrics?"
   - Q3 justify: "why X rather than Y? what is the trade-off?"
2. Arnav answers in his own words, in the Log below, BEFORE seeing any answer. No notes, no looking at the code.
3. Claude grades each answer: correct / partly / wrong. For "partly" and "wrong" it names the missing piece as a hint, not a lecture.
4. Anything graded "wrong" is added to Revisit and re-asked at the start of the next session.
5. Break-it experiments (M2, M3) are logged in the Break-it log: the hypothesis is written BEFORE the run.
6. Numbers quoted in answers come only from docs/numbers.md (which comes only from results/).

## Log

Template (copy one block per task, newest at the bottom):

```
### <YYYY-MM-DD> — <task ID> — <task name>
Q1 (explain): <question>
- Arnav's answer: <own words>
- Grade: correct | partly | wrong
- Missing piece: <hint, or "none">

Q2 (break-it): <question>
- Arnav's answer:
- Grade:
- Missing piece:

Q3 (justify): <question>
- Arnav's answer:
- Grade:
- Missing piece:
```

### EXAMPLE (format illustration only, not a real graded answer) — S.1 — Repo scaffold
Q1 (explain): What do Tier A and Tier B mean in this repo, and which files fall in each?
- Arnav's answer: Tier A is the core logic (simulator, agents, training loop, heuristics, stats). I type it myself while Claude teaches. Tier B is glue like configs, tests, scripts, docs and the demo, which Claude may write.
- Grade: correct
- Missing piece: none

Q2 (break-it): What if Claude wrote the Tier A files for you to review?
- Arnav's answer: It would be faster, but I would not be able to explain or debug them in the viva.
- Grade: partly
- Missing piece: Name the concrete failure: you could not answer "what if we removed X?" because you never made the decisions inside the code.

Q3 (justify): Why are the tests (Tier B) written before the Tier A module they cover?
- Arnav's answer: _(example left blank)_
- Grade: _(n/a)_
- Missing piece: _(n/a)_

## Revisit
Questions graded "wrong". Re-ask at the start of the next session; move a line to "cleared" once answered correctly.

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
