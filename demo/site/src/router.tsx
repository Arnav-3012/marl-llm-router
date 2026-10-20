// Minimal hash router (static hosting friendly): routes are "#/name".
import { useEffect, useState, type ReactNode } from "react";

export const ROUTES = [
  { path: "/", label: "Overview" },
  { path: "/replay", label: "Replay" },
  { path: "/headtohead", label: "Head to head" },
  { path: "/pareto", label: "Pareto" },
  { path: "/baselines", label: "Baselines & E1" },
  { path: "/observability", label: "Observability" },
  { path: "/traces", label: "Traces" },
  { path: "/method", label: "Method" },
] as const;

export function useRoute(): string {
  const get = () => (window.location.hash.replace(/^#/, "") || "/");
  const [r, setR] = useState(get);
  useEffect(() => {
    const f = () => { setR(get()); window.scrollTo({ top: 0 }); };
    window.addEventListener("hashchange", f);
    return () => window.removeEventListener("hashchange", f);
  }, []);
  return r;
}

export function Link({ to, children, className }: { to: string; children: ReactNode; className?: string }) {
  return <a className={className} href={`#${to}`}>{children}</a>;
}
