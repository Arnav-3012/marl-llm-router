// Pareto, Baselines & E1, Observability, Traces, Method pages.
import { RankedBars } from "../viz/RankedBars";
import { useState } from "react";
import { BarsCI, LineChart, ParetoScatter, type BarSeries } from "../charts";
import { Card, ChartFrame, Info, Loaded, PageHead, Marker, SourceNote, fmt, styleOf, useData, useLoad } from "../ui";
import { Link } from "../router";
import type { ActionShares, BehaviourData, ClassBehaviour, Metric, MetricRow, PolicyTable } from "../data/types";

const RHOS = ["0.5", "0.8", "0.95"];
const METRIC_LABEL: Record<string, string> = {
  goodput_rps: "goodput (requests/s that met both targets)", sla_attainment: "SLA attainment (share of arrivals)", breach_rate: "breach rate", drop_rate: "drop rate",
  ttft_p95: "TTFT p95 (s)", tpot_p95: "TPOT p95 (s/token)", e2e_p95: "end-to-end p95 (s)", cost_per_request: "cost per request (synthetic units)", cache_hit_rate: "cache hit rate (token share)", jain_utilisation: "Jain's index, all servers (a saturated cluster scores 1: not a quality of routing)", util_fast: "utilisation of the fast servers", util_slow: "utilisation of the slow servers", jain_fast: "Jain's index over the fast servers only (even sharing between equal servers)",
};
const METRIC_BETTER: Record<string, "higher" | "lower"> = {
  goodput_rps: "higher", sla_attainment: "higher", breach_rate: "lower", drop_rate: "lower", ttft_p95: "lower", tpot_p95: "lower",
  e2e_p95: "lower", cost_per_request: "lower", cache_hit_rate: "higher", jain_fast: "higher",
};
const METRIC_TIP: Record<string, string> = {
  goodput_rps: "Requests per second that finished AND met both targets (first token within 5 s, then at least 10 tokens per second). It counts only useful work, so a policy that serves many requests late scores low. Dropped requests count as failures.",
  sla_attainment: "Share of all arriving requests that met both targets. Dropped and late requests count against it.",
  breach_rate: "Share of arriving requests that missed a target or were dropped (1 minus SLA attainment).",
  drop_rate: "Share of arriving requests that were refused or lost. A policy with the Reject action drops some on purpose, so always read its drop rate next to its goodput.",
  ttft_p95: "Time to first token: how long the slowest 1 in 20 completed requests waited before the first word of the answer. Dropped requests have no time and are not included.",
  tpot_p95: "Seconds per output token for the slowest 1 in 20 completed requests (lower means faster streaming).",
  e2e_p95: "End-to-end time of the slowest 1 in 20 completed requests.",
  cost_per_request: "Synthetic price per busy second, summed over servers and divided by completed requests. It is a design choice (fast servers cost 4, slow ones 1), not a bill.",
  cache_hit_rate: "Share of prompt tokens served from the prefix cache instead of being recomputed.",
  jain_utilisation: "Jain's index over all four servers: 1 means all equally busy. A saturated cluster scores 1, so this is NOT a measure of routing quality (ADR-030).",
  util_fast: "Share of time the fast servers were busy.",
  util_slow: "Share of time the slow servers were busy; near 0 means the policy leaves them idle on purpose.",
  jain_fast: "Jain's index over the two fast servers only: 1 means they share the work evenly.",
};

/** One sentence per load: who leads, and who is not clearly different (95% intervals overlap). */
function readingFor(series: BarSeries[], better: "higher" | "lower" | undefined, digits = 2) {
  if (!better) return null;
  const name = (s: BarSeries) => s.label ?? styleOf(s.id).label;
  const lines = RHOS.map((rho, gi) => {
    const items = series.map((s) => ({ s, v: s.values[gi] })).filter((x) => x.v && x.v.mean != null) as { s: BarSeries; v: Metric }[];
    if (!items.length) return null;
    const lead = items.reduce((a, b) => (better === "higher" ? (b.v.mean! > a.v.mean! ? b : a) : (b.v.mean! < a.v.mean! ? b : a)));
    const tied = items.filter((x) => x !== lead && Math.abs(x.v.mean! - lead.v.mean!) <= (x.v.ci ?? 0) + (lead.v.ci ?? 0));
    return (
      <p key={rho}><b>ρ = {rho}:</b> {name(lead.s)} is {better === "higher" ? "highest" : "lowest"} ({fmt(lead.v.mean, digits)}){tied.length ? `; not clearly different (intervals overlap): ${tied.map((x) => name(x.s)).join(", ")}` : "; clearly ahead of the rest shown"}.</p>
    );
  }).filter(Boolean);
  return <>{lines}<p className="muted" style={{ margin: 0 }}>Read from the 5-seed means and 95% intervals shown; overlapping intervals are not called a difference.</p></>;
}
const col = (rows: Record<string, MetricRow> | undefined, key: string): (Metric | null)[] => RHOS.map((r) => rows?.[r]?.[key] ?? null);
const fromTable = (t: PolicyTable | undefined, p: string, key: string) => RHOS.map((r) => t?.[p]?.[r]?.[key] ?? null);

