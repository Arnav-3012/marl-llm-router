import { useEffect, useMemo, useRef, useState } from "react";
import { Card, Loaded, SourceNote, useData, useLoad, useReducedMotion } from "../ui";
import { ReplayStage } from "../viz/ReplayStage";
import type { Frame } from "../data/types";

const POLICIES = [["ddqn", "DDQN agents"], ["sed_local", "SED local (k=full)"], ["cache_aware", "Cache-aware local"], ["sed_global", "SED global"], ["random", "Random"]];
const RHOS = ["0.5", "0.8", "0.95"];
const ACT = ["Accept", "Forward", "Defer"];

export function Replay() {
  const ds = useData();
  const reduced = useReducedMotion();
  const [policy, setPolicy] = useState("ddqn");
  const [rho, setRho] = useState("0.8");
  const state = useLoad(() => ds.getReplayMeta(policy, rho), [policy, rho]);
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(2);
  const acc = useRef(0);

  const frames: Frame[] = state.env?.data?.frames ?? [];
  const layout = state.env?.data?.layout ?? ["fast_expensive", "slow_cheap", "fast_expensive", "slow_cheap"];
  useEffect(() => { setIdx(0); setPlaying(false); }, [policy, rho]);

  // running totals per frame (computed once per episode)
  const totals = useMemo(() => {
    let arrived = 0, ok = 0, missed = 0;
    return frames.map((f) => { arrived += f.arrivals.length; ok += f.resolves.filter((r) => r.ok).length; missed += f.resolves.filter((r) => !r.ok).length; return { arrived, ok, missed }; });
  }, [frames]);
  const depth = useMemo(() => frames.map((f) => (f.queue ?? []).reduce((a, b) => a + b, 0)), [frames]);

  useEffect(() => {
    if (!playing || !frames.length) return;
    let raf = 0, last = performance.now();
    const loop = (now: number) => {
      acc.current += ((now - last) / 1000) * 24 * speed; last = now;
      const adv = Math.floor(acc.current);
      if (adv > 0) { acc.current -= adv; setIdx((i) => { const n = Math.min(i + adv, frames.length - 1); if (n >= frames.length - 1) setPlaying(false); return n; }); }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, frames.length]);

  const frame = frames[Math.min(idx, Math.max(frames.length - 1, 0))];
  const tot = totals[Math.min(idx, Math.max(totals.length - 1, 0))];
  const recent = useMemo(() => {
    const out: string[] = [];
    for (let i = Math.max(0, idx - 6); i <= idx && frames[i]; i++) {
      const f = frames[i];
      f.acts.forEach((a) => out.push(`t=${f.t.toFixed(1)}s  req ${a.req} → agent ${a.agent}: ${ACT[a.action]}`));
      f.resolves.forEach((r) => out.push(`t=${f.t.toFixed(1)}s  req ${r.req} ${r.ok ? "met its SLA ✓" : `missed (${r.status}) ✕`}`));
    }
    return out.slice(-6);
  }, [frames, idx]);

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === " ") { e.preventDefault(); setPlaying((p) => !p); }
    if (e.key === "ArrowRight") setIdx((i) => Math.min(i + 1, frames.length - 1));
    if (e.key === "ArrowLeft") setIdx((i) => Math.max(i - 1, 0));
  };

  return (
    <>
      <div className="eyebrow">replay of a recorded episode</div>
      <h1 style={{ fontSize: "clamp(28px,4vw,40px)" }}>Watch the cluster route traffic</h1>
      <p className="lead">This is a recording of one held-out episode (seed 0) written by the simulator, not a live simulation. Pick a policy and a load and press play.</p>
      <div className="controls">
        <label>policy <select value={policy} onChange={(e) => setPolicy(e.target.value)} aria-label="policy">{POLICIES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
        <label>load ρ <select value={rho} onChange={(e) => setRho(e.target.value)} aria-label="load rho">{RHOS.map((r) => <option key={r}>{r}</option>)}</select></label>
        <button className="primary" onClick={() => setPlaying((p) => !p)} disabled={!frames.length} aria-label={playing ? "pause" : "play"}>{playing ? "Pause" : "Play"}</button>
        <label>speed <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} aria-label="speed">{[0.5, 1, 2, 4, 8, 16].map((s) => <option key={s} value={s}>{s}x</option>)}</select></label>
        <span className="muted"><span className="kbd">space</span> play/pause · <span className="kbd">←</span><span className="kbd">→</span> step{reduced ? " · reduced motion: stepped" : ""}</span>
      </div>
      <Loaded state={state} what={`Replay (${policy}, ρ ${rho})`}>
        {(_d, env) => frame && tot && (
          <div className="grid g2" style={{ gridTemplateColumns: "minmax(0,2fr) minmax(260px,1fr)" }} onKeyDown={onKey}>
            <Card className="flat">
              <div className="stage-wrap" tabIndex={0} aria-label="replay stage, space to play or pause">
                <ReplayStage frame={frame} layout={layout} mode={policy === "sed_global" || policy === "random" ? "global" : "agents"} />
              </div>
              <input type="range" min={0} max={Math.max(frames.length - 1, 0)} value={idx} onChange={(e) => { setPlaying(false); setIdx(Number(e.target.value)); }} aria-label="time scrubber" />
              <svg viewBox="0 0 400 40" className="chart" aria-label="total queue depth over the episode" role="img">
                <polyline fill="none" stroke="#7170ff" strokeWidth="1.5" points={depth.map((v, i) => `${(i / Math.max(depth.length - 1, 1)) * 400},${38 - (v / Math.max(...depth, 1)) * 34}`).join(" ")} />
                <line x1={(idx / Math.max(frames.length - 1, 1)) * 400} x2={(idx / Math.max(frames.length - 1, 1)) * 400} y1="0" y2="40" stroke="#f7f8f8" />
              </svg>
              <div className="muted" style={{ fontSize: 12 }}>t = {frame.t.toFixed(1)} s · frame {idx + 1} / {frames.length} · total queue depth over time</div>
            </Card>
            <div className="grid" style={{ alignContent: "start" }}>
              <div className="kpis">
                <Card><div className="label">arrived</div><div className="stat">{tot.arrived}</div></Card>
                <Card><div className="label">met SLA ✓</div><div className="stat" style={{ color: "#7be0c3" }}>{tot.ok}</div></Card>
                <Card><div className="label">missed ✕</div><div className="stat" style={{ color: "#ffb37a" }}>{tot.missed}</div></Card>
              </div>
              <Card className="flat"><div className="label">recent decisions</div><div className="ticker">{recent.length ? recent.map((l, i) => <div key={i}>{l}</div>) : "nothing yet"}</div></Card>
              <div className="muted" style={{ fontSize: 12.5 }}>● Accept · → Forward · ⏱ Defer. Fast servers are solid squares, slow ones dashed circles; the ring is KV-cache fullness (red above 80%). Counts are tallies of this recording only.</div>
              <SourceNote source={env.source} />
            </div>
          </div>
        )}
      </Loaded>
    </>
  );
}
