"""Fill the computed parts of docs/presentation-prompt.md from the exported dashboard data. Tier B.

uv run python -m scripts.fill_presentation [--data demo/site/public/data]

Writes only between the AUTO markers: (numbers) a table of the headline results, (layout) the
sentence for the layout-test slide, (live) the sentence for the real-server slide. Everything comes
from the same JSON the dashboard reads (which comes from results/), so the deck cannot say what the
site does not. Sections without results say so and are left for later; nothing is invented.
"""

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
    print(f"filled {a.file} (numbers, layout, live)")


if __name__ == "__main__":
    main()
