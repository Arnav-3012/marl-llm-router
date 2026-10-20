// TypeScript mirror of the JSON written by scripts/export_dashboard_data.py (schema_version 1).
// parseEnvelope throws on a mismatch so a stale export fails loudly instead of showing wrong numbers.

export const SCHEMA_VERSION = 1;

export type Metric = { mean: number | null; ci: number | null; n: number };
export type MetricRow = Record<string, Metric>;
export type Source = {
  files?: string[];
  config_hash?: string;
  n_seeds?: number;
  note?: string;
  [k: string]: unknown;
} | null;

export type Envelope<T> = {
  schema_version: number;
  status: "ok" | "not_run";
  data: T | null;
  source: Source | Record<string, Source>;
  reason?: string;
};

export type PolicyTable = Record<string, Record<string, MetricRow>>; // policy -> rho -> metrics

export type BaselinesData = {
  metrics: string[];
  baselines: { policies: PolicyTable } | null;
  learned: { label: string; rows: Record<string, MetricRow> } | null;
  learned_extra?: { id: string; label: string; rows: Record<string, MetricRow> }[];
};

export type ParetoPoint = {
  label: string;
  kind: "learned" | "baseline";
  lambda: number | null;
  cost: Metric;
  latency: Metric;
  goodput: Metric;
  on_frontier: boolean;
};
export type ParetoData = { rho: number; x: string; y: string; points: ParetoPoint[] };

export type ObservabilityData = {
  learned: { label: string; rows: Record<string, MetricRow> }[];
  references: Record<string, Record<string, MetricRow> | null>;
};

export type ActionShares = { n: number; accept?: number; forward?: number; defer?: number; reject?: number };
export type ClassBehaviour = { all: ActionShares; by_wait: Record<string, ActionShares>; by_prompt: Record<string, ActionShares> };
export type BehaviourData = {
  agents_experiment: string;
  seeds: number[];
  split: string;
  rhos: Record<string, { fast: ClassBehaviour; slow: ClassBehaviour }>;
  units: { wait_s: number; prompt_tokens: number };
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type StressData = Record<string, any>;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type LooseData = Record<string, any>;

export type TrainingData = {
  columns: string[];
  n_seeds: number;
  episodes: Record<string, number | null>[];
  seeds?: { seed: number; episodes: Record<string, number | null>[] }[];
};

export type OverviewData = {
  q1_goodput: Record<string, unknown> | null;
  q2_pareto_available: boolean;
  real_server_runs?: number;
  q2_frontier?: { learned: string[]; on_frontier: string[] } | null;
  q4_reject?: { rhos: Record<string, Record<string, { goodput: Metric; drop_rate: Metric } | null>> } | null;
  q3_observability_available: boolean;
  experiments_finished_seeds: Record<string, number>;
  exported_at: string;
  not_done: string[];
};

export type TracesData = Record<string, Record<string, unknown>>;

export type MethodData = {
  adrs: { id: string; title: string; status: string }[];
  profiling_fit: Record<string, unknown> | null;
  profiling_machine: Record<string, unknown> | null;
  lambda_sat: Record<string, unknown> | null;
  calibration: Record<string, unknown> | null;
};

export type Frame = {
  tick: number;
  t: number;
  queue: number[] | null;
  active: number[] | null;
  kv: number[] | null;
  arrivals: { req: number; entry: number; p: number | null; o: number | null }[];
  acts: { agent: number; req: number; action: number }[];
  forwards: { req: number; src: number; dst: number }[];
  resolves: { req: number; ok: boolean; status: string; server: number | null; ttft?: number | null; cost?: number | null }[];
};
export type ReplayData = { policy: string; rho: number; dt: number; layout?: string[]; frames: Frame[] };

// ---- head-to-head (Sh.H2): every policy on the identical held-out slice ---------------------------
export type H2HPolicy = { id: string; label: string; kind: "learned" | "baseline"; mode: "agents" | "global" };
export type PairedDiff = { metric: string; n: number; seeds: number[]; mean_diff: number; ci95: [number, number]; excludes_zero: boolean };
export type H2HRho = {
  slice_id: string;
  seeds: number[];
  config_hash: string;
  summary: Record<string, MetricRow>; // policy -> metric -> mean/ci over seeds
  paired_diff: Record<string, Record<string, PairedDiff> | null>; // baseline -> metric -> learned minus baseline
  replay: Record<string, string | null>;
};
export type HeadToHeadData = {
  dt: number;
  layout: string[] | null;
  learned: string;
  event_seed: number;
  slice_split: string;
  policies: H2HPolicy[];
  rhos: Record<string, H2HRho>;
};
export type H2HReplay = {
  policy: string;
  rho: number;
  dt: number;
  layout: string[] | null;
  mode: "agents" | "global";
  seed: number;
  events: { cap: number; original: number; kept: number; truncated: boolean; seed: number } | null;
  frames: Frame[];
};

export function parseEnvelope<T>(raw: unknown, name: string): Envelope<T> {
  const e = raw as Envelope<T>;
  if (!e || typeof e !== "object" || e.schema_version !== SCHEMA_VERSION || (e.status !== "ok" && e.status !== "not_run")) {
    throw new Error(`${name}: expected schema_version ${SCHEMA_VERSION} envelope, got ${JSON.stringify(raw)?.slice(0, 120)}`);
  }
  if (e.status === "ok" && e.data == null) throw new Error(`${name}: status ok but data is null`);
  return e;
}
