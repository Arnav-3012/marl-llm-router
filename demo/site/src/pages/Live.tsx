// Live mode: a guided live test. One button runs the whole check on this machine and narrates it like a chat; the cluster is
// drawn live next to it and the results land underneath. Works only while the local router is running; the recorded pages never
// depend on it. A mock backend is labelled MOCK everywhere: it rehearses the plumbing, it is not a result.
import { useCallback, useEffect, useRef, useState } from "react";
import { Card, ChartFrame, Info, PageHead, fmt } from "../ui";
import { ReplayStage } from "../viz/ReplayStage";
import type { Frame } from "../data/types";
import { Link } from "../router";

const API = new URLSearchParams(window.location.search).get("api") ?? "http://127.0.0.1:8000";
const ALL: [string, string][] = [["sed_global", "SED global"], ["route_to_fast_shed", "Hand-written rule + shed"], ["ddqn_agents", "Learned agents"], ["route_to_fast", "Hand-written rule"], ["random", "Random"]];
const DEFAULT = ["sed_global", "route_to_fast_shed", "ddqn_agents"];

type Health = { status: string; mode: string; time_scale: number; backends: { name: string; class: string; url: string; up: boolean }[]; running: string | null };
type Msg = { i: number; at: string; kind: "info" | "ok" | "warn" | "error"; text: string };
type Row = { policy: string; label: string; run_id: string; slice: string; metrics: any };
type Check = { state: string; messages: Msg[]; n: number; rows: Row[]; current_run: string | null; opts?: any };

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API}${path}`, { ...init, headers: { "Content-Type": "application/json" } });
  if (!r.ok) throw new Error((await r.json().catch(() => ({ detail: r.statusText }))).detail ?? r.statusText);
  return r.json();
}

const ICON: Record<Msg["kind"], string> = { info: "·", ok: "✓", warn: "!", error: "✕" };

export function Live() {
  const [health, setHealth] = useState<Health | null>(null);
  const [down, setDown] = useState(false);
  const [state, setState] = useState("idle");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [rows, setRows] = useState<Row[]>([]);
  const [frames, setFrames] = useState<Frame[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [sent, setSent] = useState<{ sent: number; of: number } | null>(null);
  const [err, setErr] = useState("");
  const [seconds, setSeconds] = useState(60);
  const [rho, setRho] = useState(0.8);
  const [seed, setSeed] = useState(0);
  const [policies, setPolicies] = useState<string[]>(DEFAULT);
  const [chat, setChat] = useState({ prompt: "Explain in two sentences why the sky is blue.", reply: null as any, busy: false, policy: "sed_local_full" });
  const n = useRef(0);
  const lastTick = useRef(-1);
  const curRun = useRef<string | null>(null);
  const feed = useRef<HTMLDivElement>(null);
  const auto = useRef(new URLSearchParams(window.location.search).get("autostart") === "1");

  useEffect(() => {
    let live = true;
    const ping = () => api<Health>("/health").then((h) => { if (live) { setHealth(h); setDown(false); } }).catch(() => { if (live) setDown(true); });
    ping();
    const id = setInterval(ping, 3000);
    return () => { live = false; clearInterval(id); };
  }, []);

  const poll = useCallback(async () => {
    try {
      const s = await api<Check>(`/livecheck/status?since=${n.current}`);
      if (s.messages.length) { n.current = s.n; setMsgs((m) => [...m, ...s.messages]); }
      setState(s.state); setRows(s.rows);
      if (s.current_run && s.current_run !== curRun.current) { curRun.current = s.current_run; lastTick.current = -1; setFrames([]); setRunId(s.current_run); }
      const id = curRun.current;
      if (id) {
        const f = await api<{ frames: Frame[] }>(`/runs/${id}/frames?since=${lastTick.current}&cap=2000`).catch(() => ({ frames: [] as Frame[] }));
        if (f.frames.length) { lastTick.current = f.frames[f.frames.length - 1].tick; setFrames((old) => [...old, ...f.frames].slice(-3000)); }
        if (s.state === "running") api<any>("/simulate/status").then((x) => x.run_id === id && setSent({ sent: x.sent, of: x.of })).catch(() => undefined);
      }
    } catch { /* the next poll retries */ }
  }, []);
  useEffect(() => { const id = setInterval(poll, 800); return () => clearInterval(id); }, [poll]);
  useEffect(() => { feed.current?.scrollTo({ top: feed.current.scrollHeight, behavior: "smooth" }); }, [msgs.length]);

  const start = useCallback(async () => {
    setErr(""); setMsgs([]); setRows([]); setFrames([]); n.current = 0; curRun.current = null; setRunId(null); setSent(null);
    try { await api("/livecheck/start", { method: "POST", body: JSON.stringify({ seconds, rho, seed, policies }) }); setState("running"); }
    catch (e) { setErr(String((e as Error).message)); }
  }, [seconds, rho, seed, policies]);
  useEffect(() => { if (auto.current && health && health.status === "ok" && state === "idle") { auto.current = false; void start(); } });
  const stop = () => api("/livecheck/stop", { method: "POST" }).catch(() => undefined);
  const servers = (what: "start" | "stop") => {
    if (what === "stop" && !window.confirm("Stop the four llama-servers?")) return;
    if (what === "start" && !window.confirm("Start the four llama-servers on this machine? It takes about a minute and uses the CPU and GPU until you stop them.")) return;
    api(`/servers/${what}`, { method: "POST" }).catch((e) => setErr(String(e.message)));
  };
  const send = async () => {
    setChat((c) => ({ ...c, busy: true, reply: null })); setErr("");
    try { const r = await api<any>("/chat", { method: "POST", body: JSON.stringify({ prompt: chat.prompt, n_predict: 64, policy: chat.policy }) }); setChat((c) => ({ ...c, reply: r, busy: false })); }
    catch (e) { setErr(String((e as Error).message)); setChat((c) => ({ ...c, busy: false })); }
  };

  const layout = health?.backends.map((b) => b.class) ?? ["fast_expensive", "slow_cheap", "fast_expensive", "slow_cheap"];
  const arrived = frames.reduce((a, f) => a + f.arrivals.length, 0);
  const res = frames.flatMap((f) => f.resolves);
  const ok = res.filter((r) => r.ok).length;
  const ttfts = res.map((r) => r.ttft).filter((x): x is number => typeof x === "number").sort((a, b) => a - b);
  const p95 = ttfts.length ? ttfts[Math.min(ttfts.length - 1, Math.floor(0.95 * ttfts.length))] : null;
  const frame = frames[frames.length - 1];
  const mock = health?.mode === "mock";
  const real = health?.mode === "real";
  const running = state === "running";
  const best = rows.length > 1 ? Math.max(...rows.map((r) => r.metrics.goodput_rps)) : null;
  const top = Math.max(0.001, ...rows.map((r) => r.metrics.goodput_rps));
  const toggle = (k: string) => setPolicies((p) => (p.includes(k) ? p.filter((x) => x !== k) : [...p, k]));

  return (
    <>
      <PageHead eyebrow="Live test · on this machine" title="Run the real test and watch it happen">
        <p className="lead">One button checks the servers, measures capacity if needed, then replays the same held-out traffic through each policy, one after the other, and shows what happens as it happens. It needs the local router to be running; every other page works without it.</p>
      </PageHead>
      {down && <div className="notrun" role="status"><b>The live backend is not running</b>Start it as described in <code>docs/DEMO.md</code>. The recorded pages, <Link to="/headtohead">Head to head</Link>, <Link to="/replay">Replay</Link> and <Link to="/stress">Stress tests</Link>, show saved runs of the same experiment and always work.</div>}
      {health && mock && <div className="banner" role="status">MOCK BACKEND: simulated stand-ins with sped-up time. This rehearses the plumbing; it is not a result.</div>}
      {err && <div className="notrun" role="alert"><b>Error</b>{err}</div>}

      {health && (
        <>
          <div className="chips" aria-label="servers">
            {health.backends.map((b) => <span key={b.name} className={`pill ${b.up ? "ok" : "warn"}`}><span className="dot" />{b.name} · {b.class.replace("_", " ")} · {b.up ? "up" : "down"}</span>)}
            {real && <><button className="ghost" onClick={() => servers("start")} disabled={running}>Start servers</button><button className="ghost" onClick={() => servers("stop")} disabled={running}>Stop servers</button></>}
          </div>

          <div className="live-grid">
            <section className="assistant" aria-label="live test assistant">
              <header className="as-head"><span className="as-avatar" aria-hidden="true">R</span><div><b>Live test assistant</b><small>{running ? "running…" : state === "done" ? "finished" : state === "failed" ? "stopped on a problem" : state === "stopped" ? "stopped" : "ready"}</small></div></header>
              <div className="as-feed" ref={feed} role="log" aria-live="polite">
                {msgs.length === 0 && <div className="as-empty">Press <b>Start live test</b>. I will tell you what I am doing at every step: checking the servers, one short request, capacity, then one run per policy on the same traffic, and a comparison at the end.</div>}
                {msgs.map((m) => <div key={m.i} className={`as-msg ${m.kind}`}><span className="as-ic" aria-hidden="true">{ICON[m.kind]}</span><span className="as-text">{m.text}</span><time>{m.at}</time></div>)}
                {running && <div className="as-typing" aria-hidden="true"><i /><i /><i /></div>}
              </div>
              <footer className="as-foot">
                <button className="primary" onClick={start} disabled={running}>{running ? "Running…" : msgs.length ? "Run again" : "Start live test"}</button>
                <button onClick={stop} disabled={!running}>Stop</button>
                <details className="as-opts"><summary>Options</summary>
                  <div className="as-optgrid">
                    <label>seconds per run <select value={seconds} onChange={(e) => setSeconds(Number(e.target.value))}>{[30, 60, 120, 300].map((s) => <option key={s}>{s}</option>)}</select></label>
                    <label>load ρ <select value={rho} onChange={(e) => setRho(Number(e.target.value))}>{[0.3, 0.5, 0.8, 0.95].map((r) => <option key={r}>{r}</option>)}</select></label>
                    <label>seed <select value={seed} onChange={(e) => setSeed(Number(e.target.value))}>{[0, 1, 2, 3, 4].map((s) => <option key={s}>{s}</option>)}</select></label>
                  </div>
                  <div className="as-pols" role="group" aria-label="policies to run">{ALL.map(([k, l]) => <button key={k} type="button" aria-pressed={policies.includes(k)} onClick={() => toggle(k)}>{l}</button>)}</div>
                  <p className="muted" style={{ fontSize: 12.5, margin: "8px 0 0" }}>Policies run one after the other on identical requests. Load ρ is a share of this cluster's own capacity.</p>
                </details>
              </footer>
            </section>

            <div className="stage-col">
              <ChartFrame title={running && runId ? "The cluster right now" : "The cluster"} tip="The same picture as the Replay page, drawn live: each router agent decides, queues build and servers answer. Fast servers are solid squares, slow ones dashed circles. Larger dots are longer prompts.">
                {frame ? <ReplayStage frame={frame} layout={layout} mode="agents" /> : <div className="notrun"><b>Nothing running</b>The cluster appears here when a run starts.</div>}
                <div className="kpis">
                  <div className="tile"><div className="k">arrived</div><div className="v">{arrived}</div></div>
                  <div className="tile"><div className="k">met both targets</div><div className="v">{ok}</div></div>
                  <div className="tile"><div className="k">missed or dropped</div><div className="v">{res.length - ok}</div></div>
                  <div className="tile"><div className="k">first token p95</div><div className="v">{p95 == null ? "n/a" : `${fmt(p95, 2)} s`}</div></div>
                </div>
                {running && sent && <div className="muted" style={{ fontSize: 12.5 }}>{sent.sent} of {sent.of} requests sent in this run</div>}
              </ChartFrame>
            </div>
          </div>

          {rows.length > 0 && (
            <section style={{ marginTop: 28 }} aria-label="results">
              <h2>Results of this live test</h2>
              <div className="res-grid">
                {rows.map((r) => {
                  const m = r.metrics;
                  return (
                    <Card key={r.run_id} className={`res-card ${best != null && m.goodput_rps === best ? "best" : ""}`}>
                      <div className="label">{r.label}</div>
                      <div className="stat">{fmt(m.goodput_rps, 3)} <small>req/s goodput</small></div>
                      <div className="res-bar" aria-hidden="true"><i style={{ width: `${(m.goodput_rps / top) * 100}%` }} /></div>
                      <dl className="res-dl">
                        <div><dt>met both targets</dt><dd>{fmt(m.sla_attainment * 100, 0)}%</dd></div>
                        <div><dt>dropped</dt><dd>{fmt(m.drop_rate * 100, 1)}%</dd></div>
                        <div><dt>first token p95</dt><dd>{m.ttft_p95 == null ? "n/a" : `${fmt(m.ttft_p95, 2)} s`}</dd></div>
                        <div><dt>cost per request</dt><dd>{m.cost_per_request == null ? "n/a" : fmt(m.cost_per_request, 1)}</dd></div>
                      </dl>
                      <div className="muted" style={{ fontSize: 11.5 }}>slice {r.slice}</div>
                    </Card>
                  );
                })}
              </div>
              <p className="muted" style={{ marginTop: 10 }}>Runs with the same slice id saw identical requests. One run per policy is an anecdote, not a result; the 5-seed results are on the <Link to="/baselines">Baselines</Link> and <Link to="/stress">Stress tests</Link> pages. Cost is a synthetic price per busy second. Every run is saved in <code>results/live/</code> with its config, event log and machine details.</p>
            </section>
          )}

          <details className="manual">
            <summary>Manual controls: ask the cluster one question</summary>
            <Card className="flat">
              <p className="muted">One real request through the chosen policy. It shows which server answered and the measured time to first token. <Info text="The chat goes through the same router and policy code as the replay. The answer comes from a small language model (Qwen2.5 3B or 1.5B), so do not expect it to be good." /></p>
              <textarea className="chatbox" value={chat.prompt} onChange={(e) => setChat({ ...chat, prompt: e.target.value })} rows={3} aria-label="prompt" />
              <div className="controls"><label>policy <select value={chat.policy} onChange={(e) => setChat({ ...chat, policy: e.target.value })} aria-label="policy">{ALL.map(([k, l]) => <option key={k} value={k}>{l}</option>)}<option value="sed_local_full">SED local</option></select></label>
                <button className="primary" onClick={send} disabled={chat.busy || running}>{chat.busy ? "Waiting…" : "Send"}</button></div>
              {chat.reply && <div className="reading"><p><b>Answered by {chat.reply.server}</b> ({String(chat.reply.class).replace("_", " ")}) after {fmt(chat.reply.ttft_s, 3)} s to the first token, {fmt(chat.reply.tpot_s, 3)} s per token after that; passed on {chat.reply.hops} time(s).</p><p style={{ margin: 0 }}>{chat.reply.text}</p></div>}
            </Card>
          </details>
        </>
      )}
    </>
  );
}
