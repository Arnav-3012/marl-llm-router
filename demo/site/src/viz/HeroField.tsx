// Hero illustration: synthetic requests flow in, 4 router agents decide Accept / Forward / Defer, servers queue and
// serve them. It is an ILLUSTRATION of the idea (random requests, toy rules), not measured data, and says so.
// Scroll makes the offered load rise. Reduced motion: one static frame, no animation loop.
import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "../ui";

type Req = { id: number; x: number; y: number; r: number; size: number; born: number; phase: string; agent: number; server: number; t0: number; fx: number; fy: number; tx: number; ty: number; dur: number; label?: string; defers: number };
const FAST = [0, 2];
const C = { fast: "#56b4e9", slow: "#e69f00", ok: "#009e73", bad: "#d55e00", accent: "#7170ff", text: "#d0d6e0", dim: "#8a8f98" };

export function HeroField() {
  const ref = useRef<HTMLCanvasElement>(null);
  const reduced = useReducedMotion();
  const [stats, setStats] = useState({ ok: 0, missed: 0, rho: 0.5 });

  useEffect(() => {
    const canvas = ref.current!;
    const ctx = canvas.getContext("2d")!;
    let W = 0, H = 0, raf = 0, visible = true, last = performance.now(), spawnAcc = 0, uid = 0, nowT = 0, hudT = 0;
    const reqs: Req[] = [];
    const queues: Req[][] = [[], [], [], []];
    const serving: (Req | null)[] = [null, null, null, null];
    const bursts: { x: number; y: number; t: number; ok: boolean }[] = [];
    const tally = { ok: 0, missed: 0 };
    let scroll = 0;
    const rng = Math.random;

    const layout = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = canvas.clientWidth; H = canvas.clientHeight;
      canvas.width = W * dpr; canvas.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    const ay = (i: number) => H * (0.17 + i * 0.22);
    const ax = () => W * 0.3;
    const sx = () => W * 0.86;
    const slotX = (i: number) => sx() - 46 - i * 13;

    const move = (r: Req, tx: number, ty: number, dur: number, phase: string) => {
      r.fx = r.x; r.fy = r.y; r.tx = tx; r.ty = ty; r.t0 = nowT; r.dur = dur; r.phase = phase;
    };
    const spawn = () => {
      const size = Math.min(1, Math.exp(rng() * 1.6 - 1.2));
      const a = Math.floor(rng() * 4);
      const r: Req = { id: uid++, x: 8, y: ay(a) + (rng() - 0.5) * 30, r: 3 + size * 5, size, born: nowT, phase: "in", agent: a, server: -1, t0: nowT, fx: 8, fy: 0, tx: 0, ty: 0, dur: 0.9, defers: 0 };
      move(r, ax() - 22, ay(a), 0.9, "in");
      reqs.push(r);
    };
    const decide = (r: Req) => {
      const a = r.agent, q = queues[a].length + (serving[a] ? 1 : 0);
      const nb = [(a + 1) % 4, (a + 3) % 4];
      const best = nb.reduce((m, j) => (queues[j].length + (serving[j] ? 1 : 0) < queues[m].length + (serving[m] ? 1 : 0) ? j : m), nb[0]);
      const qb = queues[best].length + (serving[best] ? 1 : 0);
      if (q <= 2 || (qb >= q && r.defers >= 2)) { r.label = "accept"; r.server = a; toServer(r); }
      else if (qb < q) { r.label = "forward"; r.agent = best; move(r, ax() - 22, ay(best), 0.55, "fwd"); }
      else { r.label = "defer"; r.defers++; move(r, r.x, r.y, 0.5, "defer"); }
    };
    const toServer = (r: Req) => {
      const i = queues[r.server].length;
      queues[r.server].push(r);
      move(r, slotX(Math.min(i, 8)), ay(r.server), 0.7, "toq");
    };
    const finish = (s: number, r: Req) => {
      const waited = nowT - r.born, ok = waited < 4.2;
      (ok ? tally.ok++ : tally.missed++);
      bursts.push({ x: sx(), y: ay(s), t: nowT, ok });
      serving[s] = null;
      const i = reqs.indexOf(r); if (i >= 0) reqs.splice(i, 1);
    };

    const step = (dt: number) => {
      nowT += dt;
      const rate = 0.9 + 3.2 * scroll;                      // offered load rises as the page scrolls
      spawnAcc += dt * rate;
      while (spawnAcc >= 1) { spawnAcc -= 1; if (reqs.length < 60) spawn(); }
      for (const r of reqs) {
        const p = r.dur > 0 ? Math.min((nowT - r.t0) / r.dur, 1) : 1;
        const e = 1 - Math.pow(1 - p, 3);
        if (r.phase === "defer") { r.x = r.fx + Math.sin(p * Math.PI * 2) * 10; r.y = r.fy - Math.sin(p * Math.PI) * 16; }
        else if (r.phase !== "wait" && r.phase !== "serve") { r.x = r.fx + (r.tx - r.fx) * e; r.y = r.fy + (r.ty - r.fy) * e; }
        if (p >= 1) {
          if (r.phase === "in" || r.phase === "fwd" || r.phase === "defer") { r.phase = "think"; r.t0 = nowT; r.dur = 0.22; }
          else if (r.phase === "think") decide(r);
          else if (r.phase === "toq") r.phase = "wait";
        }
      }
      for (let s = 0; s < 4; s++) {
        if (!serving[s] && queues[s].length && queues[s][0].phase === "wait") {
          const r = queues[s].shift()!; serving[s] = r; r.phase = "serve";
          const speed = FAST.includes(s) ? 1 : 2.4;
          r.t0 = nowT; r.dur = (0.5 + r.size * 1.1) * speed;
          move(r, sx(), ay(s), 0.35, "toserve"); r.phase = "toserve";
        }
        queues[s].forEach((r, i) => { if (r.phase === "wait") { r.tx = slotX(Math.min(i, 8)); r.x += (r.tx - r.x) * Math.min(dt * 8, 1); r.y = ay(s); } });
        const r = serving[s];
        if (r && r.phase === "toserve") { const p = (nowT - r.t0) / 0.35; if (p >= 1) { r.phase = "serve"; r.t0 = nowT; } }
        else if (r && r.phase === "serve" && nowT - r.t0 > (0.5 + r.size * 1.1) * (FAST.includes(s) ? 1 : 2.4)) finish(s, r);
      }
      while (bursts.length && nowT - bursts[0].t > 0.9) bursts.shift();
    };

    const draw = () => {
      ctx.clearRect(0, 0, W, H);
      ctx.lineWidth = 1;
      // ring links between neighbouring agents
      ctx.strokeStyle = "rgba(255,255,255,0.08)";
      for (let i = 0; i < 4; i++) { ctx.beginPath(); ctx.moveTo(ax(), ay(i)); ctx.lineTo(ax(), ay((i + 1) % 4)); ctx.stroke(); }
      ctx.setLineDash([4, 6]); ctx.strokeStyle = "rgba(113,112,255,0.35)";
      for (let i = 0; i < 4; i++) { ctx.lineDashOffset = -nowT * 18; ctx.beginPath(); ctx.moveTo(ax() + 22, ay(i)); ctx.lineTo(sx() - 28, ay(i)); ctx.stroke(); }
      ctx.setLineDash([]);
      for (let i = 0; i < 4; i++) {
        const y = ay(i), fast = FAST.includes(i);
        // agent node (hexagon) with a decision label
        ctx.fillStyle = "rgba(113,112,255,0.18)"; ctx.strokeStyle = C.accent; ctx.beginPath();
        for (let k = 0; k < 6; k++) { const a = (Math.PI / 3) * k + Math.PI / 6; ctx.lineTo(ax() + Math.cos(a) * 17, y + Math.sin(a) * 17); }
        ctx.closePath(); ctx.fill(); ctx.stroke();
        ctx.fillStyle = C.text; ctx.font = "500 10px Inter, system-ui, sans-serif"; ctx.textAlign = "center"; ctx.fillText(`A${i}`, ax(), y + 3.5);
        // server: fast = solid rounded square, slow = dashed circle (shape, not only colour)
        const col = fast ? C.fast : C.slow, busy = !!serving[i];
        ctx.lineWidth = 2; ctx.strokeStyle = col; ctx.fillStyle = busy ? (fast ? "rgba(86,180,233,0.28)" : "rgba(230,159,0,0.26)") : "rgba(255,255,255,0.03)";
        if (fast) { ctx.beginPath(); ctx.roundRect(sx() - 22, y - 22, 44, 44, 9); ctx.fill(); ctx.stroke(); }
        else { ctx.setLineDash([4, 3]); ctx.beginPath(); ctx.arc(sx(), y, 23, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); ctx.setLineDash([]); }
        ctx.lineWidth = 1;
        ctx.fillStyle = C.dim; ctx.textAlign = "left"; ctx.font = "400 10px Inter, system-ui, sans-serif";
        ctx.fillText(fast ? "fast · expensive" : "slow · cheap", sx() - 40, y + 40);
        const q = queues[i].length;                          // queue length bar under the server
        ctx.fillStyle = "rgba(255,255,255,0.08)"; ctx.fillRect(sx() - 22, y + 27, 44, 4);
        ctx.fillStyle = q > 5 ? C.bad : col; ctx.fillRect(sx() - 22, y + 27, Math.min(q / 8, 1) * 44, 4);
      }
      for (const r of reqs) {
        ctx.beginPath(); ctx.arc(r.x, r.y, r.r, 0, Math.PI * 2);
        ctx.fillStyle = r.phase === "serve" ? "#f7f8f8" : "rgba(247,248,248,0.82)"; ctx.fill();
        if (r.phase === "think") { ctx.strokeStyle = C.accent; ctx.lineWidth = 1.5; ctx.stroke(); ctx.lineWidth = 1; }
        if (r.phase === "fwd") { ctx.strokeStyle = C.accent; ctx.beginPath(); ctx.moveTo(r.x, r.y); ctx.lineTo(r.fx, r.fy); ctx.stroke(); }
      }
      for (const b of bursts) {
        const p = (nowT - b.t) / 0.9;
        ctx.strokeStyle = b.ok ? C.ok : C.bad; ctx.lineWidth = 2; ctx.globalAlpha = 1 - p;
        ctx.beginPath(); ctx.arc(b.x, b.y, 24 + p * 22, 0, Math.PI * 2); ctx.stroke();
        if (!b.ok) { ctx.beginPath(); ctx.moveTo(b.x - 6, b.y - 6); ctx.lineTo(b.x + 6, b.y + 6); ctx.moveTo(b.x + 6, b.y - 6); ctx.lineTo(b.x - 6, b.y + 6); ctx.stroke(); }
        ctx.globalAlpha = 1; ctx.lineWidth = 1;
      }
      ctx.fillStyle = C.dim; ctx.font = "500 10px Inter, system-ui, sans-serif"; ctx.textAlign = "center";
      ctx.fillText("requests", 34, 14); ctx.fillText("router agents", ax(), 14); ctx.fillText("servers", sx(), 14);
    };

    const frame = (t: number) => {
      const dt = Math.min((t - last) / 1000, 0.05); last = t;
      if (visible) {
        step(dt); draw();
        hudT += dt;
        if (hudT > 0.5) { hudT = 0; setStats({ ok: tally.ok, missed: tally.missed, rho: Math.round((0.35 + 0.6 * scroll) * 100) / 100 }); }
      }
      raf = requestAnimationFrame(frame);
    };

    layout();
    const onScroll = () => { scroll = Math.min(window.scrollY / 700, 1); };
    const ro = new ResizeObserver(layout); ro.observe(canvas);
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; last = performance.now(); }); io.observe(canvas);
    window.addEventListener("scroll", onScroll, { passive: true });
    if (reduced) {                                           // static frame: simulate 6 s ahead once
      for (let i = 0; i < 360; i++) step(1 / 60);
      draw(); setStats({ ok: tally.ok, missed: tally.missed, rho: 0.5 });
    } else raf = requestAnimationFrame(frame);
    return () => { cancelAnimationFrame(raf); ro.disconnect(); io.disconnect(); window.removeEventListener("scroll", onScroll); };
  }, [reduced]);

  return (
    <div className="hero-art">
      <canvas ref={ref} role="img" aria-label="Animated illustration: requests flow to four router agents, which accept, forward or defer them to fast and slow servers" />
      <div className="hud">
        <span>illustration with synthetic requests · not measured data</span>
        <span>met SLA <b style={{ color: "#7be0c3" }}>{stats.ok}</b> · missed <b style={{ color: "#ffb37a" }}>{stats.missed}</b> · load rises as you scroll (≈ ρ {stats.rho})</span>
      </div>
    </div>
  );
}
