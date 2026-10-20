// Four small animated cards: why routing LLM requests is hard. Illustrations, not data.
import { Card, useReducedMotion } from "../ui";

const sizes = [4, 9, 5, 14, 6, 11, 4, 8];

export function WhyHard() {
  const reduced = useReducedMotion();
  return (
    <div className="grid g4">
      <Card>
        <div className="label">1 · size is unknown</div>
        <svg viewBox="0 0 200 70" className="chart" aria-hidden="true">
          {sizes.map((r, i) => <circle key={i} className="pulse" style={{ animationDelay: `${i * 0.25}s` }} cx={14 + i * 24} cy={35} r={r} fill="#f7f8f8" fillOpacity={0.8} />)}
        </svg>
        <h3>Request cost is a surprise</h3>
        <p className="muted">The prompt length is known on arrival; the answer length is not. Two requests that look alike can differ by 10x in work.</p>
      </Card>
      <Card>
        <div className="label">2 · traffic is bursty</div>
        <svg viewBox="0 0 200 70" className="chart" aria-hidden="true">
          {[10, 12, 9, 11, 48, 55, 42, 12, 10, 38, 14, 9].map((h, i) => <rect key={i} className="bar" style={{ animationDelay: `${i * 70}ms` }} x={8 + i * 16} y={66 - h} width={10} height={h} rx={2} fill={h > 30 ? "#d55e00" : "#56b4e9"} />)}
        </svg>
        <h3>Bursts overload one server</h3>
        <p className="muted">Arrivals clump. A rule that is fine on average can leave one queue long while another idles.</p>
      </Card>
      <Card>
        <div className="label">3 · caches live on one server</div>
        <svg viewBox="0 0 200 70" className="chart" aria-hidden="true">
          <rect x="20" y="14" width="56" height="42" rx="8" fill="rgba(86,180,233,0.12)" stroke="#56b4e9" strokeWidth="2" />
          <circle cx="132" cy="35" r="22" fill="rgba(230,159,0,0.1)" stroke="#e69f00" strokeWidth="2" strokeDasharray="4 3" />
          <rect className="pulse" x="30" y="24" width="36" height="8" rx="3" fill="#009e73" /><text x="48" y="48" textAnchor="middle" fontSize="9" fill="#d0d6e0">prefix</text>
          <path className="flow-line" d="M100,35 H80" stroke="#7170ff" strokeWidth="2" fill="none" />
        </svg>
        <h3>The follow-up should go home</h3>
        <p className="muted">A chat turn that re-sends its history is fast only on the server that still holds it. Balancing load fights with that.</p>
      </Card>
      <Card>
        <div className="label">4 · outcomes arrive late</div>
        <svg viewBox="0 0 200 70" className="chart" aria-hidden="true">
          <line x1="12" x2="188" y1="35" y2="35" stroke="rgba(255,255,255,0.2)" />
          <circle cx="24" cy="35" r="6" fill="#7170ff" /><text x="24" y="56" textAnchor="middle" fontSize="9" fill="#8a8f98">decide</text>
          <circle cx="176" cy="35" r="6" fill="#009e73" /><text x="176" y="56" textAnchor="middle" fontSize="9" fill="#8a8f98">+10 / −10</text>
          {reduced ? <circle cx="100" cy="35" r="4" fill="#f7f8f8" /> : <circle r="4" fill="#f7f8f8"><animateMotion dur="3s" repeatCount="indefinite" path="M24,35 H176" /></circle>}
        </svg>
        <h3>Credit comes seconds later</h3>
        <p className="muted">Whether a decision was good is known only when the request finishes, after other decisions have happened.</p>
      </Card>
    </div>
  );
}
