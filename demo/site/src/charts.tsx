// Hand-built SVG charts (no chart library): grouped bars with 95% CI whiskers, line chart, Pareto scatter.
// Every series has a colour AND a marker shape (DESIGN.md: never colour-only). Charts animate in on view.
import { useInView, fmt, Marker, styleOf, Legend } from "./ui";
import type { Metric, ParetoPoint } from "./data/types";

const W = 760;
const M = { l: 58, r: 16, t: 14, b: 58 };

function niceMax(v: number): number {
  if (v <= 0) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p;
}
const ticks = (max: number, n = 5) => Array.from({ length: n + 1 }, (_, i) => (max * i) / n);

export type BarSeries = { id: string; label?: string; color?: string; marker?: string; values: (Metric | null)[] };

export function BarsCI({ groups, series, xLabel, yLabel, digits = 2, height = 330, title }: {
  groups: string[]; series: BarSeries[]; xLabel: string; yLabel: string; digits?: number; height?: number; title: string;
}) {
  const [ref] = useInView<HTMLDivElement>(); // bars are always drawn: data must never wait for a scroll observer
  const H = height;
  const pw = W - M.l - M.r, ph = H - M.t - M.b;
  const top = Math.max(...series.flatMap((s) => s.values.map((v) => (v?.mean ?? 0) + (v?.ci ?? 0))), 0);
  const ymax = niceMax(top * 1.08);
  const gw = pw / groups.length;
  const bw = Math.min(30, (gw * 0.82) / Math.max(series.length, 1));
  const y = (v: number) => M.t + ph - (v / ymax) * ph;
  return (
    <div ref={ref}>
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title}>
        <title>{title}</title>
        {ticks(ymax).map((t) => (
          <g key={t}>
            <line className="grid" x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} />
            <text x={M.l - 8} y={y(t) + 4} textAnchor="end">{fmt(t, ymax < 5 ? 1 : 0)}</text>
          </g>
        ))}
        <line className="axis" x1={M.l} x2={W - M.r} y1={y(0)} y2={y(0)} />
        <text x={14} y={M.t + ph / 2} transform={`rotate(-90 14 ${M.t + ph / 2})`} textAnchor="middle">{yLabel}</text>
        <text x={M.l + pw / 2} y={H - 8} textAnchor="middle">{xLabel}</text>
        {groups.map((g, gi) => (
          <text key={g} className="strong" x={M.l + gi * gw + gw / 2} y={y(0) + 20} textAnchor="middle">{g}</text>
        ))}
        {series.map((s, si) => {
          const st = styleOf(s.id);
          const color = s.color ?? st.color, marker = s.marker ?? st.marker;
          return s.values.map((v, gi) => {
            const cx = M.l + gi * gw + gw / 2 - (series.length * bw) / 2 + si * bw + bw / 2;
            if (!v || v.mean == null) return <text key={`${si}-${gi}`} x={cx} y={y(0) - 6} textAnchor="middle" fontSize="9">n/a</text>;
            const yt = y(v.mean);
            return (
              <g key={`${si}-${gi}`} tabIndex={0} role="img" aria-label={`${s.label ?? st.label}, ${groups[gi]}: ${fmt(v.mean, digits)}${v.ci != null ? ` plus or minus ${fmt(v.ci, digits)}` : ""}`}>
                <title>{`${s.label ?? st.label} @ ${groups[gi]}: ${fmt(v.mean, digits)}${v.ci != null ? ` ± ${fmt(v.ci, digits)}` : ""} (n=${v.n})`}</title>
                <rect className="bar" style={{ animationDelay: `${gi * 90 + si * 40}ms` }} x={cx - bw / 2 + 1} y={yt} width={bw - 2} height={Math.max(y(0) - yt, 0)} fill={color} fillOpacity={0.78} rx={2} />
                {v.ci != null && v.ci > 0 && (
                  <g stroke="#f7f8f8" strokeWidth={1.4}>
                    <line x1={cx} x2={cx} y1={y(Math.max(v.mean - v.ci, 0))} y2={y(v.mean + v.ci)} />
                    <line x1={cx - 4} x2={cx + 4} y1={y(v.mean + v.ci)} y2={y(v.mean + v.ci)} />
                    <line x1={cx - 4} x2={cx + 4} y1={y(Math.max(v.mean - v.ci, 0))} y2={y(Math.max(v.mean - v.ci, 0))} />
                  </g>
                )}
                <g className="pop" style={{ animationDelay: `${500 + gi * 90 + si * 40}ms` }}><Marker kind={marker} x={cx} y={yt} r={4} color={color} /></g>
              </g>
            );
          });
        })}
      </svg>
      <Legend ids={series.map((s) => s.id)} />
      <DataTable groups={groups} series={series} digits={digits} />
    </div>
  );
}

