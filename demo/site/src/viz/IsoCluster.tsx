// Isometric 3D picture of the cluster: four servers (two tall and fast, two low and slow) with a router agent floating above
// each, requests arriving from the left, and the four things an agent can do shown as paths. Drawn on a canvas with plain
// projection maths (no 3D library). "hero": an illustration whose action mix is the trained agents' measured mix; the view
// tilts with the page scroll and the offered load rises as you scroll. "explain": one scripted request for the chosen action.
// Reduced motion: one static frame. It is an illustration of the idea, not measured data, and says so.
import { useEffect, useRef } from "react";
import { useReducedMotion } from "../ui";

type V3 = [number, number, number];
export type Mix = { accept: number; forward: number; defer: number; reject: number };
export type ActionKey = "accept" | "forward" | "defer" | "reject";

const FAST = [0, 2];
const SX = 2.25; // spacing of the servers along x
const H_FAST = 1.9, H_SLOW = 0.85, BOX = 1.45;
const COL = {
  fast: { top: "#7fd0fa", left: "#2f86bb", right: "#1f5d86", glow: "86,180,233" },
  slow: { top: "#f4c25a", left: "#b9801a", right: "#80570e", glow: "230,159,0" },
  agent: "#8a89ff", ok: "#2fd1a0", bad: "#ff7a45", ink: "#e8ecf3", dim: "#8a8f98",
};
const SRC: V3 = [-2.6, 0, 2.2];
const BIN: V3 = [3 * SX + 2.6, 0.2, 0.5];
const serverPos = (i: number): V3 => [i * SX, 0, 0];
const agentPos = (i: number): V3 => [i * SX, 0, (FAST.includes(i) ? H_FAST : H_SLOW) + 1.35];
const topPos = (i: number, stack = 0): V3 => [i * SX, 0, (FAST.includes(i) ? H_FAST : H_SLOW) + 0.12 + stack * 0.16];

type Particle = {
  id: number; pos: V3; from: V3; to: V3; t0: number; dur: number; phase: string; agent: number;
  hops: number; defers: number; color: string; arc: number; server: number; leaveAt: number; ok: boolean; alpha: number; loop: boolean;
};

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const ease = (t: number) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);

export const SCENARIO: Record<ActionKey, { entry: number; note: string }> = {
  accept: { entry: 0, note: "A0 keeps the request: it goes onto its own server." },
  forward: { entry: 1, note: "A1 sits on a slow server, so it passes the request to a fast neighbour." },
  defer: { entry: 0, note: "A0 holds the request back for a moment and decides again." },
  reject: { entry: 0, note: "A0 refuses the request: it cannot be served in time." },
};