export function Pareto() {
  const ds = useData();
  const s = useLoad(() => ds.getPareto(), []);
  return (
    <>
      <PageHead eyebrow="Question 2 · cost against speed" title="Can the agents trade cost for speed?"></PageHead>
      <p className="lead">The weight λ says how much a cheaper service is worth to an agent. We trained the three-action agents (before the Reject action existed) with λ = 0, 1 and 2 and compared them with fixed rules at load 0.8 on held-out traffic. Lower and further left is better; points marked ◎ are on the frontier. Dashed whiskers are 95% intervals over 5 seeds, cut off at the edge of the plot when they are huge.</p>
      <Loaded state={s} what="Cost–latency frontier (E3)">
        {(d, env) => {
          const learned = d.points.filter((p) => p.kind === "learned");
          const onFront = learned.filter((p) => p.on_frontier);
          const note = onFront.length <= 1
            ? `Only ${onFront.length ? onFront[0].label : "none of the learned settings"} of the ${learned.length} learned settings is on the frontier. The other settings have a higher mean cost and latency, but their intervals are wide (some seeds did not learn), so this λ sweep does not trace a cost-versus-latency trade-off here. A likely reason, found in the diagnosis rather than shown by this chart (ADR-027): the slow “cheap” class costs more per completed request than the fast class in this calibration.`
            : `${onFront.length} of the ${learned.length} learned settings are on the frontier: raising λ trades latency for cost along it.`;
          return (
            <>
              <Card className="flat"><ChartFrame title="Cost against latency at load 0.8" better="lower"
                tip={<><b>How to read it.</b> Each dot is one policy. Left means cheaper (synthetic price per request), lower means a shorter wait for the first token (seconds, log scale because the worst policies are 100 times slower). The best place is the bottom left. Circled dots are on the frontier: no other dot is both cheaper and faster. Dashed whiskers are 95% intervals over 5 seeds, clipped at the plot edge; a very long whisker means some seeds behaved very differently (some seeds did not learn). Labels are in the column on the right, joined to their dots by thin lines.</>}>
                <ParetoScatter points={d.points} xLabel="cost per request (synthetic units, lower is better)" yLabel="TTFT p95 (s)" title="Cost per request against TTFT p95 at load 0.8" />
              </ChartFrame><SourceNote source={env.source} /></Card>
              <div className="verdict tie" style={{ marginTop: 12 }}><b>Reading:</b> {note}</div>
            </>
          );
        }}
      </Loaded>
    </>
  );
}

