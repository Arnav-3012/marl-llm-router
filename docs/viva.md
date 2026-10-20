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

## M0.6a Arrival-rate rescaling and the seeded stream [B] 2026-10-20
Prerequisite: docs/decisions.md ADR-009 (think time is not compressed) and ADR-018 (sampler); docs/glossary.md → Data and traces → "arrival-rate rescaling", "think time", "stream sampler"; src/marl_lb/data/traces.py `sample_stream`; tests/test_sampler.py.

Bet (Arnav, before): on the held-out Azure part, the share of requests that are follow-up turns at 20 req/s will be (higher / lower / about the same) as at 2 req/s: _______
Outcome (after, printed by sample_stream on the real held-out part, seed 0; logged in docs/logs.md 2026-10-20): 51.3% at 2 req/s and 29.2% at 20 req/s, so lower ✔/✘ _______

Q1 (explain): The sampler multiplies every inter-arrival gap by one factor to reach a target rate, but leaves the think-time gaps between turns of a conversation alone. Why one factor for arrivals, why not for think times, and what does that do to the share of follow-up turns as the rate goes up?
Arnav:   Self-check: got it / partly / missed

<details><summary>Answer</summary>

One factor keeps every ratio between gaps, so a burst stays a burst and a lull stays a lull; only the clock speed changes, which is the property that makes the Azure trace worth replaying (tests/test_sampler.py checks that the gaps at 1 and 8 req/s differ by exactly 8). Think time is how long a person reads before replying: it does not get shorter because the cluster is busier, so ADR-009 keeps it in simulated seconds. Consequence: when the rate rises the whole stream gets shorter (the held-out part lasts 143.5 s at 20 req/s) while a median gap is still 131 s, so more conversations are cut by the end of the stream and fewer requests are follow-up turns. That leaves the prefix cache with less to reuse at high load, which is why the report must state the follow-up share next to any cache result.

Source: src/marl_lb/data/traces.py `sample_stream`, `session_plan`; tests/test_sampler.py `test_rescaling_keeps_the_relative_burst_structure`, `test_think_time_gaps_are_not_compressed_by_rescaling`; docs/decisions.md ADR-009, ADR-018 (follow-up shares 51.3%, 41.2%, 29.2% at 2, 5, 20 req/s, held-out, from the run output).

</details>

## M0.5.0 Learning gate L1: profiling prerequisites (Guide Parts A–B) [B] 2026-10-20
Prerequisite: Deep-Dive Guide v2 Part A (A4 prefill vs decode, A5 continuous batching, A6 prefix caching, A7 the service-time model) and Part B (B2 utilisation, B3 Little's law); the profiling protocol H1 and the fitting notes H2/H6 are what M0.5.2 and M0.5.4 implement. docs/glossary.md → LLM serving → "prefill", "decode", "TTFT", "TPOT", "interference".

Bet (Arnav, before): on one Mac server, if you double the prompt length from 1,000 to 2,000 tokens, TTFT will (less than double / about double / more than double): _______
Outcome (after, from the M0.5.2 CSVs and the M0.5.4 fit): _______ ✔/✘

Q1 (explain): Why is TTFT roughly a straight line in prompt length P with slope a, while TPOT stays nearly flat and rises with batch size B? Name what limits each phase.
Arnav:   Self-check: got it / partly / missed

<details><summary>Answer</summary>

Prefill pushes all P prompt tokens through the model in one parallel pass; the work is about 2 × parameters × P operations, mostly big matrix multiplies, so it is compute-bound and the time grows linearly with P (slope a, plus a fixed cost). Decode makes one token per step and each step has to read every weight from memory for very little arithmetic, so it is memory-bandwidth-bound; with B requests decoding together the weights are read once and shared, so a step costs t_step(B) = t_0 + k·B: t_0 is the weight read, k the extra attention work per request. The Guide's example: a 3B model at 4 bits is about 1.8 GB, and at roughly 273 GB/s one step takes at least about 6.6 ms (a ceiling near 150 tokens/s; real speed is lower; these are the Guide's approximate figures, not measurements). Batching raises total throughput but slows each user, which is why the router cares about goodput, not throughput.

