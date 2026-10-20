// Shared UI: hooks (reduced motion, in-view), cards with spotlight, "not run" states, metric display.
import { createContext, useContext, useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import type { DataSource } from "./data/dataSource";
import type { Envelope, Metric, Source } from "./data/types";

export const DataCtx = createContext<DataSource | null>(null);
export const useData = () => {
  const d = useContext(DataCtx);
  if (!d) throw new Error("DataSource missing: pages get data only through the DataSource");
  return d;
};

export function useReducedMotion(): boolean {
  const q = typeof window !== "undefined" ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
  const [r, setR] = useState(q?.matches ?? false);
  useEffect(() => {
    if (!q) return;
    const f = () => setR(q.matches);
    q.addEventListener("change", f);
    return () => q.removeEventListener("change", f);
  }, [q]);
  return r;
}

export function useInView<T extends Element>(once = true): [React.RefObject<T>, boolean] {
  const ref = useRef<T>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") return setSeen(true);
    const io = new IntersectionObserver(([e]) => (e.isIntersecting ? (setSeen(true), once && io.disconnect()) : !once && setSeen(false)), { threshold: 0.15 });
    io.observe(el);
    return () => io.disconnect();
  }, [once]);
  return [ref, seen];
}

export function Reveal({ children, delay = 0, className = "" }: { children: ReactNode; delay?: number; className?: string }) {
  const [ref, seen] = useInView<HTMLDivElement>();
  return (
    <div ref={ref} className={`reveal ${seen ? "in" : ""} ${className}`} style={{ transitionDelay: `${delay}ms` }}>
      {children}
    </div>
  );
}

/** A jargon word with a dotted underline; hover, focus or tap shows a plain-language explanation. */
export function Term({ children, tip }: { children: ReactNode; tip: ReactNode }) {
  return (
    <span className="term" tabIndex={0}>
      {children}
      <span role="tooltip" className="info-pop">{tip}</span>
    </span>
  );
}

/** Page header: small label, the question the page answers, then the short intro passed as children. */
export function PageHead({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <header className="pagehead">
      <div className="eyebrow">{eyebrow}</div>
      <h1>{title}</h1>
      {children}
    </header>
  );
}

/** An "i" button with an explanation that opens on hover, keyboard focus or tap. */
export function Info({ text, label = "More information" }: { text: ReactNode; label?: string }) {
  return (
    <span className="info">
      <button type="button" className="info-btn" aria-label={label}>i</button>
      <span role="tooltip" className="info-pop">{text}</span>
    </span>
  );
}

/** Chart header: title, which direction is better, an info tip on how to read it, and an optional one-line reading. */
export function ChartFrame({ title, better, tip, reading, children }: { title: string; better?: "higher" | "lower"; tip: ReactNode; reading?: ReactNode; children: ReactNode }) {
  return (
    <div className="chartframe">
      <div className="chart-head">
        <h3>{title}</h3>
        {better && <span className={`better ${better}`} title={`${better} is better`}>{better === "higher" ? "↑ higher is better" : "↓ lower is better"}</span>}
        <Info text={tip} label={`How to read: ${title}`} />
      </div>
      {children}
      {reading && <div className="reading" aria-live="polite">{reading}</div>}
    </div>
  );
}

export function Card({ children, className = "", style }: { children: ReactNode; className?: string; style?: CSSProperties }) {
  const onMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    e.currentTarget.style.setProperty("--mx", `${e.clientX - r.left}px`);
    e.currentTarget.style.setProperty("--my", `${e.clientY - r.top}px`);
  };
  return <div className={`card ${className}`} style={style} onMouseMove={onMove}>{children}</div>;
}

