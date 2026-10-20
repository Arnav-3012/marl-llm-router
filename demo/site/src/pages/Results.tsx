// Pareto, Baselines & E1, Observability, Traces, Method pages.
import { useState } from "react";
import { BarsCI, LineChart, ParetoScatter, type BarSeries } from "../charts";
import { Card, Loaded, Marker, SourceNote, fmt, styleOf, useData, useLoad } from "../ui";
import type { Metric, MetricRow, PolicyTable } from "../data/types";

const RHOS = ["0.5", "0.8", "0.95"];
const METRIC_LABEL: Record<string, string> = {
  goodput_rps: "goodput (requests/s that met both targets)", sla_attainment: "SLA attainment (share of arrivals)", breach_rate: "breach rate", drop_rate: "drop rate",
  ttft_p95: "TTFT p95 (s)", tpot_p95: "TPOT p95 (s/token)", e2e_p95: "end-to-end p95 (s)", cost_per_request: "cost per request (synthetic units)", cache_hit_rate: "cache hit rate (token share)", jain_utilisation: "Jain's index of utilisation",
};
const col = (rows: Record<string, MetricRow> | undefined, key: string): (Metric | null)[] => RHOS.map((r) => rows?.[r]?.[key] ?? null);
const fromTable = (t: PolicyTable | undefined, p: string, key: string) => RHOS.map((r) => t?.[p]?.[r]?.[key] ?? null);

export function Pareto() {
  const ds = useData();
  const s = useLoad(() => ds.getPareto(), []);
  return (
    <>
      <div className="eyebrow">Q2 · E3</div><h1 style={{ fontSize: "clamp(28px,4vw,40px)" }}>Cost against latency</h1>
      <p className="lead">λ weighs money against speed in the reward. Sweeping it should trace a frontier that no fixed rule reaches. Points on the frontier are circled; error bars are 95% intervals over seeds.</p>
      <Loaded state={s} what="Cost–latency frontier (E3)">
        {(d, env) => (<Card className="flat"><ParetoScatter points={d.points} xLabel="cost per request (synthetic units, lower is better)" yLabel="TTFT p95 (s)" title="Cost per request against TTFT p95 at load 0.8" /><SourceNote source={env.source} /></Card>)}
      </Loaded>
    </>
  );
}

