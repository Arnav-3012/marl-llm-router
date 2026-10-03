# Deep-Dive Learning Guide: errata
Superseded by Deep-Dive Guide v2 (2026-10-03), which folds in every item below; kept for history.

Where the Deep-Dive Learning Guide is superseded by the ADRs. When the guide and an ADR disagree, the ADR applies.
One line each: guide section · what it says · what applies now · source ADR.
The guide itself is not in the repo; section references are taken from the S.8 task brief and should be checked against the guide when it is next opened.

- D1, D8, F1, H3 · 6 observation features · 7 features (adds the prefix-hit fraction; neighbour mean wait is 0 when k=0) · docs/architecture.md observation, ADR-002
- F2 · Forward goes to a random neighbour when k=0 · Forward is masked when k=0 (and at the hop limit); when legal, the environment picks the target SED-style (min expected wait + estimated service time) · ADR-013
- Reward section · per-step reward terms (λ·C, −β·B_t, −1 per step for KV > 80%) · per-decision transitions: cost per request at resolution to the serving agent, KV term per request, −β·B_t at each transition's decision tick · ADR-014
- Delayed credit · a delayed-credit scheme different from ADR-010 (wording to be checked against the guide) · s' = the agent's next decision observation, discount γ per decision, not per tick · ADR-010
- ρ definition · ρ = λ/Σμ from nominal service rates · ρ = λ_arr / λ_sat, λ_sat measured on global-form SED by completion ratio, drop rate and backlog growth · ADR-011
- Drops · a dropped request is "charged to the last agent" · −5 R_SLA credited once to every agent that acted on it, no extra charge; last holder kept only for per-server metrics · ADR-010 (refines ADR-004)
- F3 · SLA credit "to the agent that accepted" · R_SLA shared by every acting agent; cost and KV term paid by the serving agent only · ADR-010, ADR-014
- C2, F3 · cooperation signal "every step" · −β·B_t sampled once per transition at its decision tick · ADR-014
- G4 · degenerate policy "~100% Reject" · there is no Reject action; the warning sign is ~100% of any one action · ADR-013 (action set)
- H4 · scale arrivals to ρ via λ/Σμ · ρ = λ_arr / λ_sat · ADR-011
- Other conflicts: none recorded. The guide text was not available in this session, so no further guide-versus-ADR conflicts could be checked; add lines here as they are found (candidates to check: heuristics as full-state only vs ADR-012 local and global forms, agent timing vs ADR-013, entry rule vs ADR-013).