export function IsoCluster({ mode, mixFast, mixSlow, action, playKey = 0, scrollLinked = true, height = 420 }: {
  mode: "hero" | "explain"; mixFast?: Mix; mixSlow?: Mix; action?: ActionKey; playKey?: number; scrollLinked?: boolean; height?: number;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const reduced = useReducedMotion();
  const props = useRef({ mixFast, mixSlow, action });
  props.current = { mixFast, mixSlow, action };

  useEffect(() => {
    const canvas = ref.current!;
    const ctx = canvas.getContext("2d")!;
    let W = 0, H = 0, raf = 0, visible = true, last = performance.now(), nowT = 0, spawnAcc = 0, uid = 0, yaw = 0.5, mouse = 0;
    const ps: Particle[] = [];
    const free = [0, 0, 0, 0];
    const queued = [0, 0, 0, 0];
    const bursts: { pos: V3; t: number; ok: boolean }[] = [];
    let pulse: { agent: number; t: number } | null = null;
    const rng = Math.random;
    const mixOf = (i: number): Mix => (FAST.includes(i) ? props.current.mixFast : props.current.mixSlow) ?? (FAST.includes(i) ? { accept: 0.59, forward: 0.06, defer: 0.31, reject: 0.03 } : { accept: 0.0, forward: 0.6, defer: 0.38, reject: 0.02 });

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = canvas.clientWidth; H = canvas.clientHeight;
      canvas.width = W * dpr; canvas.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    // projection: yaw about the vertical axis, fixed pitch
    const pitch = 0.56;
    const project = (p: V3): [number, number, number] => {
      const cT = Math.cos(yaw), sT = Math.sin(yaw), sP = Math.sin(pitch), cP = Math.cos(pitch);
      const S = Math.min(W / 12.6, H / 5.0);
      const depth = p[0] * sT + p[1] * cT;
      return [W * 0.5 + (p[0] - 3.4) * cT * S - p[1] * sT * S, H * 0.6 + (depth * sP - p[2] * cP) * S - 1.5 * S, depth];
    };

    const poly = (pts: V3[], fill: string, stroke?: string) => {
      ctx.beginPath();
      pts.forEach((p, k) => { const [x, y] = project(p); k ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
      ctx.closePath(); ctx.fillStyle = fill; ctx.fill();
      if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = 1; ctx.stroke(); }
    };

    const box = (c: V3, w: number, d: number, h: number, col: { top: string; left: string; right: string }, busy: number) => {
      const [x, y, z] = c, x0 = x - w / 2, x1 = x + w / 2, y0 = y - d / 2, y1 = y + d / 2;
      const sT = Math.sin(yaw), cT = Math.cos(yaw);
      const faces: { n: [number, number]; pts: V3[]; fill: string }[] = [
        { n: [1, 0], pts: [[x1, y0, z], [x1, y1, z], [x1, y1, z + h], [x1, y0, z + h]], fill: col.right },
        { n: [-1, 0], pts: [[x0, y0, z], [x0, y1, z], [x0, y1, z + h], [x0, y0, z + h]], fill: col.left },
        { n: [0, 1], pts: [[x0, y1, z], [x1, y1, z], [x1, y1, z + h], [x0, y1, z + h]], fill: col.left },
        { n: [0, -1], pts: [[x0, y0, z], [x1, y0, z], [x1, y0, z + h], [x0, y0, z + h]], fill: col.right },
      ];
      faces.filter((f) => f.n[0] * sT + f.n[1] * cT > 0).forEach((f) => poly(f.pts, f.fill, "rgba(255,255,255,0.07)"));
      poly([[x0, y0, z + h], [x1, y0, z + h], [x1, y1, z + h], [x0, y1, z + h]], col.top, "rgba(255,255,255,0.18)");
      if (busy > 0) { // glow on the roof grows with the work waiting
        const [gx, gy] = project([x, y, z + h]);
        const g = ctx.createRadialGradient(gx, gy, 2, gx, gy, 46 + busy * 6);
        const rgb = col.top === COL.fast.top ? COL.fast.glow : COL.slow.glow;
        g.addColorStop(0, `rgba(${rgb},${Math.min(0.55, 0.18 + busy * 0.07)})`); g.addColorStop(1, `rgba(${rgb},0)`);
        ctx.fillStyle = g; ctx.fillRect(gx - 80, gy - 80, 160, 160);
      }
    };

    const floor = () => {
      ctx.lineWidth = 1;
      for (let i = -3; i <= 10; i++) {
        ctx.strokeStyle = "rgba(160,170,255,0.07)";
        const a = project([i, -1.8, 0]), b = project([i, 1.8, 0]);
        ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke();
      }
      for (let j = -1; j <= 1; j++) {
        const a = project([-3, j * 1.2, 0]), b = project([10, j * 1.2, 0]);
        ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke();
      }
    };

    const label = (text: string, p: V3, color: string, size = 11, dy = 0) => {
      const [x, y] = project(p);
      ctx.font = `510 ${size}px Inter, system-ui, sans-serif`; ctx.textAlign = "center"; ctx.fillStyle = color; ctx.fillText(text, x, y + dy);
    };

    const agentDraw = (i: number) => {
      const c = agentPos(i), r = 0.46;
      const pts: V3[] = Array.from({ length: 6 }, (_, k) => [c[0] + Math.cos((k / 6) * 6.283) * r, c[1] + Math.sin((k / 6) * 6.283) * r, c[2]] as V3);
      const [gx, gy] = project(c);
      const pulsing = pulse && pulse.agent === i ? Math.max(0, 1 - (nowT - pulse.t) / 0.5) : 0;
      const g = ctx.createRadialGradient(gx, gy, 2, gx, gy, 36);
      g.addColorStop(0, `rgba(138,137,255,${0.25 + pulsing * 0.5})`); g.addColorStop(1, "rgba(138,137,255,0)");
      ctx.fillStyle = g; ctx.fillRect(gx - 50, gy - 50, 100, 100);
      poly(pts, "rgba(138,137,255,0.28)", COL.agent);
      const sp = project([c[0], c[1], c[2] - 0.5]);
      ctx.strokeStyle = "rgba(138,137,255,0.35)"; ctx.setLineDash([3, 4]); ctx.beginPath(); ctx.moveTo(gx, gy + 6); ctx.lineTo(sp[0], sp[1] + 22); ctx.stroke(); ctx.setLineDash([]);
      label(`A${i}`, c, COL.ink, 12, 4);
    };

    const spawn = (entry?: number) => {
      const agent = entry ?? Math.floor(rng() * 4);
      ps.push({ id: uid++, pos: [...SRC], from: [...SRC], to: agentPos(agent), t0: nowT, dur: 0.9, phase: "toAgent", agent, hops: 0, defers: 0,
        color: "#d9dcff", arc: 0.5, server: -1, leaveAt: 0, ok: true, alpha: 1, loop: false });
    };

    const go = (p: Particle, to: V3, dur: number, phase: string, arc = 0.6) => {
      p.from = [...p.pos]; p.to = to; p.t0 = nowT; p.dur = dur; p.phase = phase; p.arc = arc;
    };

    const choose = (p: Particle): ActionKey => {
      if (mode === "explain") return props.current.action ?? "accept";
      const m = mixOf(p.agent);
      let a: ActionKey[] = ["accept", "forward", "defer", "reject"];
      const w = [m.accept, p.hops >= 2 ? 0 : m.forward, p.defers >= 2 ? 0 : m.defer, m.reject];
      const tot = w.reduce((s, v) => s + v, 0) || 1;
      let r = rng() * tot;
      for (let k = 0; k < 4; k++) { r -= w[k]; if (r <= 0) return a[k]; }
      a = ["accept"]; return a[0];
    };

    const decide = (p: Particle) => {
      pulse = { agent: p.agent, t: nowT };
      const act = choose(p);
      if (act === "accept") { p.server = p.agent; go(p, topPos(p.agent, queued[p.agent]), 0.55, "toServer", 0.3); }
      else if (act === "forward") {
        const fastNb = [0, 2].filter((k) => k !== p.agent);
        const cand = FAST.includes(p.agent) ? [0, 1, 2, 3].filter((k) => k !== p.agent) : fastNb;
        const tgt = cand[Math.floor(rng() * cand.length)];
        p.hops++; p.agent = tgt; go(p, agentPos(tgt), 0.8, "toAgent", 1.1);
      } else if (act === "defer") { p.defers++; go(p, agentPos(p.agent), 0.7, "defer", 0); p.loop = true; }
      else { go(p, BIN, 0.9, "toBin", 1.0); p.color = COL.bad; }
    };

    const step = (dt: number) => {
      nowT += dt;
      const hero = mode === "hero";
      if (hero) {
        const load = scrollLinked ? Math.min(window.scrollY / 700, 1) : 0.3;
        spawnAcc += dt;
        const gap = lerp(1.15, 0.38, load);
        if (spawnAcc > gap) { spawnAcc = 0; spawn(); }
      }
      for (let k = ps.length - 1; k >= 0; k--) {
        const p = ps[k];
        const t = Math.min((nowT - p.t0) / p.dur, 1), e = ease(t);
        if (p.phase === "defer") {
          const a = e * 6.283, c = agentPos(p.agent);
          p.pos = [c[0] + Math.sin(a) * 0.5, c[1] + 0.0, c[2] + 0.55 - Math.cos(a) * 0.5];
        } else if (p.phase === "serving") {
          const c = topPos(p.server, 0);
          p.pos = [c[0], c[1], c[2] + 0.1];
        } else {
          p.pos = [lerp(p.from[0], p.to[0], e), lerp(p.from[1], p.to[1], e), lerp(p.from[2], p.to[2], e) + Math.sin(Math.PI * e) * p.arc];
        }
        if (p.phase === "leave" || p.phase === "gone") p.alpha = Math.max(0, 1 - t * 1.2);
        if (t >= 1) {
          if (p.phase === "toAgent" || p.phase === "defer") { p.loop = false; p.phase = "thinking"; p.t0 = nowT; p.dur = 0.35; }
          else if (p.phase === "thinking") decide(p);
          else if (p.phase === "toServer") {
            const dur = (FAST.includes(p.server) ? 1.7 : 4.6) * (mode === "explain" ? 1.1 : 1);
            const start = Math.max(nowT, free[p.server]);
            free[p.server] = start + dur; queued[p.server]++;
            p.leaveAt = start + dur; p.ok = start - p.t0 < (FAST.includes(p.server) ? 3.5 : 6);
            p.phase = "serving"; p.color = COL.fast.top;
          } else if (p.phase === "toBin") { bursts.push({ pos: [...BIN], t: nowT, ok: false }); ps.splice(k, 1); }
          else if (p.phase === "leave") ps.splice(k, 1);
        }
        if (p.phase === "serving" && nowT >= p.leaveAt) {
          queued[p.server] = Math.max(0, queued[p.server] - 1);
          bursts.push({ pos: topPos(p.server), t: nowT, ok: p.ok });
          p.color = p.ok ? COL.ok : COL.bad;
          go(p, [p.pos[0] + 2.2, 1.6, p.pos[2] + 1.6], 0.9, "leave", 0.2);
        }
      }
    };

    const draw = () => {
      ctx.clearRect(0, 0, W, H);
      floor();
      const items: { depth: number; fn: () => void }[] = [];
      for (let i = 0; i < 4; i++) {
        const s = serverPos(i), fast = FAST.includes(i);
        items.push({ depth: project([s[0], s[1], 0])[2], fn: () => box(s, BOX, BOX, fast ? H_FAST : H_SLOW, fast ? COL.fast : COL.slow, queued[i]) });
      }
      items.sort((a, b) => a.depth - b.depth).forEach((it) => it.fn());
      // refuse bin and source marker
      poly([[BIN[0] - 0.6, -0.6, 0], [BIN[0] + 0.6, -0.6, 0], [BIN[0] + 0.6, 0.8, 0], [BIN[0] - 0.6, 0.8, 0]], "rgba(255,122,69,0.10)", "rgba(255,122,69,0.55)");
      label("refused", [BIN[0], 0.1, 0], COL.bad, 11, 20);
      label("requests", SRC, COL.dim, 11, -10);
      for (let i = 0; i < 4; i++) {
        const s = serverPos(i), fast = FAST.includes(i);
        label(fast ? "fast · expensive" : "slow · cheap", [s[0], s[1] + 0.9, 0], fast ? "#9bd9fb" : "#f4c25a", 11, 22);
      }
      for (let i = 0; i < 4; i++) agentDraw(i);
      if (mode === "explain" && props.current.action) { // the path of the chosen action stays visible
        const sc = SCENARIO[props.current.action], a = agentPos(sc.entry);
        ctx.setLineDash([5, 5]); ctx.lineWidth = 2; ctx.strokeStyle = "rgba(255,255,255,0.35)";
        const target = props.current.action === "accept" ? topPos(sc.entry) : props.current.action === "forward" ? agentPos(0) : props.current.action === "reject" ? BIN : a;
        const [x0, y0] = project(a), [x1, y1] = project(target);
        ctx.beginPath(); ctx.moveTo(x0, y0);
        if (props.current.action === "defer") ctx.arc(x0, y0 - 22, 22, 0, 6.283); else ctx.quadraticCurveTo((x0 + x1) / 2, Math.min(y0, y1) - 40, x1, y1);
        ctx.stroke(); ctx.setLineDash([]);
      }
      bursts.forEach((b) => {
        const t = (nowT - b.t) / 0.7; if (t > 1) return;
        const [x, y] = project(b.pos); ctx.strokeStyle = b.ok ? COL.ok : COL.bad; ctx.globalAlpha = 1 - t; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(x, y, 6 + t * 26, 0, 6.283); ctx.stroke(); ctx.globalAlpha = 1;
      });
      ps.slice().sort((a, b) => project(a.pos)[2] - project(b.pos)[2]).forEach((p) => {
        const [x, y] = project(p.pos);
        const g = ctx.createRadialGradient(x, y, 0, x, y, 14); g.addColorStop(0, p.color); g.addColorStop(1, "rgba(0,0,0,0)");
        ctx.globalAlpha = 0.5 * p.alpha; ctx.fillStyle = g; ctx.fillRect(x - 14, y - 14, 28, 28);
        ctx.globalAlpha = p.alpha; ctx.fillStyle = p.color; ctx.beginPath(); ctx.arc(x, y, 4.2, 0, 6.283); ctx.fill(); ctx.globalAlpha = 1;
      });
    };

    const targetYaw = () => {
      const base = mode === "hero" ? 0.5 : 0.3;
      const scroll = scrollLinked ? Math.min(window.scrollY / 900, 1) * 0.45 : 0;
      return base + scroll + mouse * 0.12 + (reduced ? 0 : Math.sin(nowT * 0.25) * 0.04);
    };

    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      if (!visible) { last = now; return; }
      const dt = Math.min((now - last) / 1000, 0.05); last = now;
      yaw += (targetYaw() - yaw) * Math.min(dt * 4, 1);
      step(dt); draw();
    };

    const onMove = (e: PointerEvent) => { const r = canvas.getBoundingClientRect(); mouse = ((e.clientX - r.left) / r.width - 0.5) * 2; };
    resize();
    yaw = targetYaw();
    if (mode === "explain") { nowT = 0; spawn(SCENARIO[props.current.action ?? "accept"].entry); }
    if (reduced) {
      if (mode === "hero") { for (let i = 0; i < 6; i++) { spawn(); step(0.5); } }
      else { for (let i = 0; i < 6; i++) step(0.4); }
      draw();
      return () => undefined;
    }
    const io = new IntersectionObserver(([en]) => { visible = en.isIntersecting; });
    io.observe(canvas);
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    window.addEventListener("pointermove", onMove, { passive: true });
    raf = requestAnimationFrame(frame);
    // explain mode: replay the scripted request when the action changes
    (canvas as HTMLCanvasElement & { replay?: () => void }).replay = () => { ps.length = 0; free.fill(0); queued.fill(0); spawn(SCENARIO[props.current.action ?? "accept"].entry); };
    return () => { cancelAnimationFrame(raf); io.disconnect(); ro.disconnect(); window.removeEventListener("pointermove", onMove); };
  }, [mode, reduced, scrollLinked]);

  useEffect(() => { (ref.current as (HTMLCanvasElement & { replay?: () => void }) | null)?.replay?.(); }, [action, playKey]);

  return (
    <canvas ref={ref} className="iso" style={{ width: "100%", height }} role="img"
      aria-label="Isometric picture of four servers, two fast and two slow, each with a router agent above it. Requests arrive from the left and each agent accepts, forwards, defers or rejects them." />
  );
}
