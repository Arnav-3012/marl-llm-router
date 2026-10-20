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

## M0.3a Trace EDA [A] 2026-10-20
Prerequisite: docs/glossary.md → Queueing → "inter-arrival CV (c_a)" and Data and traces → "index of dispersion of counts", "non-stationarity", "heavy tail"; results/eda/trace_summary.json; docs/decisions.md ADR-009, ADR-016, ADR-017; Deep-Dive Guide B5.

Bet (Arnav): BurstGPT arrivals are bursty in the short term, not only over the day: _______
Outcome (after): _______ ✔/✘

Q1 (explain): The whole-trace c_a of BurstGPT_1 is 13.3, yet inside one-hour slices the index of dispersion of 10 s counts has a median of 1.06. What do these two numbers say together about the traffic, and which one would you hand to the router designer?
Arnav:   Self-check: got it / partly / missed

<details><summary>Answer</summary>

Inside an hour the arrivals are close to random (IDC ≈ 1, like Poisson), so the large c_a does not come from short-term clumping. It comes from the rate changing between hours (hourly mean rates range from 0.002 to 0.767 req/s between the 10th and 90th percentile of slices) and from hours-long gaps: that is non-stationarity inflating the whole-trace statistic. For queueing waits, burstiness at the time scale of seconds to minutes matters (Kingman: wait grows with c_a²), so the router designer gets the short-window numbers plus the rate profile, not the single c_a.

Source: results/eda/trace_summary.json (c_a, idc_by_window_s); per-slice IDC from the printed output of notebooks/01_trace_eda.ipynb cell "IDC whole trace vs per slice"; Guide B5.

</details>

Q2 (break-it): You split BurstGPT_3 into train and held-out by shuffling requests at random (80/20). Name two separate ways the held-out score would be too optimistic.
Arnav:   Self-check: got it / partly / missed

<details><summary>Answer</summary>

(1) Time leakage: neighbouring requests of the same burst or hour fall on both sides, so the policy is tested on traffic it has effectively seen. (2) Session leakage: turns of one conversation (55,920 sessions, median gap between turns 131 s) are split, so earlier turns are in training and later turns in held-out, and the prefix-cache behaviour is evaluated on history the held-out stream does not contain. Both show up as a better score than a forward-in-time test. A time-ordered split with an embargo gap, or a split by session, avoids them (ADR-016).

Source: notebook cells (g), (i); docs/decisions.md ADR-016; docs/phase-plans.md M0.3.1.

</details>

Q3 (justify): ADR-017 considers keeping BurstGPT failure rows as "prefill-only" requests. What does the data say about that, and what does keeping them do to the statistics you compute?
Arnav:   Self-check: got it / partly / missed

<details><summary>Answer</summary>

The failure rows have prompt_tokens = 0 in 99.94% (BurstGPT_1) and 100% (BurstGPT_3) of cases, and carry about 0% of all prompt tokens, so they consume neither prefill nor decode: the "prefill-only" premise does not hold. Keeping them puts a spike of zeros in the output-length distribution (it lowers every O percentile) and creates a fake P–O correlation (Spearman 0.213 with them, 0.012 without in BurstGPT_3). They only thin the arrival count by 1.78% and 7.26%.

Source: printed output of notebooks/01_trace_eda.ipynb cells (k) and (d); results/eda/trace_summary.json (failure_rows, failure_share); docs/decisions.md ADR-017.

</details>

## M0.4a Normalisation and time-ordered split [A] 2026-10-20
Prerequisite: docs/decisions.md ADR-016 (split) and ADR-017 (failure rows); docs/glossary.md → Data and traces → "normalisation constants", "percentile", "heavy tail", "data leakage", "train/held-out split"; src/marl_lb/data/processed.py; tests/test_processed.py.

Bet (Arnav, before): the 99th-percentile prompt length of Azure conv, fitted on the first 80% of the hour, will be (higher / lower / about the same) as the whole-trace p99 of 4,142 tokens in trace_summary.json: _______
Outcome (after, from data/processed/normalisation.json after `uv run python -m marl_lb.data.processed`): _______ ✔/✘

Q1 (explain): Why are the normalisation constants fitted on the train part only, and what would go wrong if they were fitted on the whole trace?
Arnav:   Self-check: got it / partly / missed

<details><summary>Answer</summary>

The held-out part plays the role of traffic the agent has never seen. If its requests help set the scale, the training setup already contains information about the test traffic: a held-out burst of very long prompts would raise the 99th percentile, change every normalised input, and the test score would no longer come from a setup fixed before the test. This is data leakage. With train-only constants the same numbers are applied unchanged to the held-out part, which may then exceed the train p99 and is clipped to 1, exactly what a deployed router would meet. The constants are fitted once, written to normalisation.json, and only read afterwards.

Source: src/marl_lb/data/processed.py (`build_processed`: constants from `split.train`); tests/test_processed.py `test_constants_use_the_train_part_only`; docs/decisions.md ADR-016.

</details>

Q2 (break-it): You replace the 99th percentile by the maximum as the scale for prompt tokens. What happens to the typical request's normalised prompt size, and why is that a problem for the Q-network?

Arnav:   Self-check: got it / partly / missed

<details><summary>Answer</summary>

Prompt lengths are heavy-tailed: in the whole-trace summary the Azure conv p50 is 1,020 tokens, p99 is 4,142 and the maximum is 14,050. Dividing by the maximum puts the median request at about 0.07 instead of about 0.25 (computed from those three numbers, whole trace, not train-only), so most requests occupy a thin band near 0 and one outlier decides the scale. The network then sees almost no difference between a small and a medium prompt, and learning is slower and more fragile. The 99th percentile keeps the bulk spread over [0, 1] and clips the rare huge prompts to 1, which loses their exact size but not the fact that they are large.

Source: results/eda/trace_summary.json (azure_conv prompt_tokens p50, p99, max); src/marl_lb/data/processed.py `normalise` (clip to [0, 1]); tests/test_processed.py `test_normalise_scales_by_constant_and_clips_to_unit_interval`.

</details>

Q3 (justify): The split cuts at 80% of the trace's duration with a strict `arrival < cutoff` rule, instead of taking the first 80% of the rows. Why, and what does it cost?

Arnav:   Self-check: got it / partly / missed

<details><summary>Answer</summary>

A time threshold keeps train and held-out disjoint by construction and keeps requests with identical timestamps together, so no burst is cut in half; a row count could cut between two requests of the same instant. Cutting by duration also matches how ADR-016 reports the sizes (16,495 train and 2,871 held-out requests, 11.7 min held-out), and time order means the held-out part is strictly later than everything in training, with no shuffling. The cost: the parts differ in rate (5.89 against 4.10 req/s in ADR-016) and the held-out part is small and comes from one hour of one day; ADR-016 states this as a limitation, and the sampler (M0.6) sets the arrival rate itself, so the rate difference does not carry into experiments.

Source: src/marl_lb/data/processed.py `time_split`; tests/test_processed.py `test_split_cuts_at_the_fraction_of_the_duration_and_reports_both_sizes`, `test_requests_arriving_at_the_same_instant_stay_on_one_side_of_the_cut`; docs/decisions.md ADR-016.

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
