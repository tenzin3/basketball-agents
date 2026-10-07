"use client";

import { useState } from "react";

export interface ScenarioState {
  score_margin: number;
  quarter: number;
  game_clock: number;
  shot_clock: number;
  timeouts: number;
  possession_start: string;
  defensive_scheme: string;
  opponent_notes: string;
  question: string;
}

const PRESETS: { label: string; s: Partial<ScenarioState> }[] = [
  {
    label: "Down 1, 9 seconds, they switch everything",
    s: { score_margin: -1, game_clock: 9, shot_clock: 9, timeouts: 0, possession_start: "frontcourt, live ball",
         defensive_scheme: "switch everything", question: "Down 1 with 9 seconds remaining. What play should we run and who should take the final shot?" },
  },
  {
    label: "Tied, 24 seconds, drop coverage",
    s: { score_margin: 0, game_clock: 24, shot_clock: 24, timeouts: 1, possession_start: "after timeout, sideline out of bounds",
         defensive_scheme: "drop coverage on ball screens, help from the nail", question: "Tied with 24 seconds left. How do we get the last shot and who takes it?" },
  },
  {
    label: "Down 3, 5 seconds, full court",
    s: { score_margin: -3, game_clock: 5, shot_clock: 5, timeouts: 0, possession_start: "baseline inbound, full court",
         defensive_scheme: "deny the inbound, top-locked shooters", question: "Down 3 with 5 seconds and the full court to go. Who shoots, and how do we get it there?" },
  },
  {
    label: "Who should initiate the offense?",
    s: { score_margin: 4, game_clock: 420, shot_clock: 24, timeouts: 3, possession_start: "half court",
         defensive_scheme: "aggressive blitz on ball screens", question: "Against a blitzing defense, who should initiate the offense and through which action?" },
  },
];

const DEFENSES = ["switch everything", "drop coverage", "blitz / trap the ball handler", "2-3 zone", "box-and-one", "ice side pick-and-rolls"];

export default function ScenarioForm({ onSubmit, busy, error }: {
  onSubmit: (s: ScenarioState, provider: string) => void;
  busy: boolean;
  error?: string | null;
}) {
  const [s, setS] = useState<ScenarioState>({
    score_margin: -1, quarter: 4, game_clock: 9, shot_clock: 9, timeouts: 0, possession_start: "frontcourt, live ball",
    defensive_scheme: "switch everything", opponent_notes: "",
    question: "Down 1 with 9 seconds remaining. What play should we run and who should take the final shot?",
  });
  const [provider, setProvider] = useState("");
  const set = <K extends keyof ScenarioState>(k: K, v: ScenarioState[K]) => setS((x) => ({ ...x, [k]: v }));

  const numField = (k: keyof ScenarioState, label: string, min: number, max: number, step = 1) => (
    <label className="flex flex-col items-center rounded-md bg-ink px-3 pb-2 pt-1.5 text-board">
      <span className="text-xs text-board/70">{label}</span>
      <input
        type="number" min={min} max={max} step={step}
        value={s[k] as number}
        onChange={(e) => set(k, Number(e.target.value) as never)}
        className="tabular w-full bg-transparent text-center font-display text-4xl font-semibold text-[#ffcf5c] outline-none"
      />
    </label>
  );

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); onSubmit(s, provider); }}
      className="rounded-md border border-rule bg-sheet p-4 sm:p-6"
    >
      <div className="flex flex-wrap gap-2">
        {PRESETS.map((p) => (
          <button key={p.label} type="button" onClick={() => setS((x) => ({ ...x, ...p.s }))}
            className="rounded-full border border-rule px-3 py-1 text-sm hover:border-ink">
            {p.label}
          </button>
        ))}
      </div>

      <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-5">
        {numField("score_margin", "Margin", -40, 40)}
        {numField("quarter", "Quarter", 1, 6)}
        {numField("game_clock", "Game clock (s)", 0, 720, 0.1)}
        {numField("shot_clock", "Shot clock (s)", 0, 24, 0.1)}
        {numField("timeouts", "Timeouts", 0, 7)}
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm">
          Defensive scheme
          <input list="defenses" value={s.defensive_scheme} onChange={(e) => set("defensive_scheme", e.target.value)}
            className="rounded border border-rule bg-white px-3 py-2" />
          <datalist id="defenses">{DEFENSES.map((d) => <option key={d} value={d} />)}</datalist>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Possession starts
          <input value={s.possession_start} onChange={(e) => set("possession_start", e.target.value)}
            className="rounded border border-rule bg-white px-3 py-2" />
        </label>
      </div>
      <label className="mt-4 flex flex-col gap-1 text-sm">
        Question for the huddle
        <textarea rows={2} value={s.question} onChange={(e) => set("question", e.target.value)}
          className="rounded border border-rule bg-white px-3 py-2 text-base" />
      </label>
      <label className="mt-4 flex flex-col gap-1 text-sm">
        Opponent notes (optional)
        <input value={s.opponent_notes} onChange={(e) => set("opponent_notes", e.target.value)}
          placeholder="e.g. their center is in foul trouble"
          className="rounded border border-rule bg-white px-3 py-2" />
      </label>

      <div className="mt-6 flex flex-wrap items-center gap-4">
        <button type="submit" disabled={busy}
          className="rounded-md bg-marker px-5 py-2.5 font-display text-xl font-semibold text-white disabled:opacity-60">
          {busy ? "Calling the huddle…" : "Start the huddle"}
        </button>
        <label className="flex items-center gap-2 text-sm text-ink-soft">
          Model
          <select value={provider} onChange={(e) => setProvider(e.target.value)} className="rounded border border-rule bg-white px-2 py-1">
            <option value="">Server default</option>
            <option value="anthropic">Anthropic</option>
            <option value="openai">OpenAI</option>
            <option value="gemini">Gemini</option>
            <option value="local">Local model</option>
            <option value="mock">Mock (offline test)</option>
          </select>
        </label>
        {error && <p role="alert" className="text-sm text-marker-red">{error}</p>}
      </div>
    </form>
  );
}