export function Baselines() {
  const ds = useData();
  const b = useLoad(() => ds.getBaselines(), []);
  const [metric, setMetric] = useState("goodput_rps");
  const [showAll, setShowAll] = useState(false); // default: the first agent, the final agent and the key rules
  return (
    <>
      <PageHead eyebrow="Question 1 · the main comparison" title="Do the learned agents beat the rules?"></PageHead>
      <p className="lead">Same held-out traffic for every policy, 5 seeds, mean ± 95% interval. Agents with three actions were trained at ρ = 0.8; agents with the Reject action (ADR-029) at ρ = 0.5, 0.8 and 0.95. “All policies” adds the other agents and baselines.</p>
      <div className="controls"><label>metric <select value={metric} onChange={(e) => setMetric(e.target.value)} aria-label="metric">{Object.entries(METRIC_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
        <span className="seg" role="group" aria-label="which policies"><button aria-pressed={!showAll} onClick={() => setShowAll(false)}>key policies</button><button aria-pressed={showAll} onClick={() => setShowAll(true)}>all policies</button></span></div>
      <Loaded state={b} what="Baselines and learned agents (E1)">
        {(d, env) => {
          const all = ["sed_global", "route_to_fast", "route_to_fast_shed", "sed_local_full", "sed_local_k0", "cache_aware_global", "cache_aware_local_full", "jsq_global", "po2_global", "round_robin", "random"];
          const key = ["sed_global", "route_to_fast", "route_to_fast_shed", "sed_local_full", "random"];
          const order = showAll ? all : key;
          const series: BarSeries[] = [
            ...(d.learned ? [{ id: "ddqn", label: showAll ? d.learned.label : "DDQN agents (3 actions)", values: col(d.learned.rows, metric) }] : []),
            ...(d.learned_extra ?? []).filter((l) => showAll || l.id === "ddqn_reject_mix").map((l) => ({ id: l.id, label: showAll ? l.label : "DDQN agents + Reject", values: col(l.rows, metric) })),
            ...order.filter((p) => d.baselines?.policies[p]).map((p) => ({ id: p, values: fromTable(d.baselines?.policies, p, metric) })),
          ];
          return (
            <Card className="flat">
              <ChartFrame title={METRIC_LABEL[metric]} better={METRIC_BETTER[metric]}
                tip={<><b>How to read it.</b> Each group is one offered load ρ: 0.5 is a light load, 0.8 a heavy one, 0.95 an overload (ρ is the arrival rate as a share of what the cluster can serve). Each bar is one policy, the mean over 5 seeds on the same traffic; the white whisker is the 95% interval. <br /><br /><b>This metric.</b> {METRIC_TIP[metric]}</>}
                reading={readingFor(series, METRIC_BETTER[metric], metric.includes("tpot") ? 3 : 2)}>
                <BarsCI groups={RHOS} series={series} xLabel="offered load ρ (fraction of the saturation rate)" yLabel={METRIC_LABEL[metric]} title={`${METRIC_LABEL[metric]} by policy and load`} digits={metric.includes("tpot") ? 3 : 2} />
              </ChartFrame>
              <SourceNote source={env.source} />
            </Card>
          );
        }}
      </Loaded>
      <p className="muted" style={{ marginTop: 32 }}>How the agents were trained (return, loss, Q-values, exploration, actions, every seed): <Link to="/training">Training page →</Link></p>
    </>
  );
}

export function Observability() {
  const ds = useData();
  const s = useLoad(() => ds.getObservability(), []);
  return (
    <>
      <PageHead eyebrow="Question 3 · local information" title="What does seeing the neighbours buy?"></PageHead>
      <p className="lead">With k = 0 an agent sees only its own server. With k = full it also sees how busy the others are. The gap between the two is what that information is worth. A centralised reference (one agent seeing everything) was not built.</p>
      <Loaded state={s} what="k = 0 against k = full (E4)">
        {(d, env) => {
          const series: BarSeries[] = [
            ...d.learned.map((l) => ({ id: l.label.includes("k=0") ? "ddqn_k0" : "ddqn", label: l.label, color: l.label.includes("k=0") ? "#b57700" : "#e69f00", marker: l.label.includes("k=0") ? "diamond" : "circle", values: col(l.rows, "goodput_rps") })),
            ...(["sed_local_k0", "sed_local_full", "sed_global"] as const).filter((p) => d.references[p]).map((p) => ({ id: p, values: fromTable({ [p]: d.references[p] as Record<string, MetricRow> }, p, "goodput_rps") })),
          ];
          return (<Card className="flat"><ChartFrame title="Goodput by how much each agent can see" better="higher"
            tip={<><b>How to read it.</b> k = 0: an agent sees only its own server. k = full: it also sees the mean wait of the other servers. Same bars as the Baselines page: mean over 5 seeds, white whisker = 95% interval. The gap between the k = 0 and k = full agents is what local information about the neighbours is worth.</>}
            reading={readingFor(series, "higher")}>
            <BarsCI groups={RHOS} series={series} xLabel="offered load ρ" yLabel="goodput (req/s)" title="Goodput by visibility" />
          </ChartFrame><SourceNote source={env.source} /></Card>);
        }}
      </Loaded>
      <Behaviour />
    </>
  );
}

const ACTION_STYLE: { key: "accept" | "forward" | "defer" | "reject"; label: string; color: string }[] = [
  { key: "accept", label: "Accept (serve here)", color: "#0072b2" },
  { key: "forward", label: "Forward (to a neighbour)", color: "#009e73" },
  { key: "defer", label: "Defer (wait one tick)", color: "#cc79a7" },
  { key: "reject", label: "Reject (drop)", color: "#d55e00" },
];

function ShareBar({ label, s }: { label: string; s: ActionShares }) {
  const parts = ACTION_STYLE.filter((a) => (s[a.key] ?? 0) > 0);
  const txt = parts.map((a) => `${a.label.split(" ")[0]} ${((s[a.key] ?? 0) * 100).toFixed(0)}%`).join(", ");
  return (
    <div className="sharerow" role="img" aria-label={`${label}: ${txt}, ${s.n} decisions`}>
      <span className="sharelabel">{label}</span>
      <span className="sharebar">{parts.map((a) => <span key={a.key} style={{ width: `${(s[a.key] ?? 0) * 100}%`, background: a.color }}>{(s[a.key] ?? 0) >= 0.08 ? `${((s[a.key] ?? 0) * 100).toFixed(0)}%` : ""}</span>)}</span>
      <span className="muted sharen">{s.n.toLocaleString()}</span>
    </div>
  );
}

function ClassPanel({ title, c, d }: { title: string; c: ClassBehaviour; d: BehaviourData }) {
  const { wait_s, prompt_tokens } = d.units;
  const fmtRange = (label: string, scale: number, unit: string) => {
    const [lo, hi] = label.split("-").map(Number);
    const a = lo * scale, b = hi * scale;
    return hi >= 1 ? `> ${a.toFixed(0)} ${unit}` : `${a.toFixed(0)}–${b.toFixed(0)} ${unit}`;
  };
  return (
    <Card className="flat">
      <h3 style={{ margin: "0 0 8px", display: "flex", alignItems: "center", gap: 8 }}>{title}<Info text={<>Each bar is the share of this group\u2019s decisions by action. <b>Accept</b>: serve here. <b>Forward</b>: pass to the neighbour with the least expected wait. <b>Defer</b>: wait one tick. <b>Reject</b>: drop the request (only agents trained with it). The number at the right is how many decisions the bar covers; the bars are split by request size and by this server\u2019s expected wait at the moment of the decision.</>} label={`How to read: ${title}`} /></h3>
      <ShareBar label="all decisions" s={c.all} />
      <div className="eyebrow" style={{ margin: "12px 0 4px" }}>by prompt size</div>
      {Object.entries(c.by_prompt).filter(([, s]) => s.n > 0).map(([k, s]) => <ShareBar key={k} label={fmtRange(k, prompt_tokens, "tokens")} s={s} />)}
      <div className="eyebrow" style={{ margin: "12px 0 4px" }}>by this server's expected wait</div>
      {Object.entries(c.by_wait).filter(([, s]) => s.n > 0).map(([k, s]) => <ShareBar key={k} label={fmtRange(k, wait_s, "s")} s={s} />)}
    </Card>
  );
}

function Behaviour() {
  const ds = useData();
  const s = useLoad(() => ds.getBehaviour(), []);
  const [rho, setRho] = useState("0.8");
  return (
    <div style={{ marginTop: 40 }}>
      <div className="eyebrow">what the agents do</div><h2 style={{ margin: "4px 0 8px" }}>Are they just the simple rule?</h2>
      <Loaded state={s} what="Behaviour of the learned agents">
        {(d, env) => {
          const loads = Object.keys(d.rhos);
          const cur = d.rhos[rho] ?? d.rhos[loads[0]];
          return (
            <>
              <p className="lead">Every decision of the final agents on the held-out traffic ({d.seeds.length} seeds), as the share of each action. The hand-written rule has slow servers pass everything on and fast servers accept everything. The agents do mostly that, but also hold some requests back (Defer), refuse a few (Reject), and their choices depend on the request size and the queue. The hand rule matches their goodput, so this shows what they learned, not that it is better.</p>
              <div className="controls"><span className="seg" role="group" aria-label="offered load">{loads.map((r) => <button key={r} aria-pressed={r === (d.rhos[rho] ? rho : loads[0])} onClick={() => setRho(r)}>ρ = {r}</button>)}</span></div>
              <div className="chips" aria-label="legend">{ACTION_STYLE.filter((a) => a.key !== "reject" || (cur.fast.all.reject ?? 0) > 0 || (cur.slow.all.reject ?? 0) > 0).map((a) => <span key={a.key} className="pill"><i style={{ width: 10, height: 10, borderRadius: 2, background: a.color, display: "inline-block" }} />{a.label}</span>)}</div>
              <div className="grid-2"><ClassPanel title="Agents on the fast servers" c={cur.fast} d={d} /><ClassPanel title="Agents on the slow servers" c={cur.slow} d={d} /></div>
              <SourceNote source={env.source} />
            </>
          );
        }}
      </Loaded>
    </div>
  );
}

export function Traces() {
  const ds = useData();
  const s = useLoad(() => ds.getTraces(), []);
  return (
    <>
      <PageHead eyebrow="The data" title="The traffic we tested on"></PageHead>
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
      <PageHead eyebrow="Method, in plain words" title="What we built, and how it differs from what is used today"></PageHead>
      <p className="lead">An LLM service runs on several servers. Every incoming request has to be sent to one of them. A <b>router</b> makes that choice. A bad choice means users wait, or the answer comes too slowly, or a busy server drowns while another sits idle.</p>

      <h2>How routers usually decide</h2>
      <div className="grid g2">
        <Card><h3>Fixed rules</h3><p className="muted">Common load balancers send requests round-robin (each server in turn), to a random server, to the server with the fewest waiting requests, or to the less busy of two picked at random. Simple, cheap and predictable, but they do not know that some servers are much faster than others or that a request's size matters.</p></Card>
        <Card><h3>Smarter rules with a central view</h3><p className="muted">Better rules estimate which server would finish the request soonest ("shortest expected delay"), or send a follow-up chat message to the server that still holds its earlier context in cache. They work well but need one central router that sees every server, which is a single point of failure and a bottleneck as the cluster grows.</p></Card>
        <Card><h3>Refusing work when overloaded</h3><p className="muted">When more requests arrive than the servers can handle, real services answer "too busy" to some of them (load shedding), so the rest still get a fast answer. Without it, every queue fills and almost everyone waits too long.</p></Card>
        <Card><h3>Hand-tuned thresholds</h3><p className="muted">Each of these rules has knobs (which servers are fast, when to refuse) that a person sets by hand and has to re-set when the hardware or traffic changes.</p></Card>
      </div>

      <h2>What we did instead</h2>
      <div className="grid g2">
        <Card><h3>One small learning agent per server</h3><p className="muted">There is no central router. Each server has its own agent that sees only its own server (how long its queue is, how full its memory is, how big the request is, how much time is left before the deadline) and how busy the other servers are on average.</p></Card>
        <Card><h3>Four choices</h3><p className="muted"><b>Accept</b> the request, <b>Forward</b> it to a neighbour, <b>Defer</b> it for a moment, or (in the final version) <b>Reject</b> it. Nobody tells the agent which servers are fast or when to refuse.</p></Card>
        <Card><h3>Learning by trial and reward</h3><p className="muted">Agents practise on recorded real traffic in a simulator calibrated on real servers. A request answered in time earns a reward, a late or dropped one a penalty, plus a small cost for slow or expensive work. Over many episodes the agents learn which choice pays off (deep reinforcement learning, one Double-DQN network per agent).</p></Card>
        <Card><h3>Measured honestly</h3><p className="muted">Every policy is run on exactly the same unseen traffic, 5 times with different random seeds, and compared with 95% intervals. A difference is only claimed when the intervals do not overlap; ties are shown as ties.</p></Card>
      </div>

      <h2>The policies in the charts</h2>
      <Card className="flat"><div className="tablewrap"><table>
        <thead><tr><th>Name in the charts</th><th style={{ textAlign: "left" }}>What it does</th><th>Sees</th><th>Made by</th><th>Can refuse</th></tr></thead>
        <tbody>
          {[
            ["DDQN agents + Reject (ours, final)", "Learned agents that may also refuse a request", "own server + neighbours", "learned", "yes"],
            ["DDQN agents, 3 actions (ours, first)", "Learned agents: accept, forward or defer", "own server + neighbours", "learned", "no"],
            ["Hand-written rule: route to fast + shed", "Our own expert rule: send to fast servers, refuse what cannot meet its deadline. It is told which servers are fast", "own server + server classes", "written by us", "yes"],
            ["Hand-written rule: route to fast", "The same rule without refusing", "own server + server classes", "written by us", "no"],
            ["SED (global)", "Send to the server that would finish soonest; a strong classic rule", "the whole cluster", "classic rule", "no"],
            ["SED local", "The same idea, but each router sees only itself and its neighbours", "own server + neighbours", "classic rule", "no"],
            ["Cache-aware", "Prefer the server that already holds the conversation's cached context", "whole cluster or local", "classic rule", "no"],
            ["JSQ, Po2", "Fewest waiting requests; less busy of two random servers", "the whole cluster", "classic rule", "no"],
            ["Random, round-robin", "A random server; each server in turn", "nothing", "classic rule", "no"],
          ].map((r) => <tr key={r[0]}><td>{r[0]}</td><td style={{ textAlign: "left", whiteSpace: "normal" }}>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]}</td></tr>)}
        </tbody>
      </table></div></Card>

      <h2>What we found, honestly</h2>
      <div className="grid g2">
        <Card><h3>Where ours is better</h3><p className="muted">Without any central view, the learned agents beat every rule that does not know the server speeds, by a wide margin at high load. The final agents (with Reject) beat the strong central rule (SED global) once the cluster is heavily loaded, and keep working when one fast server suddenly slows down, where the fixed route-to-fast rule loses much more.</p></Card>
        <Card><h3>Where it is a tie</h3><p className="muted">The agents match, but do not beat, our hand-written expert rule. That rule was written after we understood the problem and is told which servers are fast; the agents worked it out from reward alone. Both are already close to the most any policy could achieve.</p></Card>
        <Card><h3>What is not shown</h3><p className="muted">This is a calibrated simulation, not live servers; the calibration used one machine. Refusing requests helps the rest, but the refused share is always shown next to the gain.</p></Card>
        <Card><h3>Where to look</h3><p className="muted">Numbers: <Link to="/baselines">Baselines</Link> and <Link to="/stress">Stress tests</Link>. Side by side replays: <Link to="/headtohead">Head to head</Link>. How the agents learned: <Link to="/training">Training</Link>.</p></Card>
      </div>

      <h2>Hand-written rule or learned agents?</h2>
      <p className="lead">On the traffic we tested, the agents and our best hand-written rule perform the same. So the choice is about what each one asks of the people running the cluster.</p>
      <div className="grid g2">
        <Card><h3>What the hand-written rule needs from a person</h3><p className="muted">Someone must say which servers are the fast ones, and someone must design the rule itself: forward everything from the slow servers, refuse a request once its deadline can no longer be met. We could write it only after studying the problem. If the hardware mix or the traffic changes, the same person has to look again and rewrite or retune it.</p></Card>
        <Card><h3>What the learned agents need instead</h3><p className="muted">They are never told which servers are fast or when to refuse. They work that out from outcomes: requests that finish in time earn reward, late or dropped ones cost. What they need is a one-off measurement of the servers (profiling, to calibrate the simulator) and a training run (about 35 minutes on a laptop for 5 seeds). There is no central router either, so there is no single point of failure.</p></Card>
        <Card><h3>What we have shown</h3><p className="muted">The agents reach the rule's performance without being given the server speeds or the refusing rule, on the normal traffic, under a load ramp, with one server slowed down, and (after training on mixed traffic) on bursty code-assistant traffic. They beat every standard rule that lacks the refusing step.</p></Card>
        <Card><h3>What we found when the cluster changed</h3><p className="muted">We tested a cluster with one fast and three slow servers (<Link to="/stress">Stress tests, section 5</Link>). The agents were retrained with the same recipe and no code changes, and they beat the hand rule we rewrote and tuned for that layout. But the unchanged old rule still worked there too, because the environment already picks the best neighbour when a request is passed on, so we cannot claim that retraining is easier than rewriting. The agents also need training data and a calibrated simulator, and a person can read the rule line by line, which is hard to do with a neural network. If the cluster is stable and well known, the hand rule is the simpler choice.</p></Card>
      </div>

      <h2>Technical details</h2>
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

const SEED_COLORS = ["#e69f00", "#56b4e9", "#009e73", "#cc79a7", "#0072b2", "#d55e00", "#f0e442"];
const SEED_MARKERS = ["circle", "square", "diamond", "triangle", "circle", "square", "diamond"];

export function Training() {
  const ds = useData();
  const t = useLoad(() => ds.getTraining(), []);
  return (
    <>
      <PageHead eyebrow="How the agents learned" title="Did the agents actually learn?"></PageHead>
      <p className="lead">Independent Double-DQN agents, one per server, trained on windows of the training traffic with some random exploration. Each seed is its own line, so a run that failed to learn would show up here. Return, goodput and SLA are smoothed over 16 episodes.</p>
      <Loaded state={t} what="Training curves">
        {(d, env) => {
          const seeds = d.seeds ?? [];
          // episodes are random windows of traffic, so single episodes are noisy: the noisy series are drawn as a moving average over 8 points (16 episodes)
          const smooth = (pts: { x: number; y: number | null }[], w: number) => pts.map((p, i) => {
            const win = pts.slice(Math.max(0, i - w + 1), i + 1).filter((q) => q.y != null) as { x: number; y: number }[];
            return { x: p.x, y: win.length ? win.reduce((a, q) => a + q.y, 0) / win.length : null };
          });
          const NOISY = new Set(["return_mean", "goodput_rps", "sla_attainment"]);
          const lines = (k: string) => seeds.map((s, i) => { const raw = s.episodes.map((e) => ({ x: e.episode as number, y: e[k] as number | null })); return { id: `s${s.seed}`, label: `seed ${s.seed}`, color: SEED_COLORS[i % SEED_COLORS.length], marker: SEED_MARKERS[i % SEED_MARKERS.length], points: NOISY.has(k) ? smooth(raw, 8) : raw }; });
          const mean = (k: string) => [{ id: "m", label: "mean over seeds", color: "#e69f00", marker: "circle", points: d.episodes.map((e) => ({ x: e.episode as number, y: e[k] as number | null })) }];
          const TIPS: Record<string, [string, "higher" | "lower" | undefined]> = {
            return_mean: ["The sum of rewards an agent collected in one training episode (+10 for a request that met its targets, −10 for a miss, small costs for passing a request on). Rising means the agents are learning to route well. It includes random exploration, so it is lower than the greedy results elsewhere.", "higher"],
            goodput_rps: ["Requests per second that met both targets during training episodes, with exploration switched on.", "higher"],
            td_loss: ["How wrong the network's value estimates were when updated (Huber loss). It should settle to a low steady level; a growing curve would mean unstable learning.", undefined],
            mean_q: ["The average value the network predicted for the actions it took (rewards are scaled by 0.1). It should move smoothly and level off; a sudden jump would be a sign of trouble.", undefined],
            epsilon: ["The chance of a random action instead of the best one. It falls from 1 to 0.05 over the first half of training so agents explore first and then settle.", undefined],
            sla_attainment: ["Share of arrivals that met both targets during training episodes.", "higher"],
          };
          const chart = (title: string, k: string, yLabel: string) => <Card className="flat"><ChartFrame title={NOISY.has(k) ? `${title} (moving average)` : title} better={TIPS[k]?.[1]} tip={<>{TIPS[k]?.[0]} <br /><br /><b>Every line is one seed</b>; if one seed failed to learn it would sit apart from the others.</>}><LineChart title={title} xLabel="episode" yLabel={yLabel} series={seeds.length ? lines(k) : mean(k)} /></ChartFrame></Card>;
          // pooled action shares over equal slices of training (the per-agent split is not logged during training)
          const cols = ["act_accept", "act_forward", "act_defer", "act_reject"].filter((c) => d.columns.includes(c));
          const slices = 5;
          const size = Math.ceil(d.episodes.length / slices);
          const hist = Array.from({ length: slices }, (_, i) => {
            const part = d.episodes.slice(i * size, (i + 1) * size);
            if (!part.length) return null;
            const sums = cols.map((c) => part.reduce((a, e) => a + ((e[c] as number | null) ?? 0), 0));
            const tot = sums.reduce((a, b) => a + b, 0) || 1;
            const lo = part[0].episode as number, hi = part[part.length - 1].episode as number;
            return { label: `episodes ${lo}–${hi}`, s: { n: Math.round(tot / part.length), accept: sums[0] / tot, forward: sums[1] / tot, defer: sums[2] / tot, ...(cols.length > 3 ? { reject: sums[3] / tot } : {}) } };
          }).filter(Boolean) as { label: string; s: ActionShares }[];
          return (
            <>
              <div className="grid-2">
                {chart("Return per episode", "return_mean", "return (mean over agents)")}
                {chart("Goodput during training", "goodput_rps", "goodput (req/s, with exploration)")}
                {chart("TD loss", "td_loss", "TD loss (Huber)")}
                {chart("Mean Q of the actions taken", "mean_q", "Q (reward scaled by 0.1)")}
                {chart("Exploration rate", "epsilon", "ε")}
                {chart("SLA attainment during training", "sla_attainment", "share of arrivals meeting both targets")}
              </div>
              <h2 style={{ marginTop: 40 }}>What the agents chose while training</h2>
              <p className="lead">Share of decisions by action, pooled over agents and seeds, in five equal slices of training. The split by agent was not logged during training; the trained agents' choices by server class are on the <Link to="/observability">Observability page</Link>.</p>
              <Card className="flat">
                <div className="chips" aria-label="legend">{ACTION_STYLE.filter((a) => cols.includes(`act_${a.key}`)).map((a) => <span key={a.key} className="pill"><i style={{ width: 10, height: 10, borderRadius: 2, background: a.color, display: "inline-block" }} />{a.label}</span>)}</div>
                {hist.map((h) => <ShareBar key={h.label} label={h.label} s={h.s} />)}
              </Card>
              <SourceNote source={env.source} />
            </>
          );
        }}
      </Loaded>
    </>
  );
}

const FEATURE_LABEL: Record<string, string> = {
  own_wait: "queue wait", own_kv: "memory use", prompt_size: "request size", slack: "deadline left",
  hops: "times passed on", neighbour_wait: "neighbours' wait", prefix_hit: "cached prompt",
};
const pair = (x: [number, number] | number[] | undefined): Metric | null => (x ? { mean: x[0], ci: Number.isFinite(x[1]) ? x[1] : null, n: 5 } : null);

function verdictCounts(diffs: (Metric | null)[]) {
  let beats = 0, ties = 0, loses = 0;
  diffs.forEach((m) => {
    if (!m || m.mean == null) return;
    const h = m.ci ?? 0;
    if (m.mean - h > 0 && m.mean > 0.01) beats++;
    else if (m.mean + h < 0 && m.mean < -0.01) loses++;
    else ties++;
  });
  return { beats, ties, loses };
}

export function Stress() {
  const ds = useData();
  const s = useLoad(() => ds.getStress(), []);
  return (
    <>
      <PageHead eyebrow="Are the agents smarter than the rules?" title="Stress tests"></PageHead>
      <p className="lead">Four tests that could show the agents doing better than fixed rules, with the pass/fail rule written down before running them (ADR-032, ADR-033). The agents shown are the final ones (Reject action, trained on conversation and code-assistant traffic). Nothing was retrained or tuned for the tests themselves. Each one can fail, and a failure is shown as a failure.</p>
      <Loaded state={s} what="Stress tests">
        {(d, env) => {
          const sw = d.sweep_reject, v2 = d.sweep_v2;
          const line = (id: string, label: string, src: any, key: string) => ({ id, label, color: styleOf(id).color, marker: styleOf(id).marker, dash: styleOf(id).dash, points: (src?.rhos ?? []).map((r: number, i: number) => ({ x: r, y: src.policies[key]?.[i]?.mean ?? null })) });
          const sweepSeries = sw ? [
            line("ddqn_reject_mix", "DDQN agents + Reject", sw, "ddqn_agents"),
            ...(v2 ? [line("ddqn", "DDQN agents (3 actions)", v2, "ddqn_agents")] : []),
            line("route_to_fast_shed", styleOf("route_to_fast_shed").label, sw, "route_to_fast_shed"),
            line("route_to_fast", styleOf("route_to_fast").label, sw, "route_to_fast"),
            line("sed_global", "SED (global)", sw, "sed_global"),
          ] : [];
          const dg = d.degradation?.e8_mix, dgv2 = d.degradation?.main_v2;
          const dRhos = dg ? Object.keys(dg.rhos) : [];
          const degSeries: BarSeries[] = dg ? [
            { id: "ddqn_reject_mix", label: "DDQN agents + Reject", values: dRhos.map((r) => pair(dg.rhos[r].policies.ddqn_agents.goodput_degraded)) },
            ...(dgv2 ? [{ id: "ddqn", label: "DDQN agents (3 actions)", values: dRhos.map((r) => pair(dgv2.rhos[r]?.policies.ddqn_agents.goodput_degraded)) }] : []),
            ...["route_to_fast_shed", "route_to_fast", "sed_global", "sed_local_full"].map((p) => ({ id: p, values: dRhos.map((r) => pair(dg.rhos[r].policies[p]?.goodput_degraded)) })),
          ] : [];
          const sh = d.shuffle ?? {};
          const feats: string[] = (sh.e8_mix ?? sh.main_v2)?.features ?? [];
          const shRho = "0.8";
          const shSeries: BarSeries[] = [
            ...(sh.e8_mix ? [{ id: "ddqn_reject_mix", label: "DDQN agents + Reject", values: feats.map((f) => { const m = sh.e8_mix.rhos[shRho].features[f]; return { mean: -m.mean_diff, ci: m.ci, n: m.n }; }) }] : []),
            ...(sh.main_v2 ? [{ id: "ddqn", label: "DDQN agents (3 actions)", values: feats.map((f) => { const m = sh.main_v2.rhos[shRho].features[f]; return { mean: -m.mean_diff, ci: m.ci, n: m.n }; }) }] : []),
          ];
          const used = sh.e8_mix ? feats.filter((f) => sh.e8_mix.used[f]).map((f) => FEATURE_LABEL[f] ?? f) : [];
          const notUsed = sh.e8_mix ? feats.filter((f) => !sh.e8_mix.used[f]).map((f) => FEATURE_LABEL[f] ?? f) : [];
          return (
            <>
              <h2>1 · Every load from light to overload</h2>
              {sw ? (
                <Card className="flat"><ChartFrame title="Goodput as the load rises" better="higher"
                  tip={<><b>How to read it.</b> Left is a quiet cluster, right is an overloaded one (ρ = 1 means requests arrive as fast as the cluster can serve them). Each line is one policy on the same traffic, mean over 5 seeds. Where the strong central rule (SED global) falls to almost zero, its queues have filled and nearly every request is late.</>}
                  reading={<>{(["route_to_fast_shed", "route_to_fast", "sed_global"] as const).map((ref) => { const c = verdictCounts(sw.diff[ref]); return <p key={ref}><b>Agents + Reject vs {styleOf(ref).label}:</b> better at {c.beats}, tied at {c.ties}, worse at {c.loses} of {sw.rhos.length} loads.</p>; })}<p className="muted" style={{ margin: 0 }}>“Better” means the paired 95% interval is above zero and the gain is over 0.01 req/s (rule fixed in ADR-032).</p></>}>
                  <LineChart title="Goodput as the load rises" xLabel="offered load ρ" yLabel="goodput (req/s)" series={sweepSeries} />
                </ChartFrame></Card>
              ) : <div className="notrun"><b>Load sweep: not run</b></div>}

              <h2>2 · One fast server suddenly slows down</h2>
              {dg ? (
                <Card className="flat"><ChartFrame title="Goodput after one fast server becomes 3 times slower" better="higher"
                  tip={<><b>How to read it.</b> Halfway through the traffic, one of the two fast servers becomes 3 times slower, something none of the agents saw in training and none of the routers is told about. A rule that always sends work to "the fast servers" keeps feeding the slowed one. Bars show goodput over the whole run with the slowdown; whiskers are 95% intervals over 5 seeds.</>}
                  reading={<>{dRhos.map((r) => { const e = dg.rhos[r]; const m = e.agents_minus; return <p key={r}><b>ρ = {r}:</b> the slowdown costs the agents + Reject {fmt(e.policies.ddqn_agents.loss[0], 3)} req/s, the shed rule {fmt(e.policies.route_to_fast_shed?.loss[0], 3)}, route to fast {fmt(e.policies.route_to_fast.loss[0], 3)}, SED global {fmt(e.policies.sed_global.loss[0], 3)}. Against route to fast: {m.route_to_fast.beats ? "better" : m.route_to_fast.loses ? "worse" : "tie"}; against the shed rule: {m.route_to_fast_shed?.beats ? "better" : m.route_to_fast_shed?.loses ? "worse" : "tie"}.</p>; })}</>}>
                  <BarsCI groups={dRhos} series={degSeries} xLabel="offered load ρ" yLabel="goodput with the slowdown (req/s)" title="Goodput with one fast server slowed" />
                </ChartFrame></Card>
              ) : <div className="notrun"><b>Degradation test: not run</b></div>}

              <h2>3 · Which inputs do the agents rely on?</h2>
              {shSeries.length ? (
                <Card className="flat"><ChartFrame title="Goodput lost when one input is scrambled (ρ = 0.8)"
                  tip={<><b>How to read it.</b> We scramble one thing the agent sees (replace it with a random value of the same kind) and measure how much goodput drops. A big drop means the agent relies on that input. The hand-written rules use none of these inputs except which servers are fast. Scrambling creates situations the agent never saw, so a drop shows reliance, not that the input is used well.</>}
                  reading={sh.e8_mix ? <><p><b>Agents + Reject rely on:</b> {used.join(", ") || "none"}.</p><p><b>Not clearly:</b> {notUsed.join(", ") || "none"}.</p></> : undefined}>
                  <BarsCI groups={feats.map((f) => FEATURE_LABEL[f] ?? f)} series={shSeries} xLabel="scrambled input" yLabel="goodput lost (req/s)" title="Goodput lost per scrambled input" digits={3} />
                </ChartFrame></Card>
              ) : <div className="notrun"><b>Input scrambling: not run</b></div>}

              <h2>4 · Traffic the agents were never trained on</h2>
              {d.shift ? (
                <Card className="flat"><ChartFrame title="Goodput on unseen traffic patterns (no retraining)" better="higher"
                  tip={<><b>How to read it.</b> The same trained agents, not retrained, on two kinds of traffic they never saw. <b>Load ramp</b>: the load goes from light to full overload and back within one run. <b>Code traffic</b>: requests from a code assistant, with prompts about twice as long and arriving in big bursts; even the lightest of these three settings overloads the cluster, so most policies collapse. Bars: mean over 5 seeds with 95% intervals.</>}
                  reading={<>{Object.entries(d.shift.conditions).map(([c, e]: [string, any]) => <p key={c}><b>{c === "ramp" ? "Load ramp" : `Code traffic, rate of ρ ${c.split("_")[1]}`}:</b> against the shed rule {e.agents_minus.route_to_fast_shed.beats ? "better" : e.agents_minus.route_to_fast_shed.loses ? "worse" : "tie"}; against route to fast {e.agents_minus.route_to_fast.beats ? "better" : e.agents_minus.route_to_fast.loses ? "worse" : "tie"}; against SED global {e.agents_minus.sed_global.beats ? "better" : e.agents_minus.sed_global.loses ? "worse" : "tie"}. {e.holds_up ? "Holds up without retraining." : "Would need retraining to match the shed rule."}</p>)}</>}>
                  <BarsCI groups={Object.keys(d.shift.conditions).map((c) => (c === "ramp" ? "load ramp" : `code ${c.split("_")[1]}`))}
                    series={[["agents", "ddqn_reject_mix", "DDQN agents + Reject"], ["route_to_fast_shed", "route_to_fast_shed", undefined], ["route_to_fast", "route_to_fast", undefined], ["sed_global", "sed_global", undefined], ["sed_local_full", "sed_local_full", undefined]].map(([k, id, label]) => ({ id: id as string, label: label as string | undefined, values: Object.values(d.shift.conditions).map((e: any) => pair(e.policies[k as string].goodput)) }))}
                    xLabel="traffic" yLabel="goodput (req/s)" title="Goodput on unseen traffic" />
                </ChartFrame></Card>
              ) : <div className="notrun"><b>Shift test: not run</b></div>}
              <SourceNote source={env.source} />
            </>
          );
        }}
      </Loaded>
      <LayoutSection />
      <LiveRunsSection />
    </>
  );
}

function LayoutSection() {
  const ds = useData();
  const s = useLoad(() => ds.getLayout(), []);
  return (
    <>
      <h2>5 · A different cluster: one fast server and three slow ones</h2>
      <Loaded state={s} what="Layout test (ADR-035)">
        {(d, env) => {
          const rhos = ["0.5", "0.8", "0.95"];
          const order: [string, string][] = [["agents", "ddqn_reject_mix"], ["route_to_fast_shed_tau", "route_to_fast_shed_tau"], ["route_to_fast_shed", "route_to_fast_shed"], ["route_to_fast", "route_to_fast"], ["sed_global", "sed_global"], ["sed_local_full", "sed_local_full"], ["random", "random"]];
          const series: BarSeries[] = order.map(([k, id]) => ({ id, label: k === "agents" ? "DDQN agents + Reject (retrained for this layout)" : undefined, values: rhos.map((r) => pair(d.rhos[r].policies[k].goodput)) }));
          const v = d.verdict;
          return (
            <Card className="flat"><ChartFrame title="Goodput with one fast and three slow servers" better="higher"
              tip={<><b>What this tests.</b> The hand-written rules were designed for two fast and two slow servers. Here the cluster has one fast and three slow ones. The agents were retrained for it with exactly the same recipe and no code changes. The unchanged rules show what happens if nobody touches them; the rewritten rule is what a person would write for this layout, with its one threshold tuned on training traffic only. Load ρ is a share of this cluster's own capacity{d.lambda_sat_rps ? ` (${fmt(d.lambda_sat_rps, 2)} req/s)` : ""}.</>}
              reading={<><p><b>{v.head}</b></p>
                <p>Retraining took the agents {d.agents_training_minutes ? `about ${fmt(d.agents_training_minutes, 0)} minutes` : "one training run"} and no code changes; the rewritten rule needed a new rule class and a tuning sweep (best threshold {d.tau}). Pass/fail rule fixed in ADR-035 before the run.</p>
                <p className="muted" style={{ margin: 0 }}>Drop rates at ρ 0.95: agents {fmt(d.rhos["0.95"].policies.agents.drop_rate * 100, 1)}%, rewritten rule {fmt(d.rhos["0.95"].policies.route_to_fast_shed_tau.drop_rate * 100, 1)}%, unchanged shed rule {fmt(d.rhos["0.95"].policies.route_to_fast_shed.drop_rate * 100, 1)}%.</p></>}>
              <BarsCI groups={rhos} series={series} xLabel="offered load ρ (share of this cluster's capacity)" yLabel="goodput (req/s)" title="Goodput, one fast and three slow servers" />
            </ChartFrame><SourceNote source={env.source} /></Card>
          );
        }}
      </Loaded>
    </>
  );
}

function LiveRunsSection() {
  const ds = useData();
  const s = useLoad(() => ds.getLiveRuns(), []);
  return (
    <>
      <h2>6 · The real servers</h2>
      <Loaded state={s} what="Real-server runs">
        {(d, env) => (
          <Card className="flat">
            {d.capacity && <p className="lead" style={{ marginBottom: 12 }}>The measured capacity of the real cluster is <b>{fmt(d.capacity.lambda_sat_rps, 2)} requests per second</b>{d.capacity.quick ? " (a quick estimate)" : ""}; load ρ on the Live page is a share of it.</p>}
            {(() => {
              const frame = (c: any, short: boolean) => (
                <ChartFrame key={c.file} title={`${short ? "Short demo: " : ""}every policy on the same requests at ${fmt(c.rate_rps, 2)} requests per second, best first`} better="higher"
                  tip={`${short ? "A short live demo (about 45 s of traffic per policy), so each policy sees only about a dozen requests and the ranking is noisy. " : "The main live test on the real servers. "}Every policy replayed exactly the same requests, one after the other. The bar is goodput, requests per second that met both targets; the yellow tick is the arrival rate, the most any policy could reach. Refused requests never count as good, so the refused share is shown beside each bar. One run per policy is an anecdote, not a result.`}
                  reading={<p><b>Highest in this run: {c.ranking[0].label}.</b> {c.rho != null ? `Load ρ ${c.rho} of the measured capacity (${fmt(c.rate_rps, 2)} req/s)` : `${fmt(c.rate_rps, 2)} req/s`}, {c.seconds} s of traffic per policy{c.drain_s ? ` plus at most ${c.drain_s} s to finish` : ""}, seed {c.seed}, {c.same_slice ? "identical requests for every policy" : "slices differ"}.</p>}>
                  <RankedBars rows={c.ranking} capacity={c.rate_rps} />
                </ChartFrame>
              );
              const latest = (kinds: string[]) => { const m = new Map<number, any>(); for (const c of d.comparisons ?? []) if (kinds.includes(c.kind ?? "guided")) m.set(c.rate_rps, c); return [...m.values()].sort((x, y) => x.rate_rps - y.rate_rps); };
              const main = latest(["main"]), other = latest(["quick", "guided"]);
              return (
                <>
                  {main.map((c) => frame(c, false))}
                  {other.length > 0 && <details style={{ marginTop: 12 }}><summary>Short demo runs from the Live page ({other.length})</summary>{other.map((c) => frame(c, true))}</details>}
                </>
              );
            })()}
            {d.runs.length > 0 ? (
              <div className="tablewrap" style={{ marginTop: 16 }}><table>
                <thead><tr><th>policy</th><th>ρ</th><th>seed</th><th>slice</th><th>goodput (req/s)</th><th>met both targets</th><th>dropped</th><th>first token p95 (s)</th><th>cost / request</th></tr></thead>
                <tbody>{d.runs.map((r: any) => <tr key={r.run_id}><td style={{ textAlign: "left" }}>{styleOf(r.policy === "ddqn_agents" ? "ddqn_reject_mix" : r.policy).label}</td><td>{r.rho ?? "n/a"}</td><td>{r.seed}</td><td>{r.slice}</td><td>{fmt(r.metrics.goodput_rps, 3)}</td><td>{fmt(r.metrics.sla_attainment * 100, 0)}%</td><td>{fmt(r.metrics.drop_rate * 100, 1)}%</td><td>{r.metrics.ttft_p95 == null ? "n/a" : fmt(r.metrics.ttft_p95, 2)}</td><td>{r.metrics.cost_per_request == null ? "n/a" : fmt(r.metrics.cost_per_request, 1)}</td></tr>)}</tbody>
              </table></div>
            ) : <p className="muted">No finished run yet.</p>}
            <p className="muted" style={{ marginTop: 10 }}>Real llama-servers on one machine, replaying the same held-out traffic one policy after the other (same slice id = identical requests). One run per policy is an anecdote, not a result; it shows that the system works on real servers and how its live numbers compare with the simulation. Synthetic prices per busy second.</p>
            <SourceNote source={env.source} />
          </Card>
        )}
      </Loaded>
    </>
  );
}
