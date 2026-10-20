"""The guided live test: one button runs the whole check and narrates it. Tier B.

Steps, each reported as a message the dashboard shows like a chat: (1) all four servers answer,
(2) one short chat through a policy, (3) the capacity of this cluster (reuse the measured one, or
measure it quickly with the ADR-011 criteria; in mock mode the simulator's is used and said so),
(4) the same held-out slice replayed once per policy, one after the other (never together: they
share one chip), (5) a comparison and the honest reading: one run per policy is an anecdote.
Every run writes results/live/<run_id>/ as usual. The class is driven by app.State.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

from marl_lb.eval.saturation import find_lambda_sat
from marl_lb.router.capacity import THRESHOLDS, criteria_from_events
from marl_lb.router.factory import POLICIES
from marl_lb.router.runs import machine_info
from marl_lb.sim.request import Request

LABEL = {
    "ddqn_agents": "the learned agents (DDQN + Reject)",
    "route_to_fast_shed": "the hand-written rule (route to fast + shed)",
    "route_to_fast": "the hand-written rule (route to fast)",
    "sed_global": "SED global, a strong classic rule",
    "sed_local_full": "SED local",
    "cache_aware_global": "cache-aware routing",
    "cache_aware_local_full": "local cache-aware routing",
    "random": "random routing",
}
QUICK = {"window": 40.0, "seeds": [0], "grid": [0.15, 0.3, 0.6, 1.2], "refine": 2}
MOCK_NOTE = " MOCK: simulated stand-ins, so this is a rehearsal, not a result."


class LiveCheck:
    def __init__(self, st):
        self.st = st
        self.state = "idle"  # idle | running | done | failed | stopped
        self.messages: list[dict] = []
        self.rows: list[dict] = []
        self.current_run: str | None = None
        self.opts: dict = {}
        self.task: asyncio.Task | None = None
        self._stop = False

    def say(self, text: str, kind: str = "info") -> None:
        at = datetime.now().strftime("%H:%M:%S")
        self.messages.append({"i": len(self.messages), "at": at, "kind": kind, "text": text})

    def stop(self) -> None:
        self._stop = True
        if self.st.current and self.st.current.state == "running":
            self.st.current.stop()

    def fail(self, text: str) -> None:
        self.say(text, "error")
        self.state = "failed"

    def _stopped(self) -> None:
        self.say("Stopped.", "warn")
        self.state = "stopped"

    async def run(self, opts: dict) -> None:
        self.opts, self.state = opts, "running"
        try:
            await self._steps(opts)
        except asyncio.CancelledError:
            self._stopped()
            raise
        except Exception as e:  # noqa: BLE001 - report instead of dying silently
            self.fail(f"The live test stopped on an error: {e}")

    async def _steps(self, opts: dict) -> None:
        st = self.st
        mock = st.s.mode == "mock"
        # 1. servers
        self.say("Checking the four servers…")
        up = [await st.client.health(b.url) for b in st.backends]
        if not all(up):
            down = ", ".join(b.name for b, u in zip(st.backends, up, strict=True) if not u)
            hint = "" if mock else " Press “Start servers”, wait about a minute, then try again."
            return self.fail(f"Not all servers answer ({down}).{hint}")
        fast = sum(1 for b in st.backends if b.class_name.startswith("fast"))
        text = f"All four servers answer ({fast} fast, {len(st.backends) - fast} slow)."
        self.say(text + (MOCK_NOTE if mock else ""), "ok")
        # 2. one short chat
        self.say("Sending one short request through SED local…")
        router = st.chat_routers.get("sed_local_full") or st.new_router("sed_local_full", 0)
        st.chat_routers["sed_local_full"] = router
        st.chat_id += 1
        p = st.world.params
        req = Request(st.chat_id, 0.0, 12, 8, st.chat_id, 0, False, p.ttft_target, p.tpot_target)
        out = await router.handle(req, "Say hello in five words.", 8)
        if out.status != "done":
            return self.fail(f"The short request failed ({out.status}).")
        b = st.backends[out.server]
        kind = b.class_name.replace("_", " ")
        self.say(
            f"{b.name} ({kind}) answered: time to first token {out.completion.ttft_s:.2f} s.", "ok"
        )
        if self._stop:
            return self._stopped()
        # 3. capacity
        lam = await self._capacity(opts)
        if lam is None:
            return
        rate = opts["rho"] * lam
        whose = " (the simulator's)" if mock else ""
        self.say(
            f"Load ρ = {opts['rho']} means {rate:.2f} requests per second on this cluster; "
            f"its capacity is {lam:.2f}{whose}."
        )
        # 4. one run per policy on the same slice
        todo = [x for x in opts["policies"] if x in POLICIES]
        if "ddqn_agents" in todo and not st.s.agents_exp:
            self.say(
                "Skipping the learned agents: the router was started without their weights.", "warn"
            )
            todo.remove("ddqn_agents")
        slice_ids = set()
        for k, pol in enumerate(todo, 1):
            if self._stop:
                return self._stopped()
            self.say(
                f"Run {k} of {len(todo)}: {LABEL.get(pol, pol)}, {opts['seconds']:.0f} s of "
                f"held-out traffic (seed {opts['seed']}). Watch the cluster below."
            )
            run, _ = st.make_run(pol, opts["seed"], opts["seconds"], rate_rps=rate)
            run.cfg["rho"] = opts["rho"]
            st.current, self.current_run = run, run.run_id
            m = await run.run()
            sl = json.loads((run.dir / "slice.json").read_text())["slice_id"]
            slice_ids.add(sl)
            self.rows.append(
                {
                    "policy": pol,
                    "label": LABEL.get(pol, pol),
                    "run_id": run.run_id,
                    "slice": sl,
                    "metrics": m,
                }
            )
            ttft = f", first token p95 {m['ttft_p95']:.2f} s" if m["ttft_p95"] else ""
            self.say(
                f"Done: goodput {m['goodput_rps']:.3f} req/s, {m['sla_attainment'] * 100:.0f}% "
                f"of requests met both targets, {m['drop_rate'] * 100:.1f}% dropped{ttft}.",
                "ok",
            )
        if self._stop:
            return self._stopped()
        # 5. reading
        same = len(slice_ids) == 1
        self.say(
            f"All {len(self.rows)} runs replayed the same requests (slice "
            f"{'/'.join(sorted(slice_ids))}).",
            "ok" if same else "warn",
        )
        self._compare()
        self.say(
            "Honest reading: one run per policy is an anecdote, not a result. The 5-seed recorded "
            "results are on the Baselines and Stress tests pages; this check shows that the system "
            "runs for real and how the live numbers compare."
            + (" MOCK: not a result." if mock else "")
        )
        self.state = "done"

    def _compare(self) -> None:
        if len(self.rows) < 2:
            return
        best = max(self.rows, key=lambda r: r["metrics"]["goodput_rps"])
        parts = "; ".join(f"{r['label']}: {r['metrics']['goodput_rps']:.3f}" for r in self.rows)
        self.say(f"Goodput (req/s): {parts}. Highest in this run: {best['label']}.")

    async def _capacity(self, opts: dict) -> float | None:
        st = self.st
        if st.s.mode == "mock":
            self.say("Capacity: using the simulator's value (mock mode).")
            return st.lambda_sat()
        f = st.s.live_root / "real_lambda_sat.json"
        if f.exists() and opts.get("capacity", "auto") != "measure":
            doc = json.loads(f.read_text())
            when = doc.get("measured", "earlier")[:16]
            self.say(
                f"Capacity of this cluster: {doc['lambda_sat_rps']:.2f} requests per second "
                f"(measured {when}).",
                "ok",
            )
            return float(doc["lambda_sat_rps"])
        n_grid, n_ref, win = len(QUICK["grid"]), QUICK["refine"], QUICK["window"]
        self.say(
            f"Capacity not measured yet: measuring it now, quickly ({n_grid} loads plus {n_ref} "
            f"refinements, {win:.0f} s each, one seed; about 6 to 10 minutes). Please do not "
            "use the machine meanwhile.",
            "warn",
        )
        loop = asyncio.get_running_loop()
        points: list[dict] = []

        def evaluate(rate: float) -> dict:
            async def one() -> dict:
                run, _ = st.make_run("sed_global", 0, win, rate_rps=rate)
                st.current, self.current_run = run, run.run_id
                await run.run()
                crit = criteria_from_events(run.router.events.events, win)
                points.append({"rate_rps": rate, "run_id": run.run_id, **crit})
                self.say(
                    f"  {rate:.2f} req/s: {crit['completion_ratio'] * 100:.0f}% completed in "
                    f"time, {crit['drop_rate'] * 100:.0f}% dropped, backlog x"
                    f"{crit['backlog_ratio']:.1f}."
                )
                return crit

            c = asyncio.run_coroutine_threadsafe(one(), loop).result()
            return {k: c[k] for k in ("completion_ratio", "drop_rate", "backlog_ratio")}

        args = (evaluate, QUICK["grid"], n_ref, THRESHOLDS)
        found = await asyncio.to_thread(find_lambda_sat, *args)
        lam = found["lambda_sat_rps"]
        if lam is None:
            self.fail(
                "Every tested load kept up, so the capacity is above the tested range. Run "
                "scripts/live_capacity_probe.py with a larger --grid."
            )
            return None
        doc = {
            "lambda_sat_rps": float(lam),
            "policy": "sed_global",
            "quick": True,
            "window_s": win,
            "seeds": QUICK["seeds"],
            "points": points,
            "machine": machine_info(),
            "measured": datetime.now().isoformat(timespec="seconds"),
        }
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(doc, indent=2, default=float))
        self.say(
            f"Measured capacity: {lam:.2f} requests per second (a quick estimate; the full "
            "probe is more careful).",
            "ok",
        )
        return float(lam)
