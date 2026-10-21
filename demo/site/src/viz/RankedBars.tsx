// A ranked comparison of policies that all replayed the SAME requests: one row per policy, best first, with goodput as the bar and
// the share that met both targets and the refused share beside it (a policy that refuses requests must always show how many).
// Used by the Live page (this run) and the Stress tests page (the saved real-server comparison). One run per policy is an anecdote.
import { fmt } from "../ui";

export type RankRow = { label: string; policy: string; goodput_rps: number; sla_attainment: number; drop_rate: number; ttft_p95?: number | null };

export function RankedBars({ rows, capacity }: { rows: RankRow[]; capacity?: number | null }) {
  const ranked = [...rows].sort((a, b) => b.goodput_rps - a.goodput_rps);
  const top = Math.max(0.001, capacity ?? 0, ...ranked.map((r) => r.goodput_rps));
  const best = ranked[0]?.goodput_rps ?? 0;
  return (
    <div className="rk" role="table" aria-label="policies ranked by goodput, best first">
      <div className="rk-head" role="row"><span>policy</span><span>goodput (requests per second that met both targets)</span><span>met both</span><span>refused</span></div>
      {ranked.map((r, i) => (
        <div key={r.policy} className={`rk-row ${i === 0 ? "best" : ""}`} role="row">
          <span className="rk-name"><b>{i + 1}</b>{r.label}</span>
          <span className="rk-bar"><i style={{ width: `${Math.max(1, (r.goodput_rps / top) * 100)}%` }} /><em>{fmt(r.goodput_rps, 3)}</em>
            {capacity ? <u style={{ left: `${Math.min(100, (capacity / top) * 100)}%` }} title="the arrival rate: no policy can exceed it" /> : null}</span>
          <span>{fmt(r.sla_attainment * 100, 0)}%</span>
          <span>{fmt(r.drop_rate * 100, 1)}%</span>
        </div>
      ))}
      <p className="muted rk-note">{ranked.length > 1 && best - ranked[1].goodput_rps < 0.01 ? "The top two are within 0.01 req/s here: treat them as tied." : ""}</p>
    </div>
  );
}
