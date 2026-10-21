// Live mode: a guided live test. One button runs the whole check on this machine and narrates it like a chat; the cluster is
// drawn live next to it and the results land underneath. Works only while the local router is running; the recorded pages never
// depend on it. A mock backend is labelled MOCK everywhere: it rehearses the plumbing, it is not a result.
import { useCallback, useEffect, useRef, useState } from "react";
import { Card, ChartFrame, Info, PageHead, fmt } from "../ui";
import { ReplayStage } from "../viz/ReplayStage";
import type { Frame } from "../data/types";
import { Link } from "../router";
import { RankedBars } from "../viz/RankedBars";

const API = new URLSearchParams(window.location.search).get("api") ?? "http://127.0.0.1:8000";
const ALL: [string, string][] = [["sed_global", "SED global"], ["route_to_fast_shed", "Hand-written rule + shed"], ["ddqn_agents", "Learned agents"], ["ddqn_robust", "Robust agents"], ["route_to_fast", "Hand-written rule"], ["random", "Random"]];
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

  const start = useCallback(async (extra?: Record<string, unknown>) => {
    setErr(""); setMsgs([]); setRows([]); setFrames([]); n.current = 0; curRun.current = null; setRunId(null); setSent(null);
    try { await api("/livecheck/start", { method: "POST", body: JSON.stringify({ seconds, rho, seed, policies, ...(extra ?? {}) }) }); setState("running"); }
    catch (e) { setErr(String((e as Error).message)); }
  }, [seconds, rho, seed, policies]);
  // The quick overload showdown for a demo: a fixed, heavy arrival rate (about four times what the cluster serves in time), 45 s of
  // traffic per policy and at most 45 s to finish, so four policies take about six minutes and the differences are large.
  // Rates are the agents' training loads: rho 0.5 and 0.8 of the simulator lambda_sat 0.591 req/s (results/saturation/lambda_sat_flat.json; rho_train 0.8, configs/train.yaml) = 0.30 and 0.47 req/s.
  // The full showdown (the main result): two rates, 120 s of traffic per policy, five policies; about 36 minutes, saved as the main comparison.
  const fullShowdown = () => { if (window.confirm("The full showdown takes about 36 minutes and needs the machine to itself. Start it?")) void start({ rates: [0.3, 0.47], seconds: 120, drain_s: 90, policies: ["sed_global", "route_to_fast", "route_to_fast_shed", "ddqn_agents", "ddqn_robust"] }); };
  // Training load only (rho 0.8 = 0.47 req/s), about 12 minutes.
  const mediumShowdown = () => { if (window.confirm("The medium-load showdown takes about 12 minutes and needs the machine to itself. Start it?")) void start({ rates: [0.47], seconds: 120, drain_s: 90, policies: ["sed_global", "route_to_fast", "route_to_fast_shed", "ddqn_agents", "ddqn_robust"] }); };
  // Quick overload showdown: 0.30 req/s = rho 0.5 of the simulator lambda_sat, inside the agents' training loads; 75 s so a run holds enough requests to rank.
  const showdown = () => start({ rate_rps: 0.3, seconds: 75, drain_s: 60, policies: ["sed_global", "route_to_fast_shed", "ddqn_agents", "ddqn_robust"] });
  useEffect(() => { if (auto.current && health && health.status === "ok" && state === "idle") { auto.current = false; void start(); } });
  const stop = () => api("/livecheck/stop", { method: "POST" }).catch(() => undefined);
  const servers = (what: "start" | "stop") => {
    if (what === "stop" && !window.confirm("Stop the four llama-servers?")) return;
    if (what === "start" && !window.confirm("Start the four llama-servers on this machine? It takes about a minute and uses the CPU and GPU until you stop them.")) return;
    api(`/servers/${what}`, { method: "POST" }).catch((e) => setErr(String(e.message)));
  };
  // "Try your own prompt": the same prompt (or the same burst of N copies) goes through every policy, one policy after the other
  // (they share one chip, so running them at the same moment would make them slow each other down and the comparison unfair).
  type Cmp = { policy: string; n: number; refused?: number; met: number; ttft50: number; ttft95: number; total50: number; servers: string; hops: number; err?: string };
  const [cmp, setCmp] = useState<Cmp[] | null>(null);
  const [cmpBusy, setCmpBusy] = useState("");
  const [burst, setBurst] = useState(1);
  const askAll = async () => {
    setErr(""); setCmp([]); setChat((c) => ({ ...c, reply: null }));
    const pols: string[] = [...ALL.map(([k]) => k), "sed_local_full"];
    const med = (x: number[], q: number) => { const v = [...x].sort((m, n2) => m - n2); return v.length ? v[Math.min(v.length - 1, Math.floor(q * v.length))] : NaN; };
    for (const k of pols) {
      setCmpBusy(k);
      try {
        // the burst is staggered (a request every 250 ms) and answers are 200 tokens, close to the traffic the agents were trained on
        const all = await Promise.all(Array.from({ length: burst }, async (_, i) => { await new Promise((r) => setTimeout(r, i * 250)); return api<any>("/chat", { method: "POST", body: JSON.stringify({ prompt: chat.prompt, n_predict: 200, policy: k }) }); }));
        const rs = all.filter((r) => !r.refused);
        const refused = all.length - rs.length;
        const met = rs.filter((r) => r.ttft_s <= 5 && r.tpot_s <= 0.1).length;
        const total = rs.map((r) => r.ttft_s + (r.tpot_s || 0) * 199);
        if (!rs.length) throw new Error(`refused all ${all.length} requests`);
        const names = Array.from(new Set(rs.map((r) => `${r.server}`))).join(", ");
        setCmp((c) => [...(c ?? []), { policy: k, n: all.length, refused, met, ttft50: med(rs.map((r) => r.ttft_s), 0.5), ttft95: med(rs.map((r) => r.ttft_s), 0.95), total50: med(total, 0.5), servers: names, hops: rs.reduce((a2, r) => a2 + (r.hops ?? 0), 0) }]);
      } catch (e) { setCmp((c) => [...(c ?? []), { policy: k, n: 0, met: 0, ttft50: NaN, ttft95: NaN, total50: NaN, servers: "", hops: 0, err: String((e as Error).message) }]); }
    }
    setCmpBusy("");
  };
  const polName = (k: string) => (ALL.find(([x]) => x === k) ?? [k, "SED local"])[1];
  const PROMPTS: [string, string][] = [
    ["Short question", "What is the capital of France?"],
    ["Explain (medium)", "Explain in a few sentences how a transformer language model produces the next word."],
    ["Long document (about 1,500 tokens)", "Summarise the following text in one sentence.\n\n" + "The cluster has four servers of two kinds. Fast servers answer quickly but cost more per second; slow servers are cheaper and slower. A router decides, for every request, which server should answer it. ".repeat(48)],
  ];
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
                <button className="primary" onClick={() => start()} disabled={running}>{running ? "Running…" : msgs.length ? "Run again" : "Start live test"}</button>
                <button onClick={mediumShowdown} disabled={running} title="the medium load, five policies, about 12 minutes">Medium-load showdown (12 min)</button>
                <button onClick={fullShowdown} disabled={running} title="the main real-server result: two loads, five policies, about 36 minutes">Full showdown (36 min)</button>
                <button onClick={showdown} disabled={running} title="training-load overload (0.30 req/s), four policies, about 10 minutes">Quick overload showdown (10 min)</button>
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
                  <div className="tile" title="finished, but the first word came after 5 s or words came slower than 10 per second"><div className="k">answered late</div><div className="v">{res.filter((r) => r.status === "done" && !r.ok).length}</div></div>
                  <div className="tile" title="refused on purpose or a server error"><div className="k">refused</div><div className="v">{res.filter((r) => r.status !== "done").length}</div></div>
                  <div className="tile" title="sent, no final result yet"><div className="k">still waiting</div><div className="v">{Math.max(0, arrived - res.length)}</div></div>
                  <div className="tile"><div className="k">first token p95</div><div className="v">{p95 == null ? "n/a" : `${fmt(p95, 2)} s`}</div></div>
                </div>
                {running && sent && <div className="muted" style={{ fontSize: 12.5 }}>{sent.sent} of {sent.of} requests sent in this run</div>}
              </ChartFrame>
            </div>
          </div>

          {rows.length === 0 && (
            <div className="verdict tie" style={{ marginTop: 20 }}><b>Looking for the saved results?</b> The charts of earlier live tests are kept on the <Link to="/liveresults">Live results page</Link>: the medium and heavy loads, every run side by side. This page only shows the test you start here.</div>
          )}
          {rows.length > 0 && (
            <section style={{ marginTop: 28 }} aria-label="results">
              <h2>Results of this live test</h2>
              {rows.length > 1 && <Card className="flat" style={{ marginBottom: 16 }}>
                <ChartFrame title="Every policy on the same requests, best first" better="higher" tip="Each policy replayed exactly the same requests, one after the other. The bar is goodput: requests per second that met both targets. The yellow tick is the arrival rate, the most any policy could reach. Refused requests never count as good, so the refused share is shown beside each bar.">
                  <RankedBars rows={rows.map((r) => ({ label: r.label, policy: r.policy, goodput_rps: r.metrics.goodput_rps, sla_attainment: r.metrics.sla_attainment, drop_rate: r.metrics.drop_rate, ttft_p95: r.metrics.ttft_p95 }))} capacity={rows[0].metrics.n_arrived / rows[0].metrics.arrival_window_s} />
                </ChartFrame>
              </Card>}
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
                <button className="primary" onClick={send} disabled={chat.busy || running}>{chat.busy ? "Waiting…" : "Send"}</button>
                <button onClick={askAll} disabled={chat.busy || running || !!cmpBusy} title="send the same prompt through every policy and rank them">{cmpBusy ? `Trying ${polName(cmpBusy)}…` : "Compare all policies"}</button></div>
              <div className="controls" style={{ marginTop: 8 }}>
                <label>example <select value="" onChange={(e) => { const x = PROMPTS.find(([n2]) => n2 === e.target.value); if (x) setChat((c) => ({ ...c, prompt: x[1] })); }} aria-label="example prompts"><option value="">choose…</option>{PROMPTS.map(([n2]) => <option key={n2}>{n2}</option>)}</select></label>
                <label>load <select value={burst} onChange={(e) => setBurst(Number(e.target.value))} aria-label="requests at once"><option value={1}>1 request (idle cluster)</option><option value={4}>4 at once (busy)</option><option value={8}>8 at once (heavy)</option><option value={12}>12 at once (overload)</option></select></label>
              </div>
              {cmp && cmp.length > 0 && (() => {
                const done = cmp.filter((x) => !x.err);
                const ranked = [...done].sort((x, y) => (y.met / y.n - x.met / x.n) || (x.total50 - y.total50));
                const win = ranked[0];
                const tie = ranked.length > 1 && ranked[1].met === win.met && Math.abs(ranked[1].total50 - win.total50) < 0.25 * win.total50;
                return (
                  <div style={{ marginTop: 12 }}>
                    {!cmpBusy && win && <div className="reading"><p style={{ margin: 0 }}><b>{tie ? "No clear winner" : `Best here: ${polName(win.policy)}`}.</b> {win.met} of {win.n} answers met both targets (first word within 5 s and 10 words per second), median time to the full answer {fmt(win.total50, 1)} s.{tie ? " The top policies are within a quarter of each other: treat as tied." : ""} One try per policy is an anecdote, not a result.</p></div>}
                    <div className="tablewrap"><table>
                      <thead><tr><th>policy</th><th>met both targets</th><th>first token median / p95 (s)</th><th>full answer median (s)</th><th>servers used</th><th>passed on</th></tr></thead>
                      <tbody>{cmp.map((x) => <tr key={x.policy} className={win && x.policy === win.policy && !cmpBusy ? "best-row" : ""}><td style={{ textAlign: "left" }}>{polName(x.policy)}</td>{x.err ? <td colSpan={5}>{x.err}</td> : <><td>{x.met} of {x.n}{x.refused ? ` (${x.refused} refused)` : ""}</td><td>{fmt(x.ttft50, 2)} / {fmt(x.ttft95, 2)}</td><td>{fmt(x.total50, 1)}</td><td>{x.servers}</td><td>{x.hops}</td></>}</tr>)}</tbody>
                    </table></div>
                    <p className="muted" style={{ fontSize: 12.5 }}>The requests of one burst arrive 250 ms apart and ask for 200-token answers. The policies run one after another, not at the same moment: all four servers share one chip, so running them together would make them slow each other down and the comparison unfair. With one request on an idle cluster most policies pick the same fast server; the differences appear under load, so try 4, 8 or 12 at once.</p>
                  </div>
                );
              })()}
              {chat.reply && <div className="reading"><p><b>Answered by {chat.reply.server}</b> ({String(chat.reply.class).replace("_", " ")}) after {fmt(chat.reply.ttft_s, 3)} s to the first token, {fmt(chat.reply.tpot_s, 3)} s per token after that; passed on {chat.reply.hops} time(s).</p><p style={{ margin: 0 }}>{chat.reply.text}</p></div>}
            </Card>
          </details>
        </>
      )}
    </>
  );
}
