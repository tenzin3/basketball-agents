"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CourtStep } from "@/lib/types";
import { PLAYER_COLORS, SHORT, slugFor } from "@/lib/format";

/* Half court, basket at the top. 10 px = 1 ft. Court is 50 ft wide, 47 ft deep. */
type Pt = { x: number; y: number };
const RIM: Pt = { x: 250, y: 52 };

export const LOCATIONS: Record<string, Pt> = {
  rim: { x: 250, y: 64 },
  left_dunker: { x: 178, y: 46 },
  right_dunker: { x: 322, y: 46 },
  left_block: { x: 160, y: 108 },
  right_block: { x: 340, y: 108 },
  left_short_corner: { x: 108, y: 92 },
  right_short_corner: { x: 392, y: 92 },
  left_elbow: { x: 172, y: 190 },
  right_elbow: { x: 328, y: 190 },
  free_throw_line: { x: 250, y: 190 },
  left_corner: { x: 34, y: 42 },
  right_corner: { x: 466, y: 42 },
  left_wing: { x: 66, y: 228 },
  right_wing: { x: 434, y: 228 },
  left_slot: { x: 150, y: 300 },
  right_slot: { x: 350, y: 300 },
  top_of_key: { x: 250, y: 318 },
  backcourt: { x: 250, y: 452 },
  left_sideline_inbound: { x: -16, y: 250 },
  right_sideline_inbound: { x: 516, y: 250 },
  baseline_inbound: { x: 300, y: -16 },
};

const DEFAULT_START: Record<string, string> = {
  curry: "top_of_key", kobe: "right_wing", jordan: "left_wing", durant: "left_corner", lebron: "right_elbow",
};
const MOVE_ACTIONS = new Set(["dribble", "drive", "cut", "space", "relocate", "roll", "pop", "post_up", "screen", "shoot", "inbound"]);
const PASS_ACTIONS = new Set(["pass", "handoff", "inbound"]);

type State = { pos: Record<string, Pt>; holder: string | null; ball: Pt };

const lerp = (a: Pt, b: Pt, p: number): Pt => ({ x: a.x + (b.x - a.x) * p, y: a.y + (b.y - a.y) * p });
const ease = (p: number) => (p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2);

function screenSpot(target: Pt, from: Pt): Pt {
  // stand ~3 ft from the teammate, on the side the screener is coming from
  const dx = from.x - target.x, dy = from.y - target.y;
  const d = Math.hypot(dx, dy) || 1;
  return { x: target.x + (dx / d) * 30, y: target.y + (dy / d) * 30 };
}

interface Prepared { steps: (CourtStep & { slug?: string; targetSlug?: string; d: number })[]; start: State; end: number }

function prepare(start: Record<string, string | null> | undefined, ballStart: string | undefined, seq: CourtStep[]): Prepared {
  const pos: Record<string, Pt> = {};
  const used: Pt[] = [];
  for (const slug of Object.keys(DEFAULT_START)) {
    const entry = Object.entries(start ?? {}).find(([n]) => slugFor(n) === slug);
    const locName: string | null | undefined = entry ? entry[1] : undefined;
    const loc = (locName ? LOCATIONS[locName] : undefined) ?? LOCATIONS[DEFAULT_START[slug]];
    let p = { ...loc };
    while (used.some((u) => Math.hypot(u.x - p.x, u.y - p.y) < 20)) p = { x: p.x + 22, y: p.y + 14 };
    used.push(p);
    pos[slug] = p;
  }
  const holder = slugFor(ballStart) ?? "curry";
  const steps = [...seq].sort((a, b) => a.time - b.time).map((s, i, arr) => {
    const next = arr.slice(i + 1).find((n) => n.time > s.time);
    const d = Math.min(1.2, Math.max(0.45, next ? next.time - s.time : 1));
    return { ...s, slug: slugFor(s.player), targetSlug: slugFor(s.target), d };
  });
  const end = steps.length ? Math.max(...steps.map((s) => s.time + s.d)) : 0;
  return { steps, start: { pos, holder, ball: pos[holder] ?? RIM }, end };
}

