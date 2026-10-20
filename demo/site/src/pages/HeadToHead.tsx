// Head-to-head page, RECORDED mode (Sh.H2, ADR-025): a baseline and the learned agents replayed side by side
// on the IDENTICAL held-out slice. Nothing is simulated here: every tile is computed from the recorded event
// log of one seed up to the current time, and the final summary is read from the paired evaluation files.
import { useEffect, useMemo, useRef, useState } from "react";
import { Card, Loaded, NotRun, Num, SourceNote, fmt, styleOf, useData, useLoad, useReducedMotion } from "../ui";
import { ReplayStage } from "../viz/ReplayStage";
import type { Envelope, Frame, H2HPolicy, H2HReplay, HeadToHeadData, PairedDiff } from "../data/types";

const TARGET_PLAY_S = 40; // at 1x a whole episode takes this many real seconds
const DEFAULT_LAYOUT = ["fast_expensive", "slow_cheap", "fast_expensive", "slow_cheap"];
const EMPTY: Frame[] = [];
const ZERO: Cum = { arrived: 0, met: 0, late: 0, dropped: 0, done: 0, cost: 0, ttftN: 0 };

const HIGHER_BETTER: Record<string, boolean> = { goodput_rps: true, sla_attainment: true, drop_rate: false, ttft_p95: false, cost_per_request: false };
const METRIC_LABEL: Record<string, string> = {
  goodput_rps: "goodput (req/s)",
  ttft_p95: "p95 TTFT (s)",
  sla_attainment: "SLA attainment",
  cost_per_request: "cost per request (synthetic price)",
  drop_rate: "drop rate",
};
const SUMMARY_COLS = ["goodput_rps", "ttft_p95", "sla_attainment", "cost_per_request", "drop_rate"];

/** Index of the last frame at or before simulated time t. */
function frameAt(frames: Frame[], t: number): number {
  let lo = 0, hi = frames.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (frames[mid].t <= t) lo = mid; else hi = mid - 1;
  }
  return Math.max(lo, 0);
}

type Cum = { arrived: number; met: number; late: number; dropped: number; done: number; cost: number; ttftN: number };

/** Running totals after each frame, from the event log only (met / late / dropped come from each resolve). */
function useCumulative(frames: Frame[]) {
  return useMemo(() => {
    const cum: Cum[] = [];
    const ttfts: number[] = [];
    const c: Cum = { arrived: 0, met: 0, late: 0, dropped: 0, done: 0, cost: 0, ttftN: 0 };
    for (const f of frames) {
      c.arrived += f.arrivals.length;
      for (const r of f.resolves) {
        if (r.ok) c.met++;
        else if (r.status === "dropped") c.dropped++;
        else c.late++;
        if (r.status === "done") {
          c.done++;
          if (r.cost != null) c.cost += r.cost;
          if (r.ttft != null) ttfts.push(r.ttft);
        }
      }
      c.ttftN = ttfts.length;
      cum.push({ ...c });
    }
    return { cum, ttfts };
  }, [frames]);
}

function p95(values: number[], n: number): number | null {
  if (n < 1) return null;
  const s = values.slice(0, n).sort((a, b) => a - b);
  return s[Math.min(s.length - 1, Math.ceil(0.95 * s.length) - 1)];
}

function Tile({ k, v, unit, title }: { k: string; v: number | null; unit?: string; title: string }) {
  return (
    <div className="tile" title={title}>
      <div className="k">{k}</div>
      <div className="v">{v == null ? <span className="muted">n/a</span> : <>{fmt(v, v >= 100 ? 0 : 2)}{unit && <small> {unit}</small>}</>}</div>
    </div>
  );
}

