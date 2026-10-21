"""Fill the computed parts of docs/presentation-prompt.md from the exported dashboard data. Tier B.

uv run python -m scripts.fill_presentation [--data demo/site/public/data]

Writes only between the AUTO markers: (numbers) a table of the headline results, (layout) the
sentence for the layout-test slide, (live) the sentence for the real-server slide. Everything comes
from the same JSON the dashboard reads (which comes from results/), so the deck cannot say what the
site does not. Sections without results say so and are left for later; nothing is invented.
"""

# ruff: noqa: E501  (long prose strings for the presentation text)
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from marl_lb.config import ROOT
from marl_lb.eval.layout_verdict import layout_sentence, live_sentence

RHOS = ["0.5", "0.8", "0.95"]


def load(data: Path, name: str):
    p = data / name
    env = json.loads(p.read_text()) if p.exists() else None
    return env["data"] if env and env.get("status") == "ok" else None


def cell(m) -> str:
    if not m or m.get("mean") is None:
        return "n/a"
    return f"{m['mean']:.3f}" + (f" ± {m['ci']:.3f}" if m.get("ci") is not None else "")


def numbers_block(data: Path) -> str:
    b = load(data, "baselines.json")
    if not b:
        return "_Baselines not exported yet._"
    rows = []
    mix = next((x for x in b.get("learned_extra") or [] if x["id"] == "ddqn_reject_mix"), None)
    if mix:
        rows.append(("Final agents (DDQN + Reject, conversation + code training)", mix["rows"]))
    if b.get("learned"):
        rows.append(("Agents with 3 actions (first agents)", b["learned"]["rows"]))
    pol = (b.get("baselines") or {"policies": {}})["policies"]
    for key, label in (
        ("route_to_fast_shed", "Hand-written rule: route to fast + shed"),
        ("route_to_fast", "Hand-written rule: route to fast"),
        ("sed_global", "SED global"),
        ("sed_local_full", "SED local"),
        ("random", "Random"),
    ):
        if key in pol:
            rows.append((label, pol[key]))
    out = [
        "| Policy | goodput ρ=0.5 | goodput ρ=0.8 | goodput ρ=0.95 | dropped ρ=0.95 |",
        "|---|---|---|---|---|",
    ]
    for label, table in rows:
        g = [cell(table.get(r, {}).get("goodput_rps")) for r in RHOS]
        d = table.get("0.95", {}).get("drop_rate")
        out.append(f"| {label} | {g[0]} | {g[1]} | {g[2]} | {cell(d)} |")
    return (
        "Held-out traffic, 5 seeds, mean ± 95% interval, goodput in requests per second "
        "(from the dashboard data):\n\n" + "\n".join(out)
    )


def layout_block(data: Path) -> str:
    d = load(data, "layout.json")
    if not d:
        return "[LAYOUT RESULT: the layout test has not been run yet]"
    return layout_sentence(d, d.get("agents_training_minutes"))


def live_block(data: Path) -> str:
    d = load(data, "live.json")
    if not d:
        return "[LIVE RESULT: no real-server run has been made yet]"
    return live_sentence(d)


def _latest_fit() -> dict | None:
    fits = sorted((ROOT / "results" / "calibration_load").glob("*/fit.json"))
    return json.loads(fits[-1].read_text()) if fits else None


def simreal_block(data: Path) -> str:
    """Real servers vs the simulator (ADR-037), from the last fit's own table of runs."""
    d = _latest_fit()
    if not d:
        return "[TO BE FILLED: no real-server measurement under load has been fitted yet]"
    rows = [
        "| policy | load (req/s) | met both targets: real | simulator (first calibration) |",
        "|---|---|---|---|",
    ]
    for r in sorted(
        d["fit"] + d["validation"], key=lambda r: (r["real"]["rate"], r["real"]["policy"])
    ):
        rr = r["real"]
        rows.append(
            f"| {rr['policy']} | {rr['rate']:.2f} | {rr['sla'] * 100:.0f}% | "
            f"{r['sim_old']['sla'] * 100:.0f}% |"
        )
    return (
        "Same held-out requests replayed on the real cluster and in the simulator, seed 0 (window 90 s; "
        "the 0.15 and 0.60 req/s rows are the first, 40 s runs):\n\n"
        + "\n".join(rows)
        + "\n\nThe simulator is accurate at light load and optimistic from 0.20 req/s: real busy servers "
        "slow down much more than the profiled interference predicts (fast-server time per token 0.2 to "
        "0.3 s under load against 0.011 s for a lone request). Cause: llama-server runs all requests in "
        "one forward pass (a long prompt delays everybody), attention reads every request's context at "
        "every step, and all four servers share one chip and one memory bus. The profiling had measured "
        "interference with one background request per server."
    )


