// "Life of a request": an interactive stepper plus a timeline bar that lights the active phase. Auto-advances,
// pauses on hover/focus, and stays still with reduced motion. The timeline is a schematic (not to scale).
import { useEffect, useState } from "react";
import { useReducedMotion } from "../ui";

const STEPS = [
  { t: "A request arrives", d: "It has a prompt of P tokens. How long the answer will be is unknown. It lands at a random agent, one per server.", seg: -1 },
  { t: "The agent decides", d: "Accept (my server), Forward (to the neighbour with the least expected wait) or Defer (look again next tick). It sees only 7 numbers.", seg: -1 },
  { t: "Queue", d: "Accepted requests wait for a free batch slot and KV-cache room. This waiting counts toward time to first token.", seg: 0 },
  { t: "Prefill", d: "The server reads the whole prompt in one pass. Cost grows with prompt length; a cached prefix makes it much cheaper.", seg: 1 },
  { t: "Decode", d: "One token per step, shared with the other requests in the batch. More requests per step means slower steps for everyone.", seg: 2 },
  { t: "SLA check and reward", d: "Both targets met? The agents that acted get +10, a miss −10 (a drop −5). The serving agent also pays for the seconds it used. Credit arrives only now, after the decision.", seg: 3 },
];
const SEGS = [
  { name: "queue wait", w: 22, c: "#8a8f98", pat: true },
  { name: "prefill", w: 20, c: "#56b4e9", pat: false },
  { name: "decode steps", w: 46, c: "#e69f00", pat: false },
  { name: "SLA", w: 12, c: "#009e73", pat: false },
];

export function Lifecycle() {
  const reduced = useReducedMotion();
  const [i, setI] = useState(0);
  const [paused, setPaused] = useState(false);
  useEffect(() => {
    if (reduced || paused) return;
    const id = setInterval(() => setI((x) => (x + 1) % STEPS.length), 3400);
    return () => clearInterval(id);
  }, [reduced, paused]);
  const active = STEPS[i].seg;
  return (
    <div className="grid g2" onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)} onFocus={() => setPaused(true)} onBlur={() => setPaused(false)}>
      <div role="list">
        {STEPS.map((s, k) => (
          <button key={s.t} className="step" role="listitem" aria-current={k === i} onClick={() => setI(k)}>
            <span className="n">{k + 1}</span>
            <span><h3>{s.t}</h3>{k === i && <p>{s.d}</p>}</span>
          </button>
        ))}
      </div>
      <div className="card flat" aria-live="polite">
        <div className="label">schematic, not to scale</div>
        <div className="timeline" role="img" aria-label="Timeline of a request: queue wait, prefill, decode steps, SLA check">
          {SEGS.map((s, k) => (
            <div key={s.name} style={{ width: `${s.w}%`, background: s.pat ? "repeating-linear-gradient(135deg,#8a8f98 0 6px,#6c7078 6px 12px)" : s.c, opacity: active === -1 || active === k ? 1 : 0.28, transition: "opacity 200ms" }}>{s.name}</div>
          ))}
        </div>
        <svg viewBox="0 0 400 90" className="chart" aria-hidden="true">
          <line x1="14" x2="14" y1="10" y2="40" stroke="#f7f8f8" /><line x1="14" x2="14" y1="10" y2="10" />
          <path d="M14,24 H122" stroke="#56b4e9" strokeWidth="2" markerEnd="" /><text x="18" y="18" fill="#d0d6e0" fontSize="11">TTFT = queue wait + prefill (+ first step)</text>
          <path d="M122,64 H370" stroke="#e69f00" strokeWidth="2" /><text x="126" y="58" fill="#d0d6e0" fontSize="11">TPOT = time per decode step after the first</text>
          <text x="14" y="86" fill="#8a8f98" fontSize="11">goodput = requests per second that meet BOTH targets</text>
        </svg>
        <p className="muted" style={{ fontSize: 13.5, marginBottom: 0 }}>{STEPS[i].d}</p>
      </div>
    </div>
  );
}