function PaneBody({ d, env, meta, t, dim, waiting }: { d: H2HReplay; env: Envelope<H2HReplay>; meta: H2HPolicy; t: number; dim: boolean; waiting: boolean }) {
  const frames = d.frames ?? EMPTY;
  const { cum, ttfts } = useCumulative(frames);
  const idx = frameAt(frames, t);
  const frame = frames[idx];
  const style = styleOf(meta.id);
  const shown = waiting ? ZERO : (cum[idx] ?? ZERO);
  const elapsed = waiting || !frame ? 0 : frame.t;
  const resolved = shown.met + shown.late + shown.dropped;
  const tip = (what: string) => `${what}: computed from the recorded event log (${env.source && "files" in (env.source as object) ? ((env.source as { files?: string[] }).files ?? [""])[0] : ""}) up to t = ${elapsed.toFixed(0)} s`;
  const ttftP95 = useMemo(() => p95(ttfts, shown.ttftN), [ttfts, shown.ttftN]);
  if (!frame) return <NotRun what={meta.label} reason="its event log has no frames." />;
  return (
    <div className={`pane ${dim ? "dim" : ""}`}>
      <Card className="flat">
        <div className="pane-head">
          <b style={{ color: style.color }}>{meta.label}</b>
          <span className="pill">{meta.kind === "learned" ? "learned" : "baseline"} · {meta.mode === "agents" ? "per-server agents" : "global view"}</span>
        </div>
        <div className="stage-wrap" aria-label={`${meta.label} replay`}>
          <ReplayStage frame={waiting ? { ...frame, arrivals: [], acts: [], resolves: [], forwards: [] } : frame} layout={d.layout ?? DEFAULT_LAYOUT} mode={d.mode} compact />
        </div>
        <div className="tiles" aria-label={`${meta.label} tiles so far`}>
          <Tile k="goodput" v={elapsed > 0 ? shown.met / elapsed : null} unit="req/s" title={tip("goodput = requests that met the SLA / elapsed seconds")} />
          <Tile k="p95 TTFT" v={ttftP95} unit="s" title={tip("95th percentile time to first token of requests completed so far")} />
          <Tile k="SLA met" v={resolved > 0 ? shown.met / resolved : null} title={tip("share of resolved requests that met both targets")} />
          <Tile k="cost / req" v={shown.done > 0 ? shown.cost / shown.done : null} title={tip("synthetic price per busy second x busy seconds, per completed request")} />
          <Tile k="drops" v={shown.dropped} title={tip("requests dropped so far")} />
        </div>
        <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
          {waiting ? "waiting for its turn" : `t = ${elapsed.toFixed(0)} s · ${shown.arrived} arrived · ${resolved} resolved so far`}
          {d.events?.truncated ? " · event log truncated at its cap" : ""}
        </div>
        <SourceNote source={env.source} />
      </Card>
    </div>
  );
}

function PaneState({ state, meta, t, dim, waiting }: { state: { env?: Envelope<H2HReplay>; error?: string }; meta: H2HPolicy; t: number; dim: boolean; waiting: boolean }) {
  return (
    <Loaded state={state} what={`Replay of ${meta.label}`}>
      {(d, env) => <PaneBody d={d} env={env} meta={meta} t={t} dim={dim} waiting={waiting} />}
    </Loaded>
  );
}

function judge(d: PairedDiff, higherBetter: boolean): { word: string; cls: "win" | "lose" | "tie"; icon: string } {
  if (!d.excludes_zero) return { word: "no clear difference", cls: "tie", icon: "＝" };
  return (d.mean_diff > 0) === higherBetter ? { word: "learned agents better", cls: "win", icon: "▲" } : { word: "learned agents worse", cls: "lose", icon: "▼" };
}

