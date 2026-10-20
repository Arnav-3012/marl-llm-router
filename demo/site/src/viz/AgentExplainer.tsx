// "What can an agent do?" explained: pick one of the four actions, watch one request take that path in the 3D cluster, and read
// what it means, when it helps and what it costs. The percentages are the final agents' measured action shares on held-out
// traffic (behaviour.json); the cluster picture itself is an illustration.
import { useState } from "react";
import { Info, useData, useLoad } from "../ui";
import { IsoCluster, SCENARIO, type ActionKey, type Mix } from "./IsoCluster";

const ACTIONS: { key: ActionKey; name: string; short: string; means: string; when: string; cost: string }[] = [
  { key: "accept", name: "Accept", short: "Serve it here", means: "The request joins the waiting line of the agent's own server and will be answered there.",
    when: "This server's line is short and the request fits its memory, so it can still answer in time.",
    cost: "If the line turns out too long the answer is late. +10 reward if both targets are met, −10 if not." },
  { key: "forward", name: "Forward", short: "Pass it to a neighbour", means: "The request moves to the visible neighbour that would finish it soonest. It can be passed on at most twice.",
    when: "This server is busy, or slow for this request, and another server would finish sooner. A slow server usually passes work to a fast one.",
    cost: "Each pass costs half a reward point, so agents do not bounce requests around, and the request loses a little time." },
  { key: "defer", name: "Defer", short: "Wait a moment", means: "The request goes to the back of the agent's own line and the agent decides again a moment later (0.1 s). At most twice per request.",
    when: "There is still time before the deadline and the situation may change, for example a neighbour frees up.",
    cost: "Half a reward point each time, plus the time spent waiting. Agents use it a lot without it helping goodput, which is why it is shown." },
  { key: "reject", name: "Reject", short: "Refuse it", means: "The request is dropped on purpose and the user is told the service is too busy. Only the final agents have this action.",
    when: "The request can no longer meet its deadline, so serving it late would only block requests that can still make it. This is what keeps the service working in overload.",
    cost: "−5 reward, which is better than the −10 for an answer that arrives too late. The refused share is always shown next to the results." },
];

const SEES = [
  ["Own wait", "How long a new request would wait on this server, in seconds. Ten seconds or more counts as full."],
  ["Memory use", "How full the server's key-value cache (its working memory for open conversations) is."],
  ["Request size", "How long the prompt is. Long prompts take much longer to read."],
  ["Time left", "How much of the 5-second first-word deadline is still unspent after the wait and the reading time."],
  ["Times passed on", "How often this request was already forwarded."],
  ["Neighbours' wait", "The average wait of the servers it can see. Zero when it can see none."],
  ["Cached part", "The share of the prompt this server already holds from an earlier turn of the conversation."],
];

export function useMix(): { fast?: Mix; slow?: Mix } {
  const ds = useData();
  const b = useLoad(() => ds.getBehaviour(), []);
  const d = b.env?.data;
  const at = d?.rhos?.["0.8"];
  const fix = (s?: { accept?: number; forward?: number; defer?: number; reject?: number }): Mix | undefined =>
    s ? { accept: s.accept ?? 0, forward: s.forward ?? 0, defer: s.defer ?? 0, reject: s.reject ?? 0 } : undefined;
  return { fast: fix(at?.fast.all), slow: fix(at?.slow.all) };
}

export function AgentExplainer() {
  const [action, setAction] = useState<ActionKey>("accept");
  const [play, setPlay] = useState(0);
  const mix = useMix();
  const cur = ACTIONS.find((a) => a.key === action)!;
  const pct = (m?: Mix) => (m ? (m[action] > 0 && m[action] < 0.01 ? "under 1%" : `${Math.round(m[action] * 100)}%`) : "n/a");
  return (
    <div className="explainer">
      <div className="ex-stage">
        <IsoCluster mode="explain" action={action} playKey={play} scrollLinked={false} height={340} mixFast={mix.fast} mixSlow={mix.slow} />
        <div className="ex-caption"><b>{cur.name}:</b> {SCENARIO[action].note}
          <button type="button" className="btn ex-replay" onClick={() => setPlay((n) => n + 1)}>Replay</button>
        </div>
      </div>
      <div className="ex-actions" role="group" aria-label="the four actions">
        {ACTIONS.map((a) => (
          <button key={a.key} type="button" className={`ex-card ${a.key}`} aria-pressed={a.key === action} onClick={() => setAction(a.key)}>
            <span className="ex-name">{a.name}<small>{a.short}</small></span>
            {a.key === action && (
              <span className="ex-body">
                <span><b>What it means.</b> {a.means}</span>
                <span><b>When it helps.</b> {a.when}</span>
                <span><b>What it costs.</b> {a.cost}</span>
                <span className="ex-share">Chosen by agents on fast servers {pct(mix.fast)} of the time, on slow servers {pct(mix.slow)} <Info text="Measured: share of all decisions of the final agents on held-out traffic at load 0.8, three seeds. Slow-server agents almost never accept, because the fast servers are about eight times quicker." /></span>
              </span>
            )}
          </button>
        ))}
      </div>
      <div className="ex-sees">
        <h3>What an agent sees before it chooses</h3>
        <div className="ex-chips">{SEES.map(([k, v]) => <span key={k} className="ex-chip" tabIndex={0}><b>{k}</b><i>{v}</i></span>)}</div>
        <p className="muted" style={{ marginTop: 10 }}>Seven numbers between 0 and 1, nothing else: no server names, no labels saying which servers are fast. Agents learn the difference from how requests turn out.</p>
      </div>
    </div>
  );
}
