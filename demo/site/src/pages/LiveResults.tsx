// "Live results": the permanent record of the real-server tests, read from results/live/comparison_*.json (main tests only).
// Presenter view: the LATEST run at each load only (one table and one chart per load). Older runs are not deleted: they stay in
// results/live and on the Stress tests page (section 7), and the page says how many exist.
import { Card, ChartFrame, Loaded, PageHead, SourceNote, fmt } from "../ui";
import { Link } from "../router";
import { RankedBars } from "../viz/RankedBars";
import { useData, useLoad } from "../ui";

export function LiveResults() {
  const ds = useData();
  const s = useLoad(() => ds.getLiveRuns(), []);
  return (
    <>
      <PageHead eyebrow="Real servers · saved results" title="Live results">
        <p className="lead">Every policy replayed the same requests on four real llama-servers, one policy after the other. These are the saved results of the main tests; one run per policy is an anecdote, and this page shows the latest run at each load. The Live page runs new tests.</p>
      </PageHead>
      <Loaded state={s} what="Saved real-server results">
        {(d, env) => {
          const main = (d.comparisons ?? []).filter((c: any) => c.kind === "main").sort((x: any, y: any) => (x.rate_rps - y.rate_rps) || String(x.created).localeCompare(String(y.created)));
          const rates: number[] = Array.from(new Set(main.map((c: any) => c.rate_rps as number)));
          const loadName = (r: number) => (r <= 0.2 ? "Medium load" : "Heavy load");
          if (!main.length) return <Card className="flat"><p className="muted">No main real-server test has been saved yet. Run one from the <Link to="/live">Live page</Link>.</p></Card>;
          return (
            <>
              {rates.map((rate) => {
                const all = main.filter((c: any) => c.rate_rps === rate);
                const runs = all.slice(-1); // the presenter view: only the latest run at each load; older runs stay saved
                const policies: { policy: string; label: string }[] = runs[0].ranking.map((r: any) => ({ policy: r.policy, label: r.label }));
                const get = (c: any, p: string) => c.ranking.find((r: any) => r.policy === p);
                return (
                  <section key={rate} className="block" style={{ paddingTop: 8 }}>
                    <h2>{loadName(rate)}: {fmt(rate, 2)} requests per second</h2>
                    <p className="muted">{all.length > 1 ? `Latest of ${all.length} saved runs at this load; the counts vary from run to run, so treat it as an anecdote. ` : "One saved run at this load. "}{runs[0].seconds} s of identical traffic per policy{runs[0].drain_s ? ` plus at most ${runs[0].drain_s} s to finish` : ""}; {runs[0].ranking[0].n_arrived} requests per policy. {runs.some((c: any) => c.adaptive) ? "This run used the live router's measured server speeds (ADR-039)." : "No speed correction was active."}</p>
                    <Card className="flat">
                      <div className="tablewrap"><table>
                        <thead><tr><th>policy</th>{runs.map((c: any, i: number) => <th key={c.file} colSpan={2}>run {i + 1}{c.adaptive ? " · speed correction" : ""}</th>)}</tr>
                          <tr><th></th>{runs.map((c: any) => <><th key={`${c.file}a`}>met both targets</th><th key={`${c.file}b`}>first token p95 (s)</th></>)}</tr></thead>
                        <tbody>{policies.map((p) => (
                          <tr key={p.policy}><td style={{ textAlign: "left" }}>{p.label}</td>
                            {runs.map((c: any) => { const r = get(c, p.policy); return r ? <><td key={`${c.file}${p.policy}a`}>{r.n_sla_met} of {r.n_arrived} ({fmt(r.sla_attainment * 100, 0)}%) · refused {fmt(r.drop_rate * 100, 0)}%</td><td key={`${c.file}${p.policy}b`}>{r.ttft_p95 == null ? "n/a" : fmt(r.ttft_p95, 1)}</td></> : <td colSpan={2} key={`${c.file}${p.policy}x`}>not run</td>; })}
                          </tr>))}</tbody>
                      </table></div>
                      <p className="muted" style={{ marginTop: 10, fontSize: 13 }}>Ranked by goodput: {runs.map((c: any, i: number) => `run ${i + 1}: ${c.ranking.map((r: any) => r.label.replace(/^the /, "").replace(/ \(.*$/, "").replace(/, a strong classic rule/, "")).join(" > ")}`).join(". ")}.</p>
                    </Card>
                    {rate <= 0.2 && (() => {
                      const c = runs[0];
                      const served = (r: any) => Math.round(r.n_arrived * (1 - r.drop_rate));
                      const share = (r: any) => (served(r) ? Math.round((100 * r.n_sla_met) / served(r)) : 0);
                      const ag = get(c, "ddqn_agents"), rb = get(c, "ddqn_robust"), sh = get(c, "route_to_fast_shed"), sg = get(c, "sed_global");
                      const parts: string[] = [];
                      if (ag && sh) parts.push(`The final agents refused ${fmt(ag.drop_rate * 100, 0)}% of requests and, of the ${served(ag)} they served, ${share(ag)}% met both targets; the hand shed rule refused ${fmt(sh.drop_rate * 100, 0)}% and ${share(sh)}% of its ${served(sh)} served met them.`);
                      if (rb) parts.push(`The robust agents refused ${fmt(rb.drop_rate * 100, 0)}% and ${share(rb)}% of their ${served(rb)} served requests met both targets.`);
                      if (sg) parts.push(`SED global refused ${fmt(sg.drop_rate * 100, 0)}% and ${share(sg)}% of its ${served(sg)} served requests met them.`);
                      return (
                        <Card className="flat" style={{ marginTop: 14 }}>
                          <h3>Why the agents rank where they do at this load</h3>
                          <p className="muted">{parts.join(" ")}</p>
                          <ul className="plain">
                            <li><b>The cluster is busy, not overloaded.</b> At this load most requests can still be served in time, so the policy that refuses nothing keeps every request that would have made it. Refusing only pays off once the cluster is overloaded (see the heavy load).</li>
                            <li><b>The agents were trained in a simulator that is optimistic about busy servers.</b> Real busy servers write much more slowly than the simulator predicts, so the agents' wait estimates are too low. They accept some requests that then finish late, and they refuse some that would have been fine.</li>
                            <li><b>One short run.</b> A few dozen requests per policy: one or two requests change a share by several points, so these are likely reasons, not proven ones.</li>
                          </ul>
                          <p className="muted" style={{ fontSize: 13 }}>{c.adaptive ? "This run used the live router's measured server speeds (ADR-039), which corrects the estimates for every policy." : "No speed correction was active in this run. The router can measure the real server speeds and correct the estimates (ADR-039); a run with it is marked on this page."}</p>
                        </Card>
                      );
                    })()}
                    {runs.map((c: any, i: number) => (
                      <ChartFrame key={c.file} title={`Run ${i + 1} at ${fmt(rate, 2)} req/s, best first${c.adaptive ? " (speed correction)" : ""}`} better="higher"
                        tip="The bar is goodput: requests per second that met both targets (first word within 5 s, then at least 10 words per second). The yellow tick is the arrival rate, the most any policy could reach. Refused requests never count as good, so the refused share is shown beside each bar.">
                        <RankedBars rows={c.ranking} capacity={c.rate_rps} />
                      </ChartFrame>
                    ))}
                  </section>
                );
              })}
              <SourceNote source={env.source} />
              <p className="muted" style={{ fontSize: 13 }}>How to read this honestly: one run per policy and a few dozen requests each, so differences of a few requests can change on a repeat. Medium load: the cluster is busy but not overloaded and refusing helps little. Heavy load: the cluster is overloaded for every policy, and the policies that refuse keep the first-token latency low. More in the <Link to="/method">Method page</Link>.</p>
            </>
          );
        }}
      </Loaded>
    </>
  );
}
