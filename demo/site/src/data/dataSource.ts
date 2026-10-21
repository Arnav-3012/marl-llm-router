// The ONLY way pages get data. Swap StaticJsonSource for a live source later without touching a page.
import {
  parseEnvelope,
  type BaselinesData, type BehaviourData, type StressData, type LooseData, type Envelope, type Frame, type H2HReplay, type HeadToHeadData, type MethodData, type ObservabilityData,
  type OverviewData, type ParetoData, type ReplayData, type TracesData, type TrainingData,
} from "./types";

export interface DataSource {
  getOverview(): Promise<Envelope<OverviewData>>;
  getBaselines(): Promise<Envelope<BaselinesData>>;
  getPareto(): Promise<Envelope<ParetoData>>;
  getObservability(): Promise<Envelope<ObservabilityData>>;
  getBehaviour(): Promise<Envelope<BehaviourData>>;
  getStress(): Promise<Envelope<StressData>>;
  getLayout(): Promise<Envelope<LooseData>>;
  getLiveRuns(): Promise<Envelope<LooseData>>;
  getRobust(): Promise<Envelope<LooseData>>;
  getTraining(): Promise<Envelope<TrainingData>>;
  getTraces(): Promise<Envelope<TracesData>>;
  getMethod(): Promise<Envelope<MethodData>>;
  getHeadToHead(): Promise<Envelope<HeadToHeadData>>;
  /** Recorded episode (seed = event_seed) of one policy at one load on the identical slice. */
  getH2HReplay(policy: string, rho: string): Promise<Envelope<H2HReplay>>;
  /** Frames of a recorded episode, delivered in order; meta (policy, rho, dt) comes from getReplayMeta. */
  getReplayStream(policy: string, rho: string): AsyncGenerator<Frame>;
  getReplayMeta(policy: string, rho: string): Promise<Envelope<ReplayData>>;
}

export class StaticJsonSource implements DataSource {
  constructor(private base: string = import.meta.env.BASE_URL) {}

  private async load<T>(file: string): Promise<Envelope<T>> {
    const res = await fetch(`${this.base}data/${file}`);
    if (!res.ok) throw new Error(`${file}: HTTP ${res.status}`);
    return parseEnvelope<T>(await res.json(), file);
  }

  getOverview = () => this.load<OverviewData>("overview.json");
  getBaselines = () => this.load<BaselinesData>("baselines.json");
  getPareto = () => this.load<ParetoData>("pareto.json");
  getObservability = () => this.load<ObservabilityData>("observability.json");
  getBehaviour = () => this.load<BehaviourData>("behaviour.json");
  getStress = () => this.load<StressData>("stress.json");
  getLayout = () => this.load<LooseData>("layout.json");
  getLiveRuns = () => this.load<LooseData>("live.json");
  getRobust = () => this.load<LooseData>("robust.json");
  getTraining = () => this.load<TrainingData>("training.json");
  getTraces = () => this.load<TracesData>("traces.json");
  getMethod = () => this.load<MethodData>("method.json");
  getHeadToHead = () => this.load<HeadToHeadData>("headtohead.json");
  getH2HReplay = (policy: string, rho: string) => this.load<H2HReplay>(`h2h_replay_${policy}_${rho}.json`);
  getReplayMeta = (policy: string, rho: string) => this.load<ReplayData>(`replay_${policy}_${rho}.json`);

  async *getReplayStream(policy: string, rho: string): AsyncGenerator<Frame> {
    const env = await this.getReplayMeta(policy, rho);
    for (const f of env.data?.frames ?? []) yield f;
  }
}
