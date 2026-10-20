"""The ADR-035 verdict and the plain-language sentences for the layout and live results. Tier B.

One place for the wording, so the dashboard section and the presentation prompt say the same thing
and every sentence is computed from a results file.
"""

from __future__ import annotations

RHOS = ["0.5", "0.8", "0.95"]


def layout_verdict(doc: dict) -> dict:
    """ADR-035 rule on a results/layout/<tag>.json document.

    a: the agents beat the UNCHANGED shed rule at some load (the old rule breaks).
    b: the agents are not worse than the REWRITTEN tuned rule at any load.
    """
    beats_old = [r for r in RHOS if doc["rhos"][r]["agents_minus"]["route_to_fast_shed"]["beats"]]
    loses_new = [
        r for r in RHOS if doc["rhos"][r]["agents_minus"]["route_to_fast_shed_tau"]["loses"]
    ]
    beats_new = [
        r for r in RHOS if doc["rhos"][r]["agents_minus"]["route_to_fast_shed_tau"]["beats"]
    ]
    a, b = bool(beats_old), not loses_new
    if a and b:
        head = (
            "Both conditions hold: the old hand rule breaks in this layout and the retrained "
            "agents are not worse than the rewritten, tuned rule."
        )
    elif b:
        head = (
            "The agents are not worse than the rewritten rule, but they did not beat the unchanged "
            "old rule at any load, so the old rule did not break here."
        )
    else:
        head = (
            "The rewritten, tuned rule is better than the retrained agents at load "
            + ", ".join(loses_new)
            + ": in this layout the hand rule wins."
        )
    return {
        "a": a,
        "b": b,
        "beats_old": beats_old,
        "loses_new": loses_new,
        "beats_new": beats_new,
        "head": head,
    }


def layout_sentence(doc: dict, training_minutes: float | None = None) -> str:
    """One paragraph for the presentation: numbers from the results file only."""
    v = layout_verdict(doc)
    r = doc["rhos"]["0.8"]
    g = {k: r["policies"][k]["goodput"][0] for k in r["policies"]}
    tau = doc.get("tau")
    effort = (
        "The agents needed no code change and one training run"
        + (f" of about {training_minutes:.0f} minutes" if training_minutes else "")
        + f"; the rule needed a new rule class and a tuning sweep (best tau {tau})."
    )
    return (
        f"One fast and three slow servers (load 0.8, goodput req/s): agents {g['agents']:.3f}, "
        f"rewritten tuned rule {g['route_to_fast_shed_tau']:.3f}, unchanged shed rule "
        f"{g['route_to_fast_shed']:.3f}, unchanged route-to-fast {g['route_to_fast']:.3f}, "
        f"SED global {g['sed_global']:.3f}. {v['head']} {effort}"
    )


def live_sentence(live: dict) -> str:
    """One paragraph for the presentation from the exported live runs (real servers only)."""
    runs = live.get("runs", [])
    cap = live.get("capacity")
    if not runs and not cap:
        return "No real-server run was made."
    parts = []
    if cap:
        parts.append(
            f"The real capacity of the cluster was measured at {cap['lambda_sat_rps']:.2f} req/s"
            + (" (a quick estimate)" if cap.get("quick") else "")
            + "."
        )
    if runs:
        rows = "; ".join(
            f"{r['policy']}: goodput {r['metrics']['goodput_rps']:.3f} req/s, "
            f"{r['metrics']['sla_attainment'] * 100:.0f}% met both targets, "
            f"{r['metrics']['drop_rate'] * 100:.1f}% dropped"
            for r in runs
        )
        parts.append(f"{len(runs)} real-server run(s) on identical traffic: {rows}.")
        parts.append(
            "One run per policy is an anecdote; it shows the system works on real servers, "
            "not a new result."
        )
    return " ".join(parts)
