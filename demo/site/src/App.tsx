import { useEffect, useMemo } from "react";
import { DataCtx } from "./ui";
import { StaticJsonSource } from "./data/dataSource";
import { Link, ROUTES, useRoute } from "./router";
import { Overview } from "./pages/Overview";
import { HeadToHead } from "./pages/HeadToHead";
import { Replay } from "./pages/Replay";
import { Live } from "./pages/Live";
import { LiveResults } from "./pages/LiveResults";
import { Baselines, Method, Observability, Pareto, Stress, Traces, Training } from "./pages/Results";

const PAGES: Record<string, () => JSX.Element> = { "/": Overview, "/replay": Replay, "/headtohead": HeadToHead, "/pareto": Pareto, "/baselines": Baselines, "/training": Training, "/stress": Stress, "/live": Live, "/liveresults": LiveResults, "/observability": Observability, "/traces": Traces, "/method": Method };

export function App() {
  const route = useRoute();
  // ?data=fixture serves public/fixture-data/ and shows a banner: for checking the pages, never for results.
  const fixture = new URLSearchParams(window.location.search).get("data") === "fixture";
  const ds = useMemo(() => new StaticJsonSource(fixture ? `${import.meta.env.BASE_URL}fixture-` : import.meta.env.BASE_URL), [fixture]);
  const Page = PAGES[route] ?? Overview;
  // a thin reading-progress bar: the page tells you where you are
  useEffect(() => {
    const el = document.documentElement;
    let raf = 0;
    const set = () => { raf = 0; const max = el.scrollHeight - el.clientHeight; el.style.setProperty("--p", String(max > 0 ? Math.min(el.scrollTop / max, 1) : 0)); };
    const on = () => { if (!raf) raf = requestAnimationFrame(set); };
    set();
    window.addEventListener("scroll", on, { passive: true });
    window.addEventListener("resize", on);
    return () => { window.removeEventListener("scroll", on); window.removeEventListener("resize", on); };
  }, [route]);
  return (
    <DataCtx.Provider value={ds}>
      {fixture && <div className="banner" role="alert">FIXTURE DATA: made-up numbers to check the layout. These are NOT results.</div>}
      <div className="scrollbar" aria-hidden="true" />
      <div className="aurora" aria-hidden="true" />
      <header className="top">
        <div className="wrap">
          <Link to="/" className="brand">
            <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><rect x="2" y="2" width="9" height="9" rx="2.5" fill="#56b4e9" /><circle cx="17.5" cy="6.5" r="4.5" fill="none" stroke="#e69f00" strokeWidth="2" strokeDasharray="3 2" /><circle cx="6.5" cy="17.5" r="4.5" fill="none" stroke="#e69f00" strokeWidth="2" strokeDasharray="3 2" /><rect x="13" y="13" width="9" height="9" rx="2.5" fill="#56b4e9" /></svg>
            <span>LLM Router</span>
          </Link>
          <nav className="tabs" aria-label="pages">
            {ROUTES.map((r) => <a key={r.path} href={`#${r.path}`} aria-current={route === r.path ? "page" : undefined}>{r.label}</a>)}
          </nav>
        </div>
      </header>
      <main className="wrap" key={route}><Page /></main>
      <footer><div className="wrap">Independent Double-DQN routing in a simulator calibrated on real llama.cpp servers. Every number on this site is read from a results file and carries its source and config hash. Limits: a calibrated simulation on one machine; real-server runs appear only where they were made (Live and Stress tests pages).</div></footer>
    </DataCtx.Provider>
  );
}