function DataTable({ groups, series, digits }: { groups: string[]; series: BarSeries[]; digits: number }) {
  return (
    <details>
      <summary>Show the numbers (mean ± 95% interval)</summary>
      <div className="tablewrap">
        <table>
          <thead><tr><th>series</th>{groups.map((g) => <th key={g}>{g}</th>)}</tr></thead>
          <tbody>
            {series.map((s) => (
              <tr key={s.id}><td>{s.label ?? styleOf(s.id).label}</td>{s.values.map((v, i) => <td key={i}>{v?.mean == null ? "n/a" : `${fmt(v.mean, digits)}${v.ci != null ? ` ± ${fmt(v.ci, digits)}` : ""}`}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export type LineSeries = { id: string; label: string; color: string; dash?: string; marker?: string; points: { x: number; y: number | null }[] };

export function LineChart({ series, xLabel, yLabel, title, height = 280, yMin }: {
  series: LineSeries[]; xLabel: string; yLabel: string; title: string; height?: number; yMin?: number;
}) {
  const [ref] = useInView<HTMLDivElement>(); // lines are always drawn, no in-view gate
  const H = height;
  const pw = W - M.l - M.r, ph = H - M.t - M.b;
  const all = series.flatMap((s) => s.points.filter((p) => p.y != null) as { x: number; y: number }[]);
  if (!all.length) return <div className="notrun">No points to plot.</div>;
  const xmax = Math.max(...all.map((p) => p.x), 1);
  const lo = yMin ?? Math.min(0, ...all.map((p) => p.y));
  const hi = Math.max(...all.map((p) => p.y));
  const ymax = hi <= lo ? lo + 1 : lo + niceMax(hi - lo);
  const x = (v: number) => M.l + (v / xmax) * pw;
  const y = (v: number) => M.t + ph - ((v - lo) / (ymax - lo)) * ph;
  return (
    <div ref={ref}>
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title}>
        <title>{title}</title>
        {ticks(ymax - lo).map((t) => (
          <g key={t}><line className="grid" x1={M.l} x2={W - M.r} y1={y(lo + t)} y2={y(lo + t)} /><text x={M.l - 8} y={y(lo + t) + 4} textAnchor="end">{fmt(lo + t, ymax - lo < 5 ? 1 : 0)}</text></g>
        ))}
        {ticks(xmax, 4).map((t) => <text key={t} x={x(t)} y={H - M.b + 18} textAnchor="middle">{xmax < 5 ? fmt(t, 1) : Math.round(t)}</text>)}
        <text x={14} y={M.t + ph / 2} transform={`rotate(-90 14 ${M.t + ph / 2})`} textAnchor="middle">{yLabel}</text>
        <text x={M.l + pw / 2} y={H - 8} textAnchor="middle">{xLabel}</text>
        {series.map((s) => {  // always drawn (no in-view gate): robust for screenshots, print and reduced motion
          const pts = s.points.filter((p) => p.y != null) as { x: number; y: number }[];
          const d = pts.map((p, i) => `${i ? "L" : "M"}${x(p.x).toFixed(1)},${y(p.y).toFixed(1)}`).join(" ");
          const every = Math.max(1, Math.floor(pts.length / 8));
          return (
            <g key={s.id}>
              <path d={d} fill="none" stroke={s.color} strokeWidth={2} strokeDasharray={s.dash} />
              {pts.filter((_, i) => i % every === 0).map((p, i) => <Marker key={i} kind={s.marker ?? "circle"} x={x(p.x)} y={y(p.y)} r={3.5} color={s.color} />)}
            </g>
          );
        })}
      </svg>
      <div className="legend">
        {series.map((s) => (
          <span key={s.id}>
            <svg width="22" height="12" aria-hidden="true"><line x1="0" y1="6" x2="22" y2="6" stroke={s.color} strokeWidth="2" strokeDasharray={s.dash} /><Marker kind={s.marker ?? "circle"} x={11} y={6} r={4} color={s.color} /></svg>
            {s.label}
          </span>
        ))}
      </div>
    </div>
  );
}

export function ParetoScatter({ points, xLabel, yLabel, title }: { points: ParetoPoint[]; xLabel: string; yLabel: string; title: string }) {
  const [ref] = useInView<HTMLDivElement>(); // points are always drawn: data must never wait for a scroll observer
  const H = 380;
  const pw = W - M.l - M.r, ph = H - M.t - M.b;
  // the axes follow the MEANS (a few intervals are huge because some seeds behaved very differently); whiskers are clipped to the plot
  const xs = points.map((p) => p.cost.mean ?? 0), ys = points.map((p) => (p.latency.mean ?? 0) + (p.latency.ci ?? 0));
  // log y-axis when the latencies span more than a factor of 30 (here 7 s to 500 s), else linear
  const yPos = points.map((p) => p.latency.mean ?? 0).filter((v) => v > 0);
  const logY = yPos.length > 1 && Math.max(...yPos) / Math.min(...yPos) > 30;
  const xmax = niceMax(Math.max(...xs) / 0.55); // data in the left ~55% of the plot; the right part holds the labels
  const yLo = logY ? 10 ** Math.floor(Math.log10(Math.min(...yPos))) : 0;
  const yHi = logY ? 10 ** Math.ceil(Math.log10(Math.max(...ys))) : niceMax(Math.max(...ys) * 1.1);
  const ymax = yHi;
  const x = (v: number) => M.l + (v / xmax) * pw;
  const y = (v: number) => (logY ? M.t + ph - ((Math.log10(Math.max(v, yLo)) - Math.log10(yLo)) / (Math.log10(yHi) - Math.log10(yLo))) * ph : M.t + ph - (v / ymax) * ph);
  const yTicks = logY ? Array.from({ length: Math.round(Math.log10(yHi / yLo)) + 1 }, (_, i) => yLo * 10 ** i) : ticks(ymax);
  const front = points.filter((p) => p.on_frontier).sort((a, b) => (a.cost.mean ?? 0) - (b.cost.mean ?? 0));
  const d = front.map((p, i) => `${i ? "L" : "M"}${x(p.cost.mean ?? 0)},${y(p.latency.mean ?? 0)}`).join(" ");
  // labels sit in a column at the right of the plot, ordered by height, joined to their dots by thin leader lines
  const labelX = M.l + pw * 0.66;
  const order = points.map((_, i) => i).sort((a, b) => y(points[a].latency.mean ?? 0) - y(points[b].latency.mean ?? 0));
  const labelY: number[] = [];
  let last = -1e9;
  order.forEach((i) => { const ly = Math.max(y(points[i].latency.mean ?? 0), last + 15); labelY[i] = ly; last = ly; });
  const clipY = (v: number) => Math.min(Math.max(y(v), M.t), M.t + ph), clipX = (v: number) => Math.min(Math.max(x(v), M.l), M.l + pw);
  return (
    <div ref={ref}>
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title}>
        <title>{title}</title>
        {yTicks.map((t) => <g key={`y${t}`}><line className="grid" x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} /><text x={M.l - 8} y={y(t) + 4} textAnchor="end">{fmt(t, ymax < 5 ? 1 : 0)}</text></g>)}
        {ticks(xmax).map((t) => <text key={`x${t}`} x={x(t)} y={H - M.b + 18} textAnchor="middle">{fmt(t, xmax < 5 ? 1 : 0)}</text>)}
        <text x={14} y={M.t + ph / 2} transform={`rotate(-90 14 ${M.t + ph / 2})`} textAnchor="middle">{yLabel}{logY ? " (log scale)" : ""}</text>
        <text x={M.l + pw / 2} y={H - 8} textAnchor="middle">{xLabel}</text>
        {front.length > 1 && <path d={d} fill="none" stroke="#f7f8f8" strokeOpacity={0.55} strokeWidth={1.5} strokeDasharray="4 4" className="flow-line" />}
        {points.map((p, i) => {
          const st = p.kind === "learned" ? styleOf("ddqn") : styleOf(p.label);
          const cx = x(p.cost.mean ?? 0), cy = y(p.latency.mean ?? 0);
          return (
            <g key={i} tabIndex={0} role="img" aria-label={`${p.label}: cost ${fmt(p.cost.mean)}, latency ${fmt(p.latency.mean)}${p.on_frontier ? ", on the frontier" : ""}`}>
              <title>{`${p.label}: cost ${fmt(p.cost.mean)} ± ${fmt(p.cost.ci)}, ${yLabel} ${fmt(p.latency.mean)} ± ${fmt(p.latency.ci)}${p.on_frontier ? " (Pareto frontier)" : ""}`}</title>
              <line x1={cx + 9} y1={cy} x2={labelX - 6} y2={labelY[i] - 4} stroke={st.color} strokeOpacity={0.35} strokeWidth={1} />
              <g stroke={st.color} strokeOpacity={0.35} strokeWidth={1.2} strokeDasharray="3 3">
                {p.cost.ci != null && <line x1={clipX((p.cost.mean ?? 0) - p.cost.ci)} x2={clipX((p.cost.mean ?? 0) + p.cost.ci)} y1={cy} y2={cy} />}
                {p.latency.ci != null && <line x1={cx} x2={cx} y1={clipY((p.latency.mean ?? 0) - p.latency.ci)} y2={clipY((p.latency.mean ?? 0) + p.latency.ci)} />}
              </g>
              <g className="pop" style={{ animationDelay: `${i * 70}ms` }}>
                {p.on_frontier && <circle cx={cx} cy={cy} r={11} fill="none" stroke="#f7f8f8" strokeOpacity={0.5} />}
                <Marker kind={st.marker} x={cx} y={cy} r={p.kind === "learned" ? 6 : 5} color={st.color} />
              </g>
              <text x={labelX} y={labelY[i]} fontSize="11" className="strong" fill={st.color}>{p.label}{p.on_frontier ? " ◎" : ""}</text>
            </g>
          );
        })}
      </svg>
      <details>
        <summary>Show the numbers (mean ± 95% interval)</summary>
        <div className="tablewrap"><table><thead><tr><th>policy</th><th>cost / request</th><th>{yLabel}</th><th>goodput (req/s)</th><th>frontier</th></tr></thead>
          <tbody>{points.map((p, i) => <tr key={i}><td>{p.label}</td><td>{fmt(p.cost.mean)} ± {fmt(p.cost.ci)}</td><td>{fmt(p.latency.mean)} ± {fmt(p.latency.ci)}</td><td>{fmt(p.goodput.mean)} ± {fmt(p.goodput.ci)}</td><td>{p.on_frontier ? "yes" : "no"}</td></tr>)}</tbody></table></div>
      </details>
    </div>
  );
}
