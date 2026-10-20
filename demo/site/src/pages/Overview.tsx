import { Link } from "../router";
import { Card, Loaded, Num, NotRun, Reveal, SourceNote, useData, useLoad, fmt } from "../ui";
import type { Metric } from "../data/types";
import { HeroField } from "../viz/HeroField";
import { Pipeline, type Stage, type StageStatus } from "../viz/Pipeline";
import { Lifecycle } from "../viz/Lifecycle";
import { WhyHard } from "../viz/WhyHard";

type Q1 = { rho: string; ddqn: Metric | null; sed_local_full: Metric; sed_global: Metric; cache_aware_local_full: Metric } | null;

/** Plain-language verdict from means and 95% CIs only; never claims more than the intervals allow. */
function verdict(ddqn: Metric | null, others: Record<string, Metric>): string {
  if (!ddqn || ddqn.mean == null) return "The learned agents have not been run yet, so there is no comparison.";
  const best = Object.entries(others).filter(([, m]) => m?.mean != null).sort((a, b) => (b[1].mean ?? 0) - (a[1].mean ?? 0))[0];
  if (!best) return "No baseline result to compare against.";
  const [name, m] = best;
  const lo = ddqn.mean - (ddqn.ci ?? 0), hi = ddqn.mean + (ddqn.ci ?? 0), blo = (m.mean ?? 0) - (m.ci ?? 0), bhi = (m.mean ?? 0) + (m.ci ?? 0);
  if (ddqn.ci == null || m.ci == null) return "Fewer than two seeds: no interval, so no claim.";
  if (lo > bhi) return `The learned agents' goodput is higher than the best baseline (${name}) and the 95% intervals do not overlap.`;
  if (hi < blo) return `The learned agents' goodput is LOWER than the best baseline (${name}) and the 95% intervals do not overlap.`;
  return `The learned agents and the best baseline (${name}) are within each other's 95% intervals: no difference can be claimed from these seeds.`;
}

