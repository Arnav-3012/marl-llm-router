"""Fill the demo-track results tables in docs/numbers.md and README.md from the exported dashboard
JSON. Tier B.

uv run python -m scripts.fill_numbers [--data demo/site/public/data]

The JSON in --data is itself produced from results/ (scripts/export_dashboard_data.py) and carries
each number's
source files and config hash, so every row written here names its source. Rows with no result are
left out, never
filled. Writes only between the AUTO markers; the rest of both files is untouched.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from marl_lb.config import ROOT

RHOS = ["0.5", "0.8", "0.95"]
LABEL = {
    "ddqn": "DDQN agents (k=full, λ=1)",
    "ddqn_reject_ft": "DDQN + Reject (v2 agents fine-tuned)",
    "ddqn_reject_mix": "DDQN + Reject (final: conversation + code training)",
    "ddqn_reject_scratch": "DDQN + Reject (conversation traffic only)",
    "ddqn_ft_ctrl": "DDQN fine-tuned without Reject (control)",
    "route_to_fast": "Route-to-fast rule (class-aware, local)",
    "route_to_fast_shed": "Route-to-fast + shed rule (class-aware, local, drops requests)",
    "sed_global": "SED global",
    "sed_local_full": "SED local k=full",
    "sed_local_k0": "SED local k=0",
    "sed_local_k1": "SED local k=1",
    "cache_aware_global": "Cache-aware global",
    "cache_aware_local_full": "Cache-aware local",
    # fmt: skip
    "jsq_global": "JSQ global",
    "po2_global": "Po2 global",
    "round_robin": "Round-robin",
    "random": "Random",
}


def cell(m) -> str:
    if not m or m.get("mean") is None:
        return "n/a"
    ci = f" ± {m['ci']:.2f}" if m.get("ci") is not None else ""
    return f"{m['mean']:.2f}{ci}"


def load(data: Path, name: str):
    p = data / name
    env = json.loads(p.read_text()) if p.exists() else None
    return env if env and env.get("status") == "ok" else None


def e1_table(data: Path) -> str:
    env = load(data, "baselines.json")
    if not env:
        return "_E1 not run yet: no results in results/baselines or results/main._\n"
    d, src = env["data"], env["source"]
    rows = []
    if d.get("learned"):
        rows.append(("ddqn", d["learned"]["rows"], src.get("learned")))
    for extra in d.get("learned_extra") or []:
        rows.append((extra["id"], extra["rows"], src.get(extra["id"])))
    for p, table in (d.get("baselines") or {"policies": {}})["policies"].items():
        rows.append(
            (p, table, src.get("route_to_fast_shed" if p == "route_to_fast_shed" else "baselines"))
        )
    out = [
        "| Policy | goodput ρ=0.5 | goodput ρ=0.8 | goodput ρ=0.95 | SLA attainment ρ=0.8 "
        "| cost/request ρ=0.8 | drop rate ρ=0.95 | seeds | Source (results/ files, config hash) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name, table, s in rows:
        g = [cell(table.get(r, {}).get("goodput_rps")) for r in RHOS]
        files = ", ".join((s or {}).get("files", [])[:1]) + (
            f" (+{len(s['files']) - 1})" if s and len(s.get("files", [])) > 1 else ""
        )
        at08 = table.get("0.8", {})
        out.append(
            f"| {LABEL.get(name, name)} | {g[0]} | {g[1]} | {g[2]} "
            f"| {cell(at08.get('sla_attainment'))} | {cell(at08.get('cost_per_request'))} "
            f"| {cell(table.get('0.95', {}).get('drop_rate'))} "
            f"| {(s or {}).get('n_seeds', '')} | `{files}` · {(s or {}).get('config_hash', '')} |"
        )
    return (
        "\n".join(out) + "\n\nGoodput in requests/s that met both targets; "
        "mean ± 95% interval over seeds (Student t). A policy that rejects requests is judged by "
        "its drop rate next to its goodput. The agents are the v2 agents (ADR-027).\n"
    )


def v1_table() -> str:
    """The stage-3 (v1) agents, kept next to v2 because the reward was changed after a diagnosis
    that looked at held-out behaviour of v1 (ADR-027).
    """
    from scripts.export_dashboard_data import learned_rows

    rows, src = learned_rows(ROOT / "results", "main", "DDQN v1")
    if not rows:
        return "_v1 results not found._\n"
    g = [cell(rows["rows"].get(r, {}).get("goodput_rps")) for r in RHOS]
    return (
        "**v1 agents (stage 3, cost paid by the serving agent only; "
        "kept for comparison, ADR-027)**\n\n"
        "| Policy | goodput ρ=0.5 | goodput ρ=0.8 | goodput ρ=0.95 | seeds | Source |\n"
        "|---|---|---|---|---|---|\n"
        f"| DDQN v1 | {g[0]} | {g[1]} | {g[2]} | {src.get('n_seeds', '')} "
        f"| `{src['files'][0]}` · {src.get('config_hash', '')} |\n"
    )


def balance_table(data: Path) -> str:
    env = load(data, "baselines.json")
    if not env:
        return ""
    d = env["data"]
    keys = ("util_fast", "util_slow", "jain_fast", "jain_utilisation")
    rows = [("ddqn", d["learned"]["rows"])] if d.get("learned") else []
    pol = (d.get("baselines") or {"policies": {}})["policies"]
    rows += [
        (p, pol[p]) for p in ("sed_global", "route_to_fast", "sed_local_full", "random") if p in pol
    ]
    out = [
        "**Balance by server class, ρ = 0.8 (ADR-030)**\n",
        "| Policy | utilisation fast servers | utilisation slow servers "
        "| Jain over the fast servers "
        "| Jain over all servers (not a routing-quality measure) |",
        "|---|---|---|---|---|",
    ]
    for name, table in rows:
        m = table.get("0.8", {})
        out.append(
            f"| {LABEL.get(name, name)} | " + " | ".join(cell(m.get(k)) for k in keys) + " |"
        )
    return "\n".join(out) + "\n"


def e34_table(data: Path) -> str:
    out = []
    p = load(data, "pareto.json")
    out.append("**E3 (λ sweep, ρ = 0.8)**\n")
    if p:
        out += [
            "| Point | cost/request | TTFT p95 (s) | goodput | on frontier |",
            "|---|---|---|---|---|",
        ]
        out += [
            f"| {x['label']} | {cell(x['cost'])} | {cell(x['latency'])} | {cell(x['goodput'])} "
            f"| {'yes' if x['on_frontier'] else 'no'} |"
            for x in p["data"]["points"]
        ]
    else:
        out.append("_not run_")
    o = load(data, "observability.json")
    out.append("\n**E4 (k=0 vs k=full), goodput**\n")
    if o:
        out += ["| Policy | ρ=0.5 | ρ=0.8 | ρ=0.95 |", "|---|---|---|---|"]
        for row in o["data"]["learned"]:
            out.append(
                f"| {row['label']} | "
                + " | ".join(cell(row["rows"].get(r, {}).get("goodput_rps")) for r in RHOS)
                + " |"
            )
    else:
        out.append("_not run_")
    return "\n".join(out) + "\n"


def splice(path: Path, tag: str, body: str) -> None:
    text = path.read_text()
    block = f"<!-- AUTO:{tag} -->\n{body}<!-- /AUTO:{tag} -->"
    if f"<!-- AUTO:{tag} -->" in text:
        text = re.sub(
            rf"<!-- AUTO:{tag} -->.*?<!-- /AUTO:{tag} -->", lambda _m: block, text, flags=re.S
        )
    else:
        text = text.rstrip("\n") + "\n\n" + block + "\n"
    path.write_text(text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT / "demo" / "site" / "public" / "data")
    a = ap.parse_args()
    body = (
        "### Demo track results (generated from results/; do not edit by hand)\n\n"
        + e1_table(a.data)
        + "\n"
        + v1_table()
        + "\n"
        + e34_table(a.data)
        + "\n"
        + balance_table(a.data)
    )
    splice(ROOT / "docs" / "numbers.md", "demo", body)
    splice(ROOT / "README.md", "results", body)
    print("filled docs/numbers.md and README.md between the AUTO markers")


if __name__ == "__main__":
    main()