export function Baselines() {
  const ds = useData();
  const b = useLoad(() => ds.getBaselines(), []);
  const t = useLoad(() => ds.getTraining(), []);
  const [metric, setMetric] = useState("goodput_rps");
  return (
    <>
      <div className="eyebrow">Q1 · E1</div><h1 style={{ fontSize: "clamp(28px,4vw,40px)" }}>Learned agents against the baselines</h1>
      <p className="lead">Same held-out traffic for every policy, 5 seeds, greedy agents (ε = 0), mean ± 95% interval. The agents were trained once at ρ = 0.8 and evaluated at all three loads.</p>
      <div className="controls"><label>metric <select value={metric} onChange={(e) => setMetric(e.target.value)} aria-label="metric">{Object.entries(METRIC_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label></div>
      <Loaded state={b} what="Baselines and learned agents (E1)">
        {(d, env) => {
          const order = ["sed_global", "sed_local_full", "sed_local_k0", "cache_aware_global", "cache_aware_local_full", "jsq_global", "po2_global", "round_robin", "random"];
          const series: BarSeries[] = [
            ...(d.learned ? [{ id: "ddqn", label: d.learned.label, values: col(d.learned.rows, metric) }] : []),
            ...order.filter((p) => d.baselines?.policies[p]).map((p) => ({ id: p, values: fromTable(d.baselines?.policies, p, metric) })),
          ];
          return (
            <Card className="flat">
              <BarsCI groups={RHOS} series={series} xLabel="offered load ρ (fraction of the saturation rate)" yLabel={METRIC_LABEL[metric]} title={`${METRIC_LABEL[metric]} by policy and load`} digits={metric.includes("tpot") ? 3 : 2} />
              <SourceNote source={env.source} />
            </Card>
          );
        }}
      </Loaded>
      <h2 style={{ marginTop: 48 }}>Training curves</h2>
      <Loaded state={t} what="Training curves">
        {(d, env) => {
          const pts = (k: string) => d.episodes.map((e) => ({ x: e.episode as number, y: e[k] as number | null }));
          return (
            <div className="grid g2">
              <Card className="flat"><LineChart title="Mean return per episode" xLabel="episode" yLabel="return (mean over agents and seeds)" series={[{ id: "r", label: "return", color: "#e69f00", marker: "circle", points: pts("return_mean") }]} /></Card>
              <Card className="flat"><LineChart title="Goodput during training" xLabel="episode" yLabel="goodput (req/s, with exploration)" series={[{ id: "g", label: "goodput", color: "#56b4e9", marker: "square", points: pts("goodput_rps") }]} /></Card>
              <Card className="flat"><LineChart title="TD loss" xLabel="episode" yLabel="TD loss (Huber)" series={[{ id: "l", label: "TD loss", color: "#cc79a7", marker: "diamond", dash: "5 4", points: pts("td_loss") }]} /></Card>
              <Card className="flat"><LineChart title="Epsilon" xLabel="episode" yLabel="ε" series={[{ id: "e", label: "ε", color: "#009e73", marker: "triangle", points: pts("epsilon") }]} /></Card>
              <div style={{ gridColumn: "1 / -1" }}><SourceNote source={env.source} /></div>
            </div>
          );
        }}
      </Loaded>
    </>
  );
}

export function Observability() {
  const ds = useData();
  const s = useLoad(() => ds.getObservability(), []);
  return (
    <>
      <div className="eyebrow">Q3 · E4</div><h1 style={{ fontSize: "clamp(28px,4vw,40px)" }}>The price of partial observability</h1>
      <p className="lead">k = 0 means an agent sees only its own server; k = full means it also sees the mean wait of every other server. The gap between them is what local information is worth. The centralised reference (one agent seeing everything) was not built in this demo.</p>
      <Loaded state={s} what="k = 0 against k = full (E4)">
        {(d, env) => {
          const series: BarSeries[] = [
            ...d.learned.map((l) => ({ id: l.label.includes("k=0") ? "ddqn_k0" : "ddqn", label: l.label, color: l.label.includes("k=0") ? "#b57700" : "#e69f00", marker: l.label.includes("k=0") ? "diamond" : "circle", values: col(l.rows, "goodput_rps") })),
            ...(["sed_local_k0", "sed_local_full", "sed_global"] as const).filter((p) => d.references[p]).map((p) => ({ id: p, values: fromTable({ [p]: d.references[p] as Record<string, MetricRow> }, p, "goodput_rps") })),
          ];
          return (<Card className="flat"><BarsCI groups={RHOS} series={series} xLabel="offered load ρ" yLabel="goodput (req/s)" title="Goodput by visibility" /><SourceNote source={env.source} /></Card>);
        }}
      </Loaded>
    </>
  );
}

export function Traces() {
  const ds = useData();
  const s = useLoad(() => ds.getTraces(), []);
  return (
    <>
      <div className="eyebrow">the data</div><h1 style={{ fontSize: "clamp(28px,4vw,40px)" }}>The traffic traces</h1>
      <p className="lead">Azure LLM Inference 2023 (conversation) drives training and held-out traffic; Azure code is the burst test (not run in this demo). BurstGPT only supplies the chat-session parameters.</p>
      <Loaded state={s} what="Trace EDA">
        {(d, env) => {
          const names = Object.keys(d);
          const bars: BarSeries[] = [{ id: "ddqn", label: "c_a (burstiness of arrivals)", color: "#56b4e9", marker: "square", values: names.map((n) => ({ mean: (d[n] as any).c_a as number, ci: null, n: 1 })) }];
          return (
            <>
              <Card className="flat"><div className="tablewrap"><table>
                <thead><tr><th>trace</th><th>rows</th><th>duration (h)</th><th>mean rate (req/s)</th><th>c_a</th><th>prompt p50 / p99</th><th>output p50 / p99</th><th>failure rows</th></tr></thead>
                <tbody>{names.map((n) => { const r = d[n] as any; return <tr key={n}><td>{n}</td><td>{fmt(r.rows, 0)}</td><td>{fmt(r.duration_s / 3600, 2)}</td><td>{fmt(r.mean_rate_rps, 3)}</td><td>{fmt(r.c_a, 2)}</td><td>{fmt(r.prompt_tokens?.p50, 0)} / {fmt(r.prompt_tokens?.p99, 0)}</td><td>{fmt(r.output_tokens?.p50, 0)} / {fmt(r.output_tokens?.p99, 0)}</td><td>{fmt(r.failure_rows, 0)}</td></tr>; })}</tbody>
              </table></div></Card>
              <div style={{ marginTop: 24 }}><Card className="flat"><BarsCI groups={names} series={bars} xLabel="trace" yLabel="c_a (1 = Poisson-like)" title="Burstiness (c_a) by trace" height={300} /></Card></div>
              <SourceNote source={env.source} />
            </>
          );
        }}
      </Loaded>
    </>
  );
}

export function Method() {
  const ds = useData();
  const s = useLoad(() => ds.getMethod(), []);
  return (
    <>
      <div className="eyebrow">method</div><h1 style={{ fontSize: "clamp(28px,4vw,40px)" }}>How it is built</h1>
      <div className="grid g2" style={{ marginTop: 24 }}>
        <Card><h3>Service model</h3><p className="muted">T = a·(P − P<sub>cached</sub>·(1 − r)) + Σ t<sub>step</sub>(B), with t<sub>step</sub>(B) = t₀ + k·B and an interference multiplier from the busy neighbours. a, t₀, k, r (cached-token cost ratio) and the interference slowdown come only from the profiling fit.</p></Card>
        <Card><h3>Learning</h3><p className="muted">Independent Double DQN per server (MLP 7→64→64→3, Huber loss, Adam, target network, replay buffer, ε from 1.0 to 0.05, γ = 0.99 per decision). Rewards are credited at resolution with the decision-time state; an episode end is truncation.</p></Card>
        <Card><h3>Reward</h3><p className="muted">R<sub>SLA</sub> (+10 / −10 / −5 drop, shared by every agent that acted) − λ·C (serving agent: price × attributed busy seconds) − KV-pressure term − β·B<sub>t</sub> (cluster breach rate), plus small immediate costs for Forward and Defer.</p></Card>
        <Card><h3>Evaluation</h3><p className="muted">Greedy agents (ε = 0), held-out traffic untouched until the final run, 5 seeds, mean ± 95% t-interval. Baselines run on exactly the same traffic.</p></Card>
      </div>
      <h2 style={{ marginTop: 48 }}>Calibration</h2>
      <Loaded state={s} what="Method data">
        {(d, env) => {
          const fit = (d.profiling_fit as any)?.classes as Record<string, any> | undefined;
          return (
            <>
              {fit ? (
                <Card className="flat"><div className="tablewrap"><table>
                  <thead><tr><th>class</th><th>a (s/token)</th><th>t₀ (s)</th><th>k (s)</th><th>cache speedup</th><th>interference s (prefill / decode)</th><th>prefill R²</th></tr></thead>
                  <tbody>{Object.entries(fit).map(([c, f]) => <tr key={c}><td>{c}</td><td>{fmt(f.prefill.a * 1e3, 3)}e-3</td><td>{fmt(f.decode.t0, 4)}</td><td>{fmt(f.decode.k, 4)}</td><td>{fmt(f.cache.cache_speedup, 1)}x</td><td>{fmt(f.interference.prefill.s, 2)} / {fmt(f.interference.decode.s, 2)}</td><td>{fmt(f.prefill.r2, 3)}</td></tr>)}</tbody>
                </table></div></Card>
              ) : <div className="notrun"><b>Profiling fit: not run</b>No fit_output.json found.</div>}
              <p className="muted" style={{ marginTop: 8 }}>5 repeats per point (the plan asks for 10); one machine ({String((d.profiling_machine as any)?.chip ?? "n/a")}).</p>
              <h2 style={{ marginTop: 48 }}>Decision records</h2>
              <Card className="flat"><div className="tablewrap"><table><thead><tr><th>ADR</th><th>title</th><th>status</th></tr></thead>
                <tbody>{d.adrs.map((a) => <tr key={a.id}><td>{a.id}</td><td style={{ textAlign: "left", whiteSpace: "normal" }}>{a.title}</td><td>{a.status || "n/a"}</td></tr>)}</tbody></table></div></Card>
              <SourceNote source={env.source} />
            </>
          );
        }}
      </Loaded>
    </>
  );
}

export { Marker, styleOf };