export function Overview() {
  const ds = useData();
  const overview = useLoad(() => ds.getOverview(), []);
  const traces = useLoad(() => ds.getTraces(), []);
  const method = useLoad(() => ds.getMethod(), []);

  const seeds = overview.env?.data?.experiments_finished_seeds ?? {};
  const m = method.env?.data;
  const stages: Stage[] = [
    { key: "profile", title: "Profile", note: "real llama.cpp, 5 repeats", status: (m?.profiling_fit ? "done" : "not_run") as StageStatus },
    { key: "calibrate", title: "Calibrate", note: "a, t0, k, cache, interference", status: (m?.calibration ? "done" : "not_run") as StageStatus },
    { key: "train", title: "Train", note: "independent DDQN in the simulator", status: ((seeds.main ?? 0) >= 5 ? "done" : (seeds.main ?? 0) > 0 ? "partial" : "not_run") as StageStatus },
    { key: "deploy", title: "Deploy", note: "real servers: not yet run", status: "not_run" },
    { key: "compare", title: "Compare", note: "baselines vs learned, 95% CI", status: ((seeds.baselines ?? 0) > 0 && (seeds.main ?? 0) > 0 ? "done" : (seeds.baselines ?? 0) + (seeds.main ?? 0) > 0 ? "partial" : "not_run") as StageStatus },
  ];

  return (
    <>
      <section className="hero">
        <div>
          <div className="eyebrow">independent Double-DQN · LLM request routing</div>
          <h1><span className="gradient-text">Four small agents learn to route</span><br />traffic across unequal LLM servers.</h1>
          <p className="lead" style={{ marginTop: 16 }}>
            Some servers are fast and expensive, some slow and cheap. Each server gets a tiny learning agent that decides, for every request,
            whether to take it, pass it on or wait. We train them in a simulator calibrated on real llama.cpp servers and measure them honestly against strong rules of thumb.
          </p>
          <div className="controls">
            <Link className="btn primary" to="/baselines">See the results</Link>
            <Link className="btn" to="/replay">Watch a recorded episode</Link>
            <span className="pill warn" title="what this build did not do"><span className="dot" />demo build: 5-repeat profiling, no break-its, no real-server replay</span>
          </div>
        </div>
        <HeroField />
      </section>

      <section className="block">
        <Reveal><div className="eyebrow">the problem</div><h2>Serving language models is a scheduling problem with a price tag</h2></Reveal>
        <div className="grid g2">
          <Reveal><Card>
            <h3>What a request costs</h3>
            <p className="muted">A request has two phases. <b style={{ color: "var(--text)" }}>Prefill</b> reads the whole prompt at once; it decides the <b style={{ color: "var(--text)" }}>time to first token</b> (TTFT).
              <b style={{ color: "var(--text)" }}> Decode</b> writes the answer one token at a time, shared with the other requests in the batch; it decides the <b style={{ color: "var(--text)" }}>time per output token</b> (TPOT).</p>
            <p className="muted">A request is <i>good</i> only if it meets both targets. The headline metric is <b style={{ color: "var(--text)" }}>goodput</b>: good requests per second, not raw throughput.</p>
          </Card></Reveal>
          <Reveal delay={80}><Card>
            <h3>What the cluster looks like</h3>
            <p className="muted">Four servers on one machine in two classes: fast-expensive (Qwen2.5-3B on the GPU) and slow-cheap (Qwen2.5-1.5B on the CPU only). Prices are <i>synthetic</i> per busy second.
              A router that ignores the difference wastes money or misses its targets; a router that sends everything to the fast pair overloads it.</p>
            <p className="muted">There is no central scheduler here: each agent sees only its own server and, optionally, its neighbours.</p>
          </Card></Reveal>
        </div>
      </section>

      <section className="block">
        <Reveal><div className="eyebrow">why it is hard</div><h2>Four reasons a fixed rule is not enough</h2></Reveal>
        <WhyHard />
      </section>

      <section className="block">
        <Reveal><div className="eyebrow">our approach</div><h2>Profile real servers, learn in a simulator, compare honestly</h2></Reveal>
        <Card className="flat"><Pipeline stages={stages} /></Card>
        <p className="muted" style={{ marginTop: 12 }}>Each stage shows what the result files say, not what was planned. Deploy stays “not run”: the learned policy has not been tried on the real servers.</p>
        <div style={{ marginTop: 32 }}><h3 style={{ marginBottom: 12 }}>The life of one request</h3><Lifecycle /></div>
        <div className="grid g3" style={{ marginTop: 32 }}>
          <Reveal><Card><div className="label">what an agent sees</div><p className="muted" style={{ margin: 0 }}>Seven numbers in [0, 1]: its own expected wait and KV-cache fullness, the prompt size, the slack left against the target, hops so far, the neighbours’ mean wait (0 when it cannot see any) and the fraction of the prompt already cached here.</p></Card></Reveal>
          <Reveal delay={60}><Card><div className="label">what it can do</div><p className="muted" style={{ margin: 0 }}><b style={{ color: "var(--text)" }}>Accept</b> the request on its own server, <b style={{ color: "var(--text)" }}>Forward</b> it (at most twice) to the neighbour with the least expected wait, or <b style={{ color: "var(--text)" }}>Defer</b> it (a limited number of times). Illegal actions are masked.</p></Card></Reveal>
          <Reveal delay={120}><Card><div className="label">what it is rewarded for</div><p className="muted" style={{ margin: 0 }}>+10 for meeting both targets, −10 for missing one, −5 for a drop, shared by every agent that acted on the request; minus the serving agent’s cost (λ × price × busy seconds) and a KV-pressure term; minus a small cooperation term for the cluster breach rate.</p></Card></Reveal>
        </div>
      </section>

      <section className="block">
        <Reveal><div className="eyebrow">three questions</div><h2>What the results say</h2></Reveal>
        <Loaded state={overview} what="Headline results">
          {(d, env) => {
            const q = d.q1_goodput as Q1;
            return (
              <div className="grid g3">
                <Reveal><Card>
                  <div className="label">Q1 · do learned agents match or beat SED and cache-aware?</div>
                  {q ? (
                    <>
                      <div className="stat"><Num m={q.ddqn} /> <small>req/s goodput at ρ 0.8, DDQN</small></div>
                      <table><tbody>
                        <tr><td>SED local, k=full</td><td><Num m={q.sed_local_full} /></td></tr>
                        <tr><td>SED global</td><td><Num m={q.sed_global} /></td></tr>
                        <tr><td>Cache-aware local</td><td><Num m={q.cache_aware_local_full} /></td></tr>
                      </tbody></table>
                      <p style={{ marginTop: 12 }}>{verdict(q.ddqn, { "SED local": q.sed_local_full, "SED global": q.sed_global, "cache-aware local": q.cache_aware_local_full })}</p>
                      <Link to="/baselines">Full table and all loads →</Link>
                    </>
                  ) : <NotRun what="Q1 goodput comparison" reason="baselines or the learned runs are not finished." />}
                </Card></Reveal>
                <Reveal delay={70}><Card>
                  <div className="label">Q2 · does λ trace a cost–latency frontier?</div>
                  {d.q2_pareto_available ? <p>Yes, there are λ runs to compare against fixed rules.</p> : <NotRun what="Cost–latency frontier (E3)" reason="the λ sweep has not been run." />}
                  <Link to="/pareto">Pareto page →</Link>
                </Card></Reveal>
                <Reveal delay={140}><Card>
                  <div className="label">Q3 · price of partial observability</div>
                  {d.q3_observability_available ? <p>k = 0 (blind) versus k = full (all neighbours) is on the observability page. The centralised reference was not built.</p> : <NotRun what="k=0 vs k=full (E4)" reason="the k ablation has not been run." />}
                  <Link to="/observability">Observability page →</Link>
                </Card></Reveal>
                <div style={{ gridColumn: "1 / -1" }}><SourceNote source={env.source} /></div>
              </div>
            );
          }}
        </Loaded>
      </section>

      <section className="block">
        <Reveal><div className="eyebrow">the data</div><h2>Real traffic, with a synthetic chat layer</h2></Reveal>
        <Loaded state={traces} what="Trace facts">
          {(t, env) => {
            const a = t.azure_conv as Record<string, any>;
            return (
              <>
                <div className="grid g4">
                  <Card><div className="label">requests (Azure conv 2023)</div><div className="stat">{fmt(a?.rows, 0)}</div></Card>
                  <Card><div className="label">window</div><div className="stat">{fmt((a?.duration_s ?? 0) / 60, 1)} <small>min</small></div></Card>
                  <Card><div className="label">mean arrival rate</div><div className="stat">{fmt(a?.mean_rate_rps, 2)} <small>req/s</small></div></Card>
                  <Card><div className="label">prompt tokens p99</div><div className="stat">{fmt(a?.prompt_tokens?.p99, 0)}</div></Card>
                </div>
                <p className="muted" style={{ marginTop: 12 }}>Arrival times and token counts come from the public Azure LLM Inference 2023 trace, rescaled to the target load. Azure has no conversation ids, so chat sessions are layered on with parameters measured on BurstGPT (an assumption, stated everywhere cache results appear).</p>
                <SourceNote source={env.source} />
              </>
            );
          }}
        </Loaded>
      </section>

      <section className="block">
        <Reveal><div className="eyebrow">honest limits</div><h2>What these results do not show</h2></Reveal>
        <div className="grid g2">
          {[
            ["One shared chip", "All four servers run on one Apple M4 Pro, so they interfere with each other. A real cluster would not share memory bandwidth."],
            ["Synthetic prices", "Class prices are made-up per-busy-second numbers with a rough real-GPU ratio. The cost axis is a design choice, not a bill."],
            ["One machine, 5-repeat profiling", "Calibration comes from one machine with 5 repeats per point, below the 10 the plan asks for. A full re-run is a later task."],
            ["Synthetic sessions", "Conversation structure is borrowed from BurstGPT and laid over Azure traffic; cache results hold only under that assumption."],
            ["Short window", "Training and held-out traffic come from about an hour of Azure conv 2023 (held-out ≈ 11.7 min), so results describe that traffic mix."],
            ["Not run", "Break-it experiments, E5 burst test, E6 specialisation, centralised DQN, real-server replay (sim-to-real gap) and Docker/Space/video."],
          ].map(([t, d], i) => (
            <Reveal key={t} delay={i * 40}><Card><h3>{t}</h3><p className="muted" style={{ margin: 0 }}>{d}</p></Card></Reveal>
          ))}
        </div>
      </section>
    </>
  );
}