function stateAt(prep: Prepared, t: number): State {
  const pos: Record<string, Pt> = Object.fromEntries(Object.entries(prep.start.pos).map(([k, v]) => [k, { ...v }]));
  let holder: string | null = prep.start.holder;
  let flight: Pt | null = null;
  for (const s of prep.steps) {
    const raw = (t - s.time) / s.d;
    if (raw <= 0) break;
    const p = ease(Math.min(1, raw));
    const who = s.slug;
    if (!who || !pos[who]) continue;
    const dest = (s.destination && LOCATIONS[s.destination]) || (s.location && LOCATIONS[s.location]) || null;
    if (s.action === "screen" && s.targetSlug && pos[s.targetSlug]) {
      // a screen is set on the teammate, so stand next to them (the stated location is where the action happens)
      const spot = screenSpot(pos[s.targetSlug], pos[who]);
      pos[who] = lerp(pos[who], spot, p);
    } else if (MOVE_ACTIONS.has(s.action) && dest && s.action !== "inbound") {
      pos[who] = lerp(pos[who], dest, p);
    }
    if (PASS_ACTIONS.has(s.action) && s.targetSlug && pos[s.targetSlug]) {
      if (s.action === "handoff" && p < 1) pos[s.targetSlug] = lerp(pos[s.targetSlug], { x: pos[who].x + 18, y: pos[who].y + 6 }, p);
      if (p < 1) flight = lerp(pos[who], pos[s.targetSlug], p);
      else { holder = s.targetSlug; flight = null; }
    }
    if (s.action === "shoot") {
      const from = pos[who];
      if (p < 1) {
        const b = lerp(from, RIM, p);
        flight = { x: b.x, y: b.y - Math.sin(p * Math.PI) * 60 };
      } else { holder = null; flight = { ...RIM }; }
    }
  }
  const ball = flight ?? (holder && pos[holder] ? { x: pos[holder].x + 11, y: pos[holder].y - 11 } : RIM);
  return { pos, holder, ball };
}

function arrowPath(a: Pt, b: Pt) {
  return `M${a.x.toFixed(1)},${a.y.toFixed(1)} L${b.x.toFixed(1)},${b.y.toFixed(1)}`;
}

