// Shared UI: hooks (reduced motion, in-view, count-up), cards with spotlight, "not run" states, metric display.
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
  const parts: { name: string; s: Source }[] = "files" in (source as object) || "config_hash" in (source as object) || "note" in (source as object)
    ? [{ name: "", s: source as Source }]
    : Object.entries(source as Record<string, Source>).map(([name, s]) => ({ name, s }));
  return (
    <div className="source">
      {parts.map(({ name, s }, i) => s && (
        <div key={i}>
          source{name ? ` (${name})` : ""}: {(s.files ?? []).slice(0, 3).join(", ")}{(s.files?.length ?? 0) > 3 ? ` +${(s.files?.length ?? 0) - 3} more` : ""}
          {s.config_hash ? ` · config ${s.config_hash}` : ""}{s.n_seeds ? ` · ${s.n_seeds} seeds` : ""}{s.note ? ` · ${s.note}` : ""}
        </div>
      ))}
    </div>
  );
}

export function fmt(v: number | null | undefined, digits = 2): string {
  if (v == null || !Number.isFinite(v)) return "n/a";
  return Math.abs(v) >= 1000 ? v.toFixed(0) : v.toFixed(digits);
}

/** mean ± 95% CI, with a count-up on first view. A missing mean is "n/a", never a number. */
export function Num({ m, digits = 2, unit = "", title }: { m: Metric | null | undefined; digits?: number; unit?: string; title?: string }) {
  const reduced = useReducedMotion();
  const [ref, seen] = useInView<HTMLSpanElement>();
  const [shown, setShown] = useState(0);
  const target = m?.mean ?? null;
  useEffect(() => {
    if (target == null) return;
    if (reduced || !seen) return setShown(target);
    let raf = 0;
    const t0 = performance.now();
    const tick = (now: number) => {
      const p = Math.min((now - t0) / 700, 1);
      setShown(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, seen, reduced]);
  if (!m || m.mean == null) return <span className="muted">n/a</span>;
  return (
    <span ref={ref} title={title ?? `n = ${m.n} seeds, mean ± 95% CI`}>
      {fmt(seen ? shown : m.mean, digits)}{unit}
      {m.ci != null && <small className="muted"> ± {fmt(m.ci, digits)}</small>}
    </span>
  );
}

export const POLICY_STYLE: Record<string, { label: string; color: string; marker: "circle" | "square" | "triangle" | "diamond" | "cross"; dash?: string }> = {
  ddqn: { label: "DDQN agents", color: "#e69f00", marker: "circle" },
  ddqn_agents: { label: "Learned agents (DDQN)", color: "#e69f00", marker: "circle" },
  sed_global: { label: "SED (global)", color: "#56b4e9", marker: "square" },
  sed_local_full: { label: "SED local, k=full", color: "#0072b2", marker: "square", dash: "6 4" },
  sed_local_k1: { label: "SED local, k=1", color: "#3b8bd0", marker: "square", dash: "2 3" },
  sed_local_k0: { label: "SED local, k=0", color: "#6b7fa8", marker: "square", dash: "1 4" },
  cache_aware_global: { label: "Cache-aware (global)", color: "#009e73", marker: "triangle" },
  cache_aware_local_full: { label: "Cache-aware local", color: "#33b895", marker: "triangle", dash: "6 4" },
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