Source: Deep-Dive Guide v2 A4, A5, A7, H1; docs/context.md Environment (service-time formula).

</details>

Q2 (break-it): You profile a server but forget to discard the first runs and you reuse the same prompt text for every repeat. Which two measurements are corrupted, in which direction, and how would you see it in the CSV?
Arnav:   Self-check: got it / partly / missed

<details><summary>Answer</summary>

(1) The first runs are slower than steady state (model weights and caches are still being loaded, the GPU clocks are not up), so the early rows inflate TTFT and TPOT; they show up as a few high outliers at the start of each point and a larger spread. (2) Reusing identical prompt text lets the server's prefix cache answer later repeats from stored KV, so prefill is skipped: TTFT looks far too small and nearly flat in P, which would make the fitted slope a too small. You would see repeat 1 high and repeats 2..N low at the same P. The fix is the protocol: discard warm-up runs, use fresh text per repeat for the cold measurements, and measure the cold-versus-warm cache effect deliberately as its own experiment.

Source: Deep-Dive Guide H1 (cold vs warm cache, repeats), A6; docs/glossary.md "warm-up".

</details>

Q3 (justify): Part H1 measures slowdown with 0, 1, ..., N−1 other servers busy instead of profiling each server alone. Why, and what would the simulator get wrong without it?
Arnav:   Self-check: got it / partly / missed

<details><summary>Answer</summary>

All the servers share one chip and one memory bandwidth, so a busy neighbour slows both prefill and decode. A server profiled alone gives the best case; the simulator would then predict latencies that no loaded cluster can reach, and every policy (including the learned one) would be tuned for a cluster that is faster than the real one, inflating goodput and hiding that spreading load across servers costs something. Measuring slowdown against the number of busy neighbours gives the data ADR-015 needs to choose how interference enters the equation (a multiplier growing with busy neighbours, a fixed multiplier, or no term, with the gap reported). It is also a stated limit: a real cluster would not share one chip.

Source: Deep-Dive Guide A7 (Interference), H1, H5; docs/decisions.md ADR-015; docs/context.md Positioning.

</details>

## M0.5.4a fit_calibration: least squares, R², residuals, interference [A] 2026-10-20
Prerequisite: Deep-Dive Guide H1, H2, H6 (profiling protocol, least-squares fit, residuals and standard errors); docs/glossary.md → "residual", "warm-up run", "interference"; docs/decisions.md ADR-015; profiling/fit_calibration.py; tests/test_fit_calibration.py.

Bet (Arnav, before): for the fast class, the fitted prefill slope a will be (smaller / similar / larger) than the slow class's, by a factor of about ______; and the slow class's TTFT against prompt length will (stay straight / curve up): _______
Outcome (after, from results/profiling/<run>/fit_output.json): _______ ✔/✘

Q1 (explain): The prefill fit is TTFT = a·P + c by least squares. What do a and c mean physically, what does R² say, and why is R² alone not enough to trust the line?
Arnav:   Self-check: got it / partly / missed

<details><summary>Answer</summary>

a is the seconds one more prompt token adds (prefill is one parallel pass whose cost grows with P); c is the fixed part of every request: HTTP and scheduling plus the one decode step that makes the first token, so c should be near t0 + k (the code prints that check). Least squares picks a and c to minimise the sum of squared gaps; the normal equations make the residuals perpendicular to the columns [P, 1]. R² is the share of TTFT variance the line explains. It can stay high when the shape is wrong: if attention cost grows with P², TTFT curves up, the line still scores a decent R², but its residuals are negative in the middle and positive at both ends. So the fit also adds a P² term and reports its t-value and its size against the line (`shape` in fit_output.json), plus the spread per prompt length.

Source: Deep-Dive Guide H2, H6 (points 2 and 3); profiling/fit_calibration.py `fit_prefill`; tests/test_fit_calibration.py `test_shape_check_flags_a_curve_and_passes_a_straight_line`.

