// Animated project pipeline: Profile -> Calibrate -> Train -> Deploy -> Compare, with data packets flowing along the
// links. Node status comes from the data (not hard-coded): a stage with no result shows "not run".
import { useReducedMotion } from "../ui";

export type StageStatus = "done" | "partial" | "not_run";
export type Stage = { key: string; title: string; note: string; status: StageStatus };

const COLOR: Record<StageStatus, string> = { done: "#009e73", partial: "#e69f00", not_run: "#8a8f98" };
const LABEL: Record<StageStatus, string> = { done: "done", partial: "partly done", not_run: "not run" };

export function Pipeline({ stages }: { stages: Stage[] }) {
  const reduced = useReducedMotion();
  const W = 1000, H = 170, n = stages.length, gap = W / n;
  const cx = (i: number) => gap * i + gap / 2;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label={`Pipeline: ${stages.map((s) => `${s.title} (${LABEL[s.status]})`).join(", then ")}`}>
      <defs>
        <linearGradient id="pl-link" x1="0" x2="1"><stop offset="0" stopColor="#7170ff" stopOpacity="0.2" /><stop offset="1" stopColor="#7170ff" stopOpacity="0.9" /></linearGradient>
        <pattern id="pl-hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="8" height="8" fill="#0f1011" /><line x1="0" y1="0" x2="0" y2="8" stroke="rgba(255,255,255,0.14)" strokeWidth="3" /></pattern>
      </defs>
      {stages.slice(0, -1).map((s, i) => {
        const x1 = cx(i) + 62, x2 = cx(i + 1) - 62, live = s.status !== "not_run" && stages[i + 1].status !== "not_run";
        return (
          <g key={`l${i}`}>
            <line x1={x1} y1={70} x2={x2} y2={70} stroke="url(#pl-link)" strokeWidth={2} className={live ? "flow-line" : undefined} strokeDasharray={live ? undefined : "2 6"} opacity={live ? 1 : 0.5} />
            {!reduced && live && (
              <circle r={4} fill="#f7f8f8">
                <animateMotion dur={`${2.4 + (i % 2) * 0.5}s`} repeatCount="indefinite" path={`M${x1},70 L${x2},70`} begin={`${i * 0.4}s`} />
              </circle>
            )}
            <path d={`M${x2 - 6},64 L${x2 + 2},70 L${x2 - 6},76`} fill="none" stroke="#7170ff" strokeWidth={2} opacity={live ? 1 : 0.4} />
          </g>
        );
      })}
      {stages.map((s, i) => (
        <g key={s.key}>
          <rect x={cx(i) - 60} y={30} width={120} height={80} rx={12} fill={s.status === "not_run" ? "url(#pl-hatch)" : "rgba(255,255,255,0.04)"} stroke={COLOR[s.status]} strokeWidth={1.5} strokeDasharray={s.status === "not_run" ? "5 4" : undefined} />
          {s.status === "done" && <circle className="pulse" cx={cx(i) + 48} cy={42} r={4} fill={COLOR.done} />}
          <text x={cx(i)} y={64} textAnchor="middle" fill="#f7f8f8" fontSize="15" fontWeight="590">{s.title}</text>
          <text x={cx(i)} y={84} textAnchor="middle" fill={COLOR[s.status]} fontSize="11.5" fontWeight="510">{LABEL[s.status]}</text>
          <text x={cx(i)} y={134} textAnchor="middle" fill="#8a8f98" fontSize="11">{s.note}</text>
        </g>
      ))}
    </svg>
  );
}