function Summary({ data, rho, learned, baseline }: { data: HeadToHeadData; rho: string; learned: H2HPolicy; baseline: H2HPolicy }) {
  const row = data.rhos[rho];
  const diffs = row.paired_diff[baseline.id];
  const lg = row.summary[learned.id]?.goodput_rps;
  return (
    <Card className="flat" style={{ marginTop: 16 }}>
      <div className="label">final summary · load {rho} · all {row.seeds.length} seeds · mean ± 95% CI</div>
      <div className="tablewrap">
        <table>
          <thead>
            <tr><th>policy</th>{SUMMARY_COLS.map((m) => <th key={m}>{METRIC_LABEL[m]}</th>)}</tr>
          </thead>
          <tbody>
            {data.policies.map((p) => (
              <tr key={p.id} className={p.kind === "learned" ? "learned-row" : ""}>
                <td><b style={{ color: styleOf(p.id).color }}>{p.label}</b></td>
                {SUMMARY_COLS.map((m) => <td key={m}><Num m={row.summary[p.id]?.[m]} digits={m === "sla_attainment" || m === "drop_rate" ? 3 : 2} /></td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h3 style={{ margin: "18px 0 6px" }}>Learned agents against {baseline.label}, same traffic, same seeds</h3>
      {diffs ? (
        <div className="tablewrap">
          <table>
            <thead><tr><th>metric</th><th>learned − baseline (mean, paired 95% interval)</th><th>reading</th></tr></thead>
            <tbody>
              {SUMMARY_COLS.map((m) => {
                const d = diffs[m];
                if (!d) return null;
                const j = judge(d, HIGHER_BETTER[m]);
                return (
                  <tr key={m}>
                    <td>{METRIC_LABEL[m]}</td>
                    <td className="mono">{d.mean_diff >= 0 ? "+" : ""}{fmt(d.mean_diff, 3)} [{fmt(d.ci95[0], 3)}, {fmt(d.ci95[1], 3)}] <span className="muted">n = {d.n}</span></td>
                    <td><span className={`pill ${j.cls === "win" ? "ok" : j.cls === "lose" ? "warn" : ""}`}>{j.icon} {j.word}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : <NotRun what="Paired difference" reason="needs at least two shared seeds." />}
      <h3 style={{ margin: "18px 0 6px" }}>Does it beat SED?</h3>
      {data.policies.filter((p) => p.kind === "baseline" && p.id.startsWith("sed")).map((p) => {
        const b = row.summary[p.id]?.goodput_rps;
        if (!lg || !b || lg.mean == null || b.mean == null) return null;
        const lo = lg.mean - (lg.ci ?? 0), hi = lg.mean + (lg.ci ?? 0), blo = b.mean - (b.ci ?? 0), bhi = b.mean + (b.ci ?? 0);
        const win = lo > bhi, lose = hi < blo;
        const head = win ? "▲ Yes, it beats it" : lose ? "▼ No, it is worse" : "＝ It matches it, it does not beat it";
        const tail = win
          ? "The 95% intervals do not overlap."
          : lose
            ? "The learned agents are lower and the intervals do not overlap."
            : "The 95% intervals overlap: a tie, not a win.";
        return (
          <div key={p.id} className={`verdict ${win ? "win" : lose ? "lose" : "tie"}`}>
            <b>{head}</b>: against {p.label} on goodput the learned agents have {fmt(lg.mean, 3)} ± {fmt(lg.ci, 3)} and the baseline {fmt(b.mean, 3)} ± {fmt(b.ci, 3)} req/s. {tail}
          </div>
        );
      })}
      <div className="muted" style={{ fontSize: 12.5, marginTop: 8 }}>
        Slice <span className="mono">{row.slice_id}</span> · seeds {row.seeds.join(", ")} · config <span className="mono">{row.config_hash}</span>. The page shows every result as measured; a non-win is shown as a non-win.
      </div>
    </Card>
  );
}

function Comparison({ data, env, learned, baselines }: { data: HeadToHeadData; env: Envelope<HeadToHeadData>; learned: H2HPolicy; baselines: H2HPolicy[] }) {
  const ds = useData();
  const reduced = useReducedMotion();
  const rhos = Object.keys(data.rhos);
  const [rho, setRho] = useState(rhos.includes("0.8") ? "0.8" : rhos[0]);
  const [baseId, setBaseId] = useState(baselines.find((p) => p.id === "sed_global")?.id ?? baselines[0].id);
  const [mode, setMode] = useState<"side" | "seq">("side");
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(2);
  const last = useRef(0);
  const baseMeta = baselines.find((p) => p.id === baseId) ?? baselines[0];

  const rb = useLoad(() => ds.getH2HReplay(baseId, rho), [baseId, rho]);
  const rl = useLoad(() => ds.getH2HReplay(learned.id, rho), [learned.id, rho]);
  const endOf = (s: { env?: Envelope<H2HReplay> }) => { const f = s.env?.data?.frames; return f && f.length ? f[f.length - 1].t : 0; };
  const tMax = Math.max(endOf(rb), endOf(rl));
  const span = mode === "seq" ? 2 * tMax : tMax;

  useEffect(() => { setT(0); setPlaying(false); }, [baseId, rho, mode]);
  // ?at=0.6 opens the page 60% into the episode (deep link for screenshots and for pointing at a moment)
  const jumped = useRef(false);
  useEffect(() => {
    const at = Number(new URLSearchParams(window.location.search).get("at"));
    if (!jumped.current && span > 0 && at > 0 && at <= 1) { jumped.current = true; setT(at * span); }
  }, [span]);

  useEffect(() => {
    if (!playing || span <= 0) return;
    const advance = (dtSeconds: number) => setT((cur) => { const n = Math.min(cur + dtSeconds * (span / (mode === "seq" ? 2 : 1) / TARGET_PLAY_S) * speed, span); if (n >= span) setPlaying(false); return n; });
    if (reduced) { // reduced motion: discrete steps instead of a smooth animation
      const id = window.setInterval(() => advance(0.5), 500);
      return () => window.clearInterval(id);
    }
    let raf = 0;
    last.current = performance.now();
    const loop = (now: number) => { advance((now - last.current) / 1000); last.current = now; raf = requestAnimationFrame(loop); };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, span, mode, reduced]);

  const phase = mode === "seq" && t >= tMax ? 1 : 0;
  const tBase = mode === "side" ? t : phase === 0 ? t : tMax;
  const tLearn = mode === "side" ? t : phase === 1 ? t - tMax : 0;
  const row = data.rhos[rho];

  const onKey = (e: React.KeyboardEvent) => {
    const step = Math.max(span / 200, 0.1);
    if (e.key === " ") { e.preventDefault(); setPlaying((p) => !p); }
    if (e.key === "ArrowRight") setT((x) => Math.min(x + step, span));
    if (e.key === "ArrowLeft") setT((x) => Math.max(x - step, 0));
  };

  return (
    <div onKeyDown={onKey}>
      <div className="controls">
        <label>load ρ <select value={rho} onChange={(e) => setRho(e.target.value)} aria-label="load rho">{rhos.map((r) => <option key={r}>{r}</option>)}</select></label>
        <label>compare against <select value={baseId} onChange={(e) => setBaseId(e.target.value)} aria-label="baseline policy">{baselines.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}</select></label>
        <span className="seg" role="group" aria-label="playback mode">
          <button aria-pressed={mode === "side"} onClick={() => setMode("side")}>side by side</button>
          <button aria-pressed={mode === "seq"} onClick={() => setMode("seq")}>one after the other</button>
        </span>
        <button className="primary" onClick={() => { if (!playing && t >= span) setT(0); setPlaying((p) => !p); }} disabled={span <= 0} aria-label={playing ? "pause" : "play"}>{playing ? "Pause" : t >= span && span > 0 ? "Replay" : "Play"}</button>
        <label>speed <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} aria-label="speed">{[0.5, 1, 2, 4, 8, 16].map((s) => <option key={s} value={s}>{s}x</option>)}</select></label>
        <span className="muted"><span className="kbd">space</span> play/pause · <span className="kbd">←</span><span className="kbd">→</span> step{reduced ? " · reduced motion: stepped" : ""}</span>
      </div>
      <div className="chips" aria-label="provenance">
        <span className="pill accent" title="hash of the request list both policies were given">same traffic · slice {row.slice_id}</span>
        <span className="pill">replay of seed {data.event_seed} · {row.seeds.length} seeds in the summary</span>
        <span className="pill" title="hash of the simulator config, calibration, load and seed list">config {row.config_hash}</span>
        <span className="pill">{data.slice_split} traffic · ε = 0 · nothing tuned on this slice</span>
      </div>
      <div className="h2h-panes" tabIndex={0} aria-label="head to head replay, space to play or pause">
        <PaneState state={rb} meta={baseMeta} t={tBase} dim={mode === "seq" && phase === 1} waiting={false} />
        <PaneState state={rl} meta={learned} t={tLearn} dim={mode === "seq" && phase === 0} waiting={mode === "seq" && phase === 0 && t === 0} />
      </div>
      <input type="range" min={0} max={Math.max(span, 0.001)} step={Math.max(span / 1000, 0.01)} value={t} onChange={(e) => { setPlaying(false); setT(Number(e.target.value)); }} aria-label="time scrubber" style={{ marginTop: 12 }} disabled={span <= 0} />
      <div className="muted" style={{ fontSize: 12 }}>
        {mode === "seq" ? `${phase === 0 ? baseMeta.label : learned.label} is playing · ` : ""}t = {(mode === "seq" ? (phase === 0 ? tBase : tLearn) : t).toFixed(0)} s of {tMax.toFixed(0)} s
      </div>
      <Summary data={data} rho={rho} learned={learned} baseline={baseMeta} />
      <div style={{ marginTop: 12 }}><SourceNote source={env.source} /></div>
    </div>
  );
}

export function HeadToHead() {
  const ds = useData();
  const state = useLoad(() => ds.getHeadToHead(), []);
  return (
    <>
      <div className="eyebrow">replay of recorded runs on identical traffic</div>
      <h1 style={{ fontSize: "clamp(28px,4vw,40px)" }}>Learned agents against the baselines</h1>
      <p className="lead">Each pane replays one policy on the very same held-out requests. These are recordings of the calibrated simulation of the cluster, not real servers and not a live run. The tiles count up from the event log; the table below them is the result over all seeds.</p>
      <Loaded state={state} what="Head-to-head comparison">
        {(data, env) => {
          const learned = data.policies.find((p) => p.kind === "learned");
          const baselines = data.policies.filter((p) => p.kind === "baseline");
          if (!learned || !baselines.length || !Object.keys(data.rhos).length) return <NotRun what="Head-to-head comparison" reason="the paired evaluation has no learned policy or no baseline." />;
          return <Comparison data={data} env={env} learned={learned} baselines={baselines} />;
        }}
      </Loaded>
    </>
  );
}