</details>

Q2 (break-it): You fit t0 and k with every request row of a batch-of-8 run, instead of one step time per run. What goes wrong, and what does the test `test_decode_fit_counts_each_run_once_not_once_per_request` guard against?
Arnav:   Self-check: got it / partly / missed

<details><summary>Answer</summary>

bench_server writes the run-level step time on each request row, so a batch of 8 appears 8 times and a batch of 1 once: large batches are over-weighted 8:1 in the regression and the standard errors come out too small (the effective sample is the number of runs, not rows). The line is pulled towards the large-B points and the reported uncertainty is falsely tight. The test builds data with 4 batch sizes x 10 repeats and requires n_runs = 40, not 150, so rows must be collapsed to one value per (batch size, prompt length, repeat). A second guard: runs with no window where all requests decode (step time nan) are dropped, not filled.

Source: profiling/fit_calibration.py `fit_decode`; profiling/bench_server.py `all_active_step_time`; tests/test_fit_calibration.py (the two decode tests).

</details>

Q3 (justify): The interference fit expresses slowdown as s·n/(N−1) through the origin, but the code also prints the slowdown at each level and a fixed-multiplier summary. Why not just commit to the formula, and what decides between ADR-015 options A, B and C?
Arnav:   Self-check: got it / partly / missed

<details><summary>Answer</summary>

Option A (linear in the number of busy neighbours) is only one of three candidate models and ADR-015 is decided in M0.5.4.1 from the data, not before it. The per-level table shows the real shape: if the slowdown grows with n roughly in proportion, A fits (linear R² near 1); if it jumps at n = 1 and then stays flat, B (one fixed multiplier) is the honest model; if the slowdown is within the noise, C (no term, reported as a sim-to-real limit) is. The fit therefore reports s with its standard error, the linear R², and the per-level means with their uncertainty, and never writes calibration.json: that waits for the ADR. A through-the-origin line also assumes no slowdown at n = 0, which is true by construction because the baseline run is the n = 0 level.

Source: docs/decisions.md ADR-015; profiling/fit_calibration.py `fit_interference`; Deep-Dive Guide A7 (Interference), H1.

</details>

## M0.5.4.1 / M0.5.5 Prefill shape and the interference decision [B] 2026-10-20
Prerequisite: docs/glossary.md → "effective tokens", "interference"; docs/decisions.md ADR-015, ADR-022; results/profiling/20261020-173822_seed0_quick/plots/fit_*.png.

Bet (Arnav, before): the straight line TTFT = a·P + c will fit both classes well (yes / no), and the slowdown from busy neighbours will be (linear / a jump / curving up): _______
Outcome (after, from results/profiling/20261020-173822_seed0_quick/fit_output.json): _______ ✔/✘

Q1 (justify): The line fit gave R² = 0.99 on both classes, yet the simulator uses a·E + q·E² through the origin. Why was the line rejected, and why is the model fitted with weights 1/TTFT?
Arnav:   Self-check: got it / partly / missed

<details><summary>Answer</summary>

R² only says how much of the variance the line explains; the points are spread over 100 to 4000 tokens, so even a bent curve has a high R². The residuals say more: the line has a negative offset (−0.085 s fast, −2.83 s slow), which cannot be a real fixed cost, and TTFT per token rises with prompt length (slow class about 9.8 ms/token at 500 tokens, 15.8 at 4000), the signature of attention cost growing with P. The simulator has no per-request offset, so using the line's slope alone would misprice short and long prompts in opposite directions (about ±30% on the slow class). Weights 1/TTFT minimise relative error: most requests are short (median prompt 1,020 tokens), and an unweighted fit would be decided by the few 4,000-token points whose TTFTs are 20 to 50 times larger.

Source: docs/decisions.md ADR-022; profiling/fit_calibration.py `fit_prefill_model`; results/profiling/20261020-173822_seed0_quick/fit_output.json (prefill shape and prefill_model).

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