export default function Court({ startPositions, ballStartsWith, sequence }: {
  startPositions?: Record<string, string | null>;
  ballStartsWith?: string;
  sequence: CourtStep[];
}) {
  const prep = useMemo(() => prepare(startPositions, ballStartsWith, sequence), [startPositions, ballStartsWith, sequence]);
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const raf = useRef<number | null>(null);
  const last = useRef<number | null>(null);

  useEffect(() => {
    // start the animation once; with reduced motion, show the finished play instead
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduced) { setT(prep.end); setPlaying(false); }
    else { setT(0); setPlaying(prep.steps.length > 0); }
  }, [prep]);

  const tick = useCallback((now: number) => {
    if (last.current != null) {
      const dt = (now - last.current) / 1000;
      setT((x) => {
        const nx = x + dt * 0.8; // slightly slower than real time so the action is readable
        if (nx >= prep.end) { setPlaying(false); return prep.end; }
        return nx;
      });
    }
    last.current = now;
    raf.current = requestAnimationFrame(tick);
  }, [prep.end]);

  useEffect(() => {
    if (!playing) { last.current = null; return; }
    raf.current = requestAnimationFrame(tick);
    return () => { if (raf.current) cancelAnimationFrame(raf.current); last.current = null; };
  }, [playing, tick]);

  const st = stateAt(prep, t);
  const traces = prep.steps.map((s) => {
    const before = stateAt(prep, s.time);
    const after = stateAt(prep, s.time + s.d);
    const who = s.slug ?? "";
    const a = before.pos[who];
    let b = after.pos[who];
    if (!a) return null;
    if (PASS_ACTIONS.has(s.action) && s.targetSlug) b = after.pos[s.targetSlug];
    if (s.action === "shoot") b = RIM;
    return { s, a, b, done: t >= s.time + s.d * 0.98, active: t >= s.time && t < s.time + s.d };
  });
  const activeIdx = traces.findIndex((x) => x?.active);

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_16rem]">
      <figure className="overflow-hidden rounded-md border border-wood-dark/50">
        <svg viewBox="-30 -30 560 510" role="img" aria-label="Half-court diagram of the coach's play" className="block w-full">
          <rect x={-30} y={-30} width={560} height={510} fill="#e9eef3" />
          <rect x={0} y={0} width={500} height={470} fill="var(--color-wood)" />
          <rect x={170} y={0} width={160} height={190} fill="#c4823f" opacity={0.55} />
          <g fill="none" stroke="#fffaf0" strokeWidth={2.5}>
            <rect x={0} y={0} width={500} height={470} />
            <rect x={170} y={0} width={160} height={190} />
            <circle cx={250} cy={190} r={60} />
            <path d="M210,52 A40,40 0 0 0 290,52" />
            <path d={`M30,0 L30,140 A237.5,237.5 0 0 0 470,140 L470,0`} />
            <path d="M190,470 A60,60 0 0 1 310,470" />
            <line x1={220} y1={40} x2={280} y2={40} />
          </g>
          <circle cx={RIM.x} cy={RIM.y} r={7.5} fill="none" stroke="#e5582a" strokeWidth={3} />

          <defs>
            {Object.entries(PLAYER_COLORS).map(([slug, c]) => (
              <marker key={slug} id={`ah-${slug}`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                <path d="M0,0 L10,5 L0,10 z" fill={c} />
              </marker>
            ))}
          </defs>

          {traces.map((tr, i) => {
            if (!tr || !tr.s.slug) return null;
            const c = PLAYER_COLORS[tr.s.slug];
            const vis = tr.done || tr.active ? 0.95 : 0.22;
            const isPass = PASS_ACTIONS.has(tr.s.action);
            const isShot = tr.s.action === "shoot";
            if (Math.hypot(tr.b.x - tr.a.x, tr.b.y - tr.a.y) < 4) return null;
            if (tr.s.action === "screen") {
              const dx = tr.b.x - tr.a.x, dy = tr.b.y - tr.a.y, d = Math.hypot(dx, dy) || 1;
              const nx = -dy / d * 10, ny = dx / d * 10;
              return (
                <g key={i} stroke={c} strokeWidth={3} strokeLinecap="round" opacity={vis}>
                  <path d={arrowPath(tr.a, tr.b)} />
                  <line x1={tr.b.x - nx} y1={tr.b.y - ny} x2={tr.b.x + nx} y2={tr.b.y + ny} />
                </g>
              );
            }
            return (
              <path key={i} d={arrowPath(tr.a, tr.b)} stroke={c} strokeWidth={isPass ? 2.5 : 3} fill="none"
                strokeDasharray={isPass ? "8 7" : isShot ? "2 7" : undefined} strokeLinecap="round"
                markerEnd={`url(#ah-${tr.s.slug})`} opacity={vis} />
            );
          })}

          {Object.entries(st.pos).map(([slug, p]) => (
            <g key={slug} transform={`translate(${p.x},${p.y})`}>
              <circle r={15} fill={PLAYER_COLORS[slug]} stroke="#fff" strokeWidth={2.5} />
              <text y={33} textAnchor="middle" className="font-display" fontSize={17} fontWeight={700} fill="#18233a"
                stroke="#fffaf0" strokeWidth={4} paintOrder="stroke">{SHORT[slug]}</text>
            </g>
          ))}
          <circle cx={st.ball.x} cy={st.ball.y} r={7} fill="#e5582a" stroke="#7a2c0f" strokeWidth={1.5} />
        </svg>
        <figcaption className="flex flex-wrap items-center gap-3 border-t border-wood-dark/40 bg-sheet px-3 py-2 text-sm">
          <button type="button" className="rounded border border-rule px-3 py-1 font-semibold"
            onClick={() => { if (t >= prep.end) setT(0); setPlaying((x) => !x); }} disabled={!prep.steps.length}>
            {playing ? "Pause" : t >= prep.end && t > 0 ? "Replay" : "Play"}
          </button>
          <input type="range" min={0} max={prep.end || 1} step={0.01} value={t} aria-label="Play timeline"
            onChange={(e) => { setPlaying(false); setT(Number(e.target.value)); }} className="min-w-40 flex-1 accent-[var(--color-marker)]" />
          <span className="tabular text-ink-soft">{t.toFixed(1)}s</span>
        </figcaption>
      </figure>

      <ol className="space-y-1.5 text-sm">
        {prep.steps.length === 0 && <li className="text-ink-soft">The coach did not return court instructions.</li>}
        {prep.steps.map((s, i) => (
          <li key={i}>
            <button type="button" onClick={() => { setPlaying(false); setT(s.time + s.d); }}
              className={`w-full rounded px-2 py-1 text-left ${i === activeIdx ? "bg-board-2" : ""}`}>
              <span className="tabular mr-2 text-ink-soft">{s.time.toFixed(1)}s</span>
              <span className="font-semibold" style={{ color: s.slug ? PLAYER_COLORS[s.slug] : undefined }}>
                {s.slug ? SHORT[s.slug] : s.player}
              </span>{" "}
              {s.action.replace("_", " ")}
              {s.target ? ` ${s.action === "pass" ? "to" : "for"} ${SHORT[slugFor(s.target) ?? ""] ?? s.target}` : ""}
              {s.destination ? ` to ${s.destination.replace(/_/g, " ")}` : s.location ? ` at ${s.location.replace(/_/g, " ")}` : ""}
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}
