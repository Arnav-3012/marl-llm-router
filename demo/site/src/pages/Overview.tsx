import { Link } from "../router";
import { Card, Info, Loaded, Num, NotRun, Reveal, SourceNote, Term, useData, useLoad, fmt } from "../ui";
import type { Metric } from "../data/types";
import { IsoCluster } from "../viz/IsoCluster";
import { AgentExplainer, useMix } from "../viz/AgentExplainer";
import { Pipeline, type Stage, type StageStatus } from "../viz/Pipeline";
import { Lifecycle } from "../viz/Lifecycle";
import { WhyHard } from "../viz/WhyHard";

type Q1 = { rho: string; ddqn: Metric | null; sed_local_full: Metric; sed_global: Metric; route_to_fast?: Metric | null; cache_aware_local_full: Metric } | null;

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
  const mix = useMix();
  const layoutD = useLoad(() => ds.getLayout(), []);
  const retrainMin: number | null = layoutD.env?.data?.agents_training_minutes ?? null;

  const seeds = overview.env?.data?.experiments_finished_seeds ?? {};
  const m = method.env?.data;
  const realRuns: number = overview.env?.data?.real_server_runs ?? 0;
  const stages: Stage[] = [
    { key: "profile", title: "Profile", note: "real llama.cpp, 5 repeats", status: (m?.profiling_fit ? "done" : "not_run") as StageStatus },
    { key: "calibrate", title: "Calibrate", note: "a, t0, k, cache, interference", status: (m?.calibration ? "done" : "not_run") as StageStatus },
    { key: "train", title: "Train", note: "independent DDQN in the simulator", status: ((seeds.main ?? 0) >= 5 ? "done" : (seeds.main ?? 0) > 0 ? "partial" : "not_run") as StageStatus },
    { key: "deploy", title: "Deploy", note: realRuns > 0 ? `real servers: ${realRuns} run${realRuns > 1 ? "s" : ""}` : "real servers: not yet run", status: (realRuns > 0 ? "partial" : "not_run") as StageStatus },
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
            {(() => {
              const n = overview.env?.data?.real_server_runs ?? 0;
              const tip = "What this build does not show: the learned agents are trained and compared in a simulator calibrated on real servers (5 repeats of each measurement, one machine). The break-it experiments and a centralised baseline were not run; a changed hardware mix (one fast, three slow servers) is on the Stress tests page.";
              return n > 0
                ? <span className="pill ok" title={tip}><span className="dot" />simulation calibrated on real servers · {n} real-server run{n > 1 ? "s" : ""}</span>
                : <span className="pill warn" title={tip}><span className="dot" />simulation calibrated on real servers · no real-server run yet</span>;
            })()}
          </div>
        </div>
        <div className="hero-stage">
          <div className="hero-frame"><IsoCluster mode="hero" mixFast={mix.fast} mixSlow={mix.slow} height={430} /></div>
          <p className="hero-note">Illustration, not measured data. The mix of accept, forward, defer and reject is the trained agents' measured mix; scroll to turn the view and raise the load.</p>
        </div>
      </section>

      <section className="block">
        <Reveal><div className="eyebrow">the problem</div><h2>Serving language models is a scheduling problem with a price tag</h2></Reveal>
        <div className="grid g2">
          <Reveal><Card>
            <h3>What a request costs</h3>
            <p className="muted">A request has two phases. <Term tip="Prefill: the model reads the whole prompt in one go before it can say anything. Longer prompts take longer, and the time grows faster than the length.">Prefill</Term> reads the whole prompt at once; it decides the <Term tip="Time to first token: how long the user waits before the first word of the answer appears. Our target is 5 seconds.">time to first token</Term>.{" "}
              <Term tip="Decode: the model writes the answer one token (roughly a word piece) at a time. Several requests share each step, so a busy server writes more slowly for everyone.">Decode</Term> writes the answer one token at a time, shared with the other requests in the batch; it decides the <Term tip="Time per output token: how long each further word piece takes. Our target is 0.1 seconds, which is 10 tokens per second, about reading speed.">time per output token</Term>.</p>
            <p className="muted">A request is <i>good</i> only if it meets both targets. The headline metric is <Term tip="Goodput: requests per second that finished and met both targets. Late answers and refused requests do not count, so a policy cannot look good by serving many requests slowly.">goodput</Term>: good requests per second, not raw throughput. Servers also keep a <Term tip="KV cache: the server's working memory for the conversations it is serving. When it is full, new requests must wait. A follow-up message is faster on the server that still holds its conversation in this cache.">KV cache</Term> of open conversations, which is why a follow-up message is fastest on the server that served the previous one.</p>
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
        <p className="muted" style={{ marginTop: 12 }}>Each stage shows what the result files say, not what was planned. Deploy is marked partial: the router runs on the real servers, and the first real runs showed the servers slow down more under load than the simulator predicted (Stress tests page).</p>
        <div style={{ marginTop: 32 }}><h3 style={{ marginBottom: 12 }}>The life of one request</h3><Lifecycle /></div>
        <div style={{ marginTop: 40 }}>
          <Reveal><div className="eyebrow">the agents</div><h2>What can an agent do with a request?</h2>
            <p className="lead">Each of the four servers has one small agent. It looks at its own server and at how busy the others are, and picks one of four actions. Pick one below to watch a request take that path.</p></Reveal>
          <AgentExplainer />
        </div>
        <div className="grid g2" style={{ marginTop: 32 }}>
          <Reveal><Card><div className="label">what it is rewarded for</div><p className="muted" style={{ margin: 0 }}>+10 when a request meets both targets (first word within 5 seconds, then at least 10 words per second), −10 when it misses one, −5 when it is dropped. Every agent that touched a request shares that reward, plus a small cost for slow or expensive service and for passing a request on. Agents learn only from these outcomes.</p></Card></Reveal>
          <Reveal delay={60}><Card><div className="label">why the reward matters</div><p className="muted" style={{ margin: 0 }}>Nobody tells an agent which servers are fast or when to refuse a request. If refusing pays better than answering late, it learns to refuse; if passing a request on is cheap, it learns to pass. That is why we also test it against a hand-written rule that was given the answer.</p></Card></Reveal>
        </div>
      </section>

      <section className="block">
        <Reveal><div className="eyebrow">four questions</div><h2>What the results say</h2>
          <p className="lead">Each card answers one question we fixed before running anything. Numbers are goodput (requests per second that met both targets) on held-out traffic, mean ± 95% interval over 5 seeds.</p></Reveal>
        <Loaded state={overview} what="Headline results">
          {(d, env) => {
            const q = d.q1_goodput as Q1;
            return (
              <div className="qgrid">
                <Reveal><Card className="qcard">
                  <div className="qhead"><span className="qnum">Q1</span><span className="label">Do learned agents match the standard routing rules?</span>
                    <Info text="Heavy load (ρ 0.8 = 80% of the cluster's capacity). The agents here are the first trained agents with three actions (accept, forward, defer); they see only their own server and their neighbours. SED global sees every server, an advantage the agents do not have." /></div>
                  {q ? (
                    <>
                      <div className="stat"><Num m={q.ddqn} /> <small>req/s, learned agents at ρ 0.8</small></div>
                      <table className="qtable"><tbody>
                        <tr><td>SED global <span className="dim">(sees every server)</span></td><td><Num m={q.sed_global} /></td></tr>
                        {q.route_to_fast && <tr><td>Route-to-fast rule</td><td><Num m={q.route_to_fast} /></td></tr>}
                        <tr><td>SED local</td><td><Num m={q.sed_local_full} /></td></tr>
                        <tr><td>Cache-aware local</td><td><Num m={q.cache_aware_local_full} /></td></tr>
                      </tbody></table>
                      <p className="qverdict">{verdict(q.ddqn, { "SED local": q.sed_local_full, "SED global": q.sed_global, ...(q.route_to_fast ? { "route-to-fast rule": q.route_to_fast } : {}), "cache-aware local": q.cache_aware_local_full })} With the same local view, the standard rules are far behind.</p>
                    </>
                  ) : <NotRun what="Q1 goodput comparison" reason="baselines or the learned runs are not finished." />}
                  <Link className="qlink" to="/baselines">Full table and all loads →</Link>
                </Card></Reveal>
                <Reveal delay={70}><Card className="qcard">
                  <div className="qhead"><span className="qnum">Q4</span><span className="label">What if the agents may refuse requests?</span>
                    <Info text="Overload (ρ 0.95). Agents trained with a fourth action, Reject, from scratch. Policies that cannot refuse keep serving requests that are already too late, so almost nothing meets its deadline. Refusing is only honest if the refused share is shown, so it is in the last row." /></div>
                  {d.q4_reject ? (() => {
                    const r = d.q4_reject.rhos["0.95"];
                    const s = r.reject_scratch!;
                    return (
                      <>
                        <div className="stat"><Num m={s.goodput} /> <small>req/s, agents with Reject at ρ 0.95</small></div>
                        <table className="qtable"><tbody>
                          <tr><td>Route-to-fast + shed rule</td><td><Num m={r.route_to_fast_shed!.goodput} /></td></tr>
                          <tr><td>Route-to-fast rule</td><td><Num m={r.route_to_fast!.goodput} /></td></tr>
                          <tr><td>Agents without Reject</td><td><Num m={r.v2!.goodput} /></td></tr>
                          <tr><td>SED global</td><td><Num m={r.sed_global!.goodput} /></td></tr>
                          <tr className="qsep"><td>Refused by the agents</td><td>{((s.drop_rate.mean ?? 0) * 100).toFixed(1)}%</td></tr>
                        </tbody></table>
                        <p className="qverdict">{verdict(s.goodput, { "SED global": r.sed_global!.goodput, "route-to-fast rule": r.route_to_fast!.goodput, "route-to-fast + shed rule": r.route_to_fast_shed!.goodput })} Both refuse a similar share of requests to get there.</p>
                      </>
                    );
                  })() : <NotRun what="Reject experiment (E8)" reason="the E8 runs have not been made." />}
                  <Link className="qlink" to="/baselines">Full table and all loads →</Link>
                </Card></Reveal>
                <Reveal delay={140}><Card className="qcard">
                  <div className="qhead"><span className="qnum">Q2</span><span className="label">Can one weight trade cost against speed?</span>
                    <Info text="λ is the weight of the cost term in the reward. We trained agents with λ = 0, 1 and 2 and placed each on a cost-versus-latency chart with the fixed rules. A trade-off would show as a curve of settings: cheaper but slower, or faster but dearer." /></div>
                  {d.q2_pareto_available ? <p className="qbody">{d.q2_frontier ? (d.q2_frontier.on_frontier.length <= 1 ? `No trade-off found: only ${d.q2_frontier.on_frontier.length ? d.q2_frontier.on_frontier[0] : "none of the learned settings"} of the ${d.q2_frontier.learned.length} learned settings is on the cost–latency frontier.` : `${d.q2_frontier.on_frontier.length} of the ${d.q2_frontier.learned.length} learned settings are on the cost–latency frontier.`) : "The λ runs are compared with fixed rules on the Pareto page."}</p> : <NotRun what="Cost–latency frontier (E3)" reason="the λ sweep has not been run." />}
                  <p className="qbody muted">Why: the slow server is not cheaper per typical request. It is cheaper per second but takes so much longer that a request costs more there. What λ did change is reliability: λ = 1 trained well on every seed.</p>
                  <Link className="qlink" to="/pareto">Pareto page →</Link>
                </Card></Reveal>
                <Reveal delay={210}><Card className="qcard">
                  <div className="qhead"><span className="qnum">Q3</span><span className="label">How much does seeing the neighbours help?</span>
                    <Info text="k is how many other servers an agent can see. k = 0: only its own server. k = full: all three others. Same training, same traffic; only the view changes." /></div>
                  {d.q3_observability_available ? <p className="qbody">Agents that see only their own server (k = 0) reach under half the goodput of agents that see their neighbours, at both loads tested. Seeing how busy the others are is what makes passing a request on useful.</p> : <NotRun what="k=0 vs k=full (E4)" reason="the k ablation has not been run." />}
                  <p className="qbody muted">Not built: a centralised learned router with a full view, so the cost of being decentralised is not measured.</p>
                  <Link className="qlink" to="/observability">Observability page →</Link>
                </Card></Reveal>
                <div style={{ gridColumn: "1 / -1" }}><SourceNote source={env.source} /></div>
              </div>
            );
          }}
        </Loaded>
      </section>

      <section className="block">
        <Reveal><div className="eyebrow">why learn it at all</div><h2>What each approach asks of the people running it</h2>
          <p className="lead">A hand-written shed rule matched our agents everywhere we measured, so the case for learning is not a higher score. It is what you have to know and do to get that score. This table is what we actually saw in this project.</p></Reveal>
        <div className="grid g2">
          <Reveal><Card className="qcard">
            <div className="qhead"><span className="qnum">rule</span><span className="label">Hand-written rule (route to fast + shed)</span></div>
            <ul className="plain">
              <li><b>Must be told</b> which servers are fast, and that a request with no time left should be refused.</li>
              <li><b>Needs a person</b> to notice the failure first, work out the fix, write it and test it. Ours was written after we diagnosed what went wrong with simple routing.</li>
              <li><b>For a different cluster</b> (one fast, three slow) we wrote a new rule class and ran a tuning sweep for its threshold{layoutD.env?.data?.tau != null ? ` (best value ${layoutD.env.data.tau})` : ""}. The old rule still worked there.</li>
              <li><b>Cheap to run:</b> no training, no simulator, nothing to retrain.</li>
            </ul>
          </Card></Reveal>
          <Reveal delay={70}><Card className="qcard">
            <div className="qhead"><span className="qnum">agents</span><span className="label">Learned agents (Double DQN + Reject)</span></div>
            <ul className="plain">
              <li><b>Told nothing</b> about which servers are fast or when to refuse. They found both from outcomes alone and reached the rule's goodput (a tie at every load).</li>
              <li><b>The goal is written as a reward</b> (deadlines, a refusal penalty, a cost weight). Changing the goal means changing numbers and retraining, not redesigning a rule.</li>
              <li><b>For the different cluster</b> the same recipe was retrained with no code change{retrainMin != null ? ` in about ${Math.round(retrainMin)} minutes` : ""}.</li>
              <li><b>Costs:</b> a profiling run and a simulator first, training time, and retraining for new traffic or hardware. They refuse about 7% of requests at overload, as the rule does.</li>
            </ul>
          </Card></Reveal>
        </div>
        <p className="muted" style={{ marginTop: 14 }}><b>What we did not prove.</b> In our layout test the unchanged old rule still worked, so we cannot say retraining is easier than rewriting. The honest case for learning is narrower: when nobody can hand-design and maintain the rule, or the objective keeps changing, a learner that reaches the expert's score from outcomes alone is a reasonable starting point. Where an expert rule is available and the setup is stable, the rule is simpler and just as good here.</p>
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
            ["Not run", "Break-it experiments, E5 burst test, E6 specialisation, centralised DQN and Docker/Space/video. Real-server runs are short (one run per policy), so they are anecdotes, not statistics."],
          ].map(([t, d], i) => (
            <Reveal key={t} delay={i * 40}><Card><h3>{t}</h3><p className="muted" style={{ margin: 0 }}>{d}</p></Card></Reveal>
          ))}
        </div>
      </section>
    </>
  );
}
