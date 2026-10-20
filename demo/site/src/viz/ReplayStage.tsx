// Draws one frame of a recorded episode: 4 router agents, 4 servers (fast = solid square, slow = dashed circle),
// queue bars, KV-fullness rings, arriving requests, decision glyphs and resolution flashes.
import type { Frame } from "../data/types";

const COL = { fast: "#56b4e9", slow: "#e69f00", ok: "#009e73", bad: "#d55e00", accent: "#7170ff" };
const ACT = ["●", "→", "⏱"]; // Accept, Forward, Defer: shape, not colour
const ACT_NAME = ["Accept", "Forward", "Defer"];

export function ReplayStage({ frame, layout, queueCap = 16, mode }: { frame: Frame; layout: string[]; queueCap?: number; mode: "agents" | "global" }) {
  const W = 880, H = 330;
  const y = (i: number) => 52 + i * 76;
  const ax = 250, sx = 740;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label={`Replay frame at t = ${frame.t.toFixed(1)} s`}>
      <text x={40} y={16} fontSize="11">requests</text>
      {mode === "agents" && <text x={ax} y={16} textAnchor="middle" fontSize="11">router agents</text>}
      <text x={sx} y={16} textAnchor="middle" fontSize="11">servers</text>
      {[0, 1, 2, 3].map((i) => {
        const fast = (layout[i] ?? "").startsWith("fast"), col = fast ? COL.fast : COL.slow;
        const q = frame.queue?.[i] ?? 0, a = frame.active?.[i] ?? 0, kv = frame.kv?.[i] ?? 0;
        const hot = kv > 0.8;
        const arrivals = frame.arrivals.filter((r) => r.entry === i);
        const acts = frame.acts.filter((r) => r.agent === i);
        const res = frame.resolves.filter((r) => r.server === i);
        return (
          <g key={i}>
            <line x1={ax + 22} x2={sx - 40} y1={y(i)} y2={y(i)} stroke="rgba(113,112,255,0.35)" strokeWidth={1.5} strokeDasharray="4 6" className="flow-line" />
            {mode === "agents" && (
              <g>
                <path d={[0, 1, 2, 3, 4, 5].map((k) => { const t = (Math.PI / 3) * k + Math.PI / 6; return `${k ? "L" : "M"}${ax + Math.cos(t) * 18},${y(i) + Math.sin(t) * 18}`; }).join(" ") + "Z"} fill="rgba(113,112,255,0.16)" stroke={COL.accent} strokeWidth={1.5} />
                <text x={ax} y={y(i) + 4} textAnchor="middle" fontSize="11" fill="#d0d6e0">A{i}</text>
                {acts.slice(0, 2).map((r, k) => (
                  <text key={`${frame.tick}-${r.req}`} className="pop" x={ax + 26 + k * 16} y={y(i) - 16} fontSize="14" fill="#f7f8f8"><title>{`${ACT_NAME[r.action]} request ${r.req}`}</title>{ACT[r.action]}</text>
                ))}
              </g>
            )}
            {arrivals.slice(0, 4).map((r, k) => (
              <circle key={`${frame.tick}-${r.req}`} className="fly" cx={ax - 60 - k * 12} cy={y(i) + (k - 1.5) * 4} r={3 + Math.min((r.p ?? 800) / 700, 6)} fill="#f7f8f8" fillOpacity={0.85}><title>{`request ${r.req}, ${r.p ?? "?"} prompt tokens`}</title></circle>
            ))}
            {/* server */}
            {fast
              ? <rect x={sx - 28} y={y(i) - 28} width={56} height={56} rx={11} fill={a ? "rgba(86,180,233,0.22)" : "rgba(255,255,255,0.03)"} stroke={col} strokeWidth={2} />
              : <circle cx={sx} cy={y(i)} r={29} fill={a ? "rgba(230,159,0,0.2)" : "rgba(255,255,255,0.03)"} stroke={col} strokeWidth={2} strokeDasharray="5 4" />}
            <circle cx={sx} cy={y(i)} r={36} fill="none" stroke={hot ? COL.bad : "rgba(255,255,255,0.18)"} strokeWidth={hot ? 3 : 1.5} strokeDasharray={`${Math.min(kv, 1) * 226} 226`} transform={`rotate(-90 ${sx} ${y(i)})`} />
            {Array.from({ length: Math.min(a, 8) }, (_, k) => <circle key={k} cx={sx - 14 + (k % 4) * 9.5} cy={y(i) - 5 + Math.floor(k / 4) * 12} r={3.4} fill="#f7f8f8" />)}
            <text x={sx + 46} y={y(i) - 4} fontSize="11" fill="#d0d6e0">{fast ? "fast" : "slow"} · {a} serving</text>
            <text x={sx + 46} y={y(i) + 11} fontSize="11" fill={hot ? "#ffb37a" : "#8a8f98"}>KV {Math.round(kv * 100)}%{hot ? " ⚠" : ""} · queue {q}</text>
            <rect x={sx - 150} y={y(i) + 8} width={100} height={6} rx={3} fill="rgba(255,255,255,0.08)" />
            <rect x={sx - 150} y={y(i) + 8} width={Math.min(q / queueCap, 1) * 100} height={6} rx={3} fill={q / queueCap > 0.6 ? COL.bad : col} />
            {res.slice(0, 2).map((r, k) => (
              <g key={`${frame.tick}-${r.req}`}>
                <circle className="ping" cx={sx} cy={y(i)} r={30} fill="none" stroke={r.ok ? COL.ok : COL.bad} strokeWidth={2.5} />
                <text className="pop" x={sx - 6 + k * 14} y={y(i) - 34} fontSize="14" fill={r.ok ? "#7be0c3" : "#ffb37a"}>{r.ok ? "✓" : "✕"}</text>
              </g>
            ))}
          </g>
        );
      })}
    </svg>
  );
}