export function useLoad<T>(fn: () => Promise<Envelope<T>>, deps: unknown[] = []) {
  const [state, setState] = useState<{ env?: Envelope<T>; error?: string }>({});
  useEffect(() => {
    let live = true;
    setState({});
    fn().then((env) => live && setState({ env })).catch((e) => live && setState({ error: String(e.message ?? e) }));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}

export function NotRun({ reason, what }: { reason?: string; what: string }) {
  return (
    <div className="notrun" role="status">
      <b>{what}: not run</b>
      {reason ?? "No result file for this yet."} Nothing is shown here because nothing was measured.
    </div>
  );
}

export function Loaded<T>({ state, what, children }: { state: { env?: Envelope<T>; error?: string }; what: string; children: (data: T, env: Envelope<T>) => ReactNode }) {
  if (state.error) return <div className="notrun" role="alert"><b>{what}: could not load</b>{state.error}</div>;
  if (!state.env) return <div className="notrun" aria-busy="true"><b>{what}</b>Loading…</div>;
  if (state.env.status === "not_run" || state.env.data == null) return <NotRun what={what} reason={state.env.reason} />;
  return <>{children(state.env.data, state.env)}</>;
}

export function SourceNote({ source }: { source: Source | Record<string, Source> | undefined }) {
  if (!source) return null;
  const parts: Source[] = "files" in (source as object) || "config_hash" in (source as object) || "note" in (source as object)
    ? [source as Source]
    : Object.values(source as Record<string, Source>);
  const live = parts.filter(Boolean) as NonNullable<Source>[];
  if (!live.length) return null;
  const folders = [...new Set(live.flatMap((s) => (s.files ?? []).map((f) => /^results\/([^/]+)\//.exec(f)?.[1] ?? f.split("/")[0])))];
  const seeds = [...new Set(live.map((s) => s.n_seeds).filter(Boolean))];
  const notes = [...new Set(live.map((s) => s.note).filter(Boolean))];
  return (
    <div className="source">
      <span>Data: {folders.length ? folders.join(", ") : "results files"}{seeds.length ? ` · ${seeds.join("/")} seeds` : ""}{notes.length ? ` · ${notes.join(", ")}` : ""}</span>
      <details className="source-more">
        <summary>files and config hashes</summary>
        {live.map((s, i) => (
          <div key={i}>{s.config_hash ? `config ${s.config_hash}: ` : ""}{(s.files ?? []).slice(0, 2).join(", ")}{(s.files?.length ?? 0) > 2 ? ` and ${(s.files?.length ?? 0) - 2} more` : ""}</div>
        ))}
      </details>
    </div>
  );
}

export function fmt(v: number | null | undefined, digits = 2): string {
  if (v == null || !Number.isFinite(v)) return "n/a";
  return Math.abs(v) >= 1000 ? v.toFixed(0) : v.toFixed(digits);
}

/** mean ± 95% CI. A missing mean is "n/a", never a number. Static on purpose: a number that counts up
 * from zero shows a wrong value for a moment (and in a screenshot), which a results page must never do. */
export function Num({ m, digits = 2, unit = "", title }: { m: Metric | null | undefined; digits?: number; unit?: string; title?: string }) {
  if (!m || m.mean == null) return <span className="muted">n/a</span>;
  return (
    <span title={title ?? `n = ${m.n} seeds, mean ± 95% CI`}>
      {fmt(m.mean, digits)}{unit}
      {m.ci != null && <small className="muted"> ± {fmt(m.ci, digits)}</small>}
    </span>
  );
}

export const POLICY_STYLE: Record<string, { label: string; color: string; marker: "circle" | "square" | "triangle" | "diamond" | "cross"; dash?: string }> = {
  ddqn: { label: "DDQN agents (3 actions)", color: "#e69f00", marker: "circle" },
  ddqn_agents: { label: "Learned agents (DDQN)", color: "#e69f00", marker: "circle" },
  sed_global: { label: "SED (global)", color: "#56b4e9", marker: "square" },
  sed_local_full: { label: "SED local, k=full", color: "#0072b2", marker: "square", dash: "6 4" },
  sed_local_k1: { label: "SED local, k=1", color: "#3b8bd0", marker: "square", dash: "2 3" },
  sed_local_k0: { label: "SED local, k=0", color: "#6b7fa8", marker: "square", dash: "1 4" },
  cache_aware_global: { label: "Cache-aware (global)", color: "#009e73", marker: "triangle" },
  cache_aware_local_full: { label: "Cache-aware local", color: "#33b895", marker: "triangle", dash: "6 4" },
  route_to_fast: { label: "Hand-written rule: route to fast", color: "#9aa4b5", marker: "square", dash: "8 3" },
  route_to_fast_shed_tau: { label: "Rewritten rule (tuned for this layout)", color: "#e8ecf3", marker: "diamond", dash: "2 3" },
  route_to_fast_shed: { label: "Hand-written rule: route to fast + shed", color: "#c3cad6", marker: "diamond", dash: "8 3" },
  ddqn_reject_ft: { label: "DDQN + Reject (fine-tuned)", color: "#d55e00", marker: "triangle" },
  ddqn_reject_mix: { label: "DDQN agents + Reject", color: "#f28e4b", marker: "circle" },
  ddqn_reject_scratch: { label: "DDQN + Reject (conversation traffic only)", color: "#b86b3a", marker: "diamond" },
  ddqn_ft_ctrl: { label: "DDQN fine-tuned, no Reject", color: "#b57700", marker: "square", dash: "3 3" },
  random: { label: "Random", color: "#cc79a7", marker: "diamond", dash: "1 4" },
  round_robin: { label: "Round-robin", color: "#b5668f", marker: "diamond", dash: "3 3" },
  jsq_global: { label: "JSQ (global)", color: "#f0e442", marker: "cross" },
  po2_global: { label: "Po2 (global)", color: "#cfc43a", marker: "cross", dash: "3 3" },
};
export const styleOf = (id: string) => POLICY_STYLE[id] ?? { label: id, color: "#8a8f98", marker: "circle" as const };

export function Marker({ kind, x, y, r = 5, color }: { kind: string; x: number; y: number; r?: number; color: string }) {
  const common = { fill: color, stroke: "#08090a", strokeWidth: 1 };
  if (kind === "square") return <rect {...common} x={x - r} y={y - r} width={2 * r} height={2 * r} rx={1.5} />;
  if (kind === "triangle") return <path {...common} d={`M${x},${y - r - 1} L${x + r + 1},${y + r} L${x - r - 1},${y + r} Z`} />;
  if (kind === "diamond") return <path {...common} d={`M${x},${y - r - 1} L${x + r + 1},${y} L${x},${y + r + 1} L${x - r - 1},${y} Z`} />;
  if (kind === "cross") return <path d={`M${x - r},${y - r} L${x + r},${y + r} M${x + r},${y - r} L${x - r},${y + r}`} stroke={color} strokeWidth={2.5} />;
  return <circle {...common} cx={x} cy={y} r={r} />;
}

export function Legend({ ids }: { ids: string[] }) {
  return (
    <div className="legend" aria-label="legend">
      {ids.map((id) => {
        const s = styleOf(id);
        return (
          <span key={id}>
            <svg width="22" height="12" aria-hidden="true">
              <line x1="0" y1="6" x2="22" y2="6" stroke={s.color} strokeWidth="2" strokeDasharray={s.dash} />
              <Marker kind={s.marker} x={11} y={6} r={4} color={s.color} />
            </svg>
            {s.label}
          </span>
        );
      })}
    </div>
  );
}