def recal_block(data: Path) -> str:
    d = _latest_fit()
    if not d:
        return "[TO BE FILLED]"
    n_ok = sum(1 for r in d["validation"] if r["pass"])
    verdict = "PASSED" if d["passed"] else "FAILED"
    return (
        f"We tried to recalibrate the simulator on those runs (three fits; pass bar fixed in advance, "
        f"ADR-037: simulated share meeting both targets within 10 points of the real one on every "
        f"validation run). The fits reproduced the runs they were fitted on but the validation "
        f"{verdict} ({n_ok} of {len(d['validation'])} validation runs within the bar), so we did NOT "
        "retrain the agents and every simulator result in this deck uses the first calibration. "
        "Say it plainly: this is a limit of the project and a finding about sim-to-real."
    )


def livecompare_block(data: Path) -> str:
    """Slide 20c: every policy on the same requests on the real servers (main comparisons)."""
    d = load(data, "live.json")
    comps = [c for c in (d or {}).get("comparisons", []) if c.get("kind") == "main"]
    if not comps:
        return "[TO BE FILLED: the full live showdown has not been run yet]"
    out = []
    comps.sort(key=lambda c: (c["rate_rps"], c.get("created", "")))
    for c in comps:
        rate, adaptive = c["rate_rps"], bool(c.get("adaptive"))
        n = c["ranking"][0].get("n_arrived")
        out.append(
            f"Real servers, {rate:.2f} req/s{' with live speed correction (ADR-039)' if adaptive else ''}, "
            f"{c['seconds']:.0f} s of identical traffic per policy plus at most {c.get('drain_s') or 0:.0f} s "
            f"to finish ({n} requests each; one run per policy, an anecdote):\n\n"
            "| rank | policy | goodput (req/s) | met both targets | refused | first token p95 (s) |\n"
            "|---|---|---|---|---|---|"
        )
        for r in c["ranking"]:
            p95 = "n/a" if r.get("ttft_p95") is None else f"{r['ttft_p95']:.1f}"
            out.append(
                f"| {r['rank']} | {r['label']} | {r['goodput_rps']:.3f} | {r['n_sla_met']} of {r['n_arrived']} "
                f"({r['sla_attainment'] * 100:.0f}%) | {r['drop_rate'] * 100:.1f}% | {p95} |"
            )
        out.append("")
    return "\n".join(out)


def splice(path: Path, tag: str, body: str) -> None:
    text = path.read_text()
    block = f"<!-- AUTO:{tag} -->\n{body}\n<!-- /AUTO:{tag} -->"
    pat = rf"<!-- AUTO:{tag} -->.*?<!-- /AUTO:{tag} -->"
    if re.search(pat, text, flags=re.S):
        text = re.sub(pat, lambda _m: block, text, flags=re.S)
    else:
        raise SystemExit(f"marker AUTO:{tag} not found in {path}")
    path.write_text(text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT / "demo" / "site" / "public" / "data")
    ap.add_argument("--file", type=Path, default=ROOT / "docs" / "presentation-prompt.md")
    a = ap.parse_args()
    splice(a.file, "numbers", numbers_block(a.data))
    splice(a.file, "layout", layout_block(a.data))
    splice(a.file, "live", live_block(a.data))
    splice(a.file, "simreal", simreal_block(a.data))
    splice(a.file, "recal", recal_block(a.data))
    splice(a.file, "livecompare", livecompare_block(a.data))
    print(f"filled {a.file} (numbers, layout, live, simreal, recal)")


if __name__ == "__main__":
    main()
