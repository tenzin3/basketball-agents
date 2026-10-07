"use client";

import { useState } from "react";
import type { SimMessage } from "@/lib/types";
import { PLAYER_COLORS, SHORT, slugFor } from "@/lib/format";

const ROUNDS = [
  { n: 1, name: "Independent analysis", blurb: "Each agent proposes a play without seeing the others." },
  { n: 2, name: "Discussion", blurb: "Agents react to all five proposals and revise." },
  { n: 3, name: "Final position", blurb: "Each agent casts a final vote." },
];

function Detail({ k, v }: { k: string; v: any }) {
  if (v == null || v === "" || (Array.isArray(v) && !v.length)) return null;
  return (
    <div className="grid grid-cols-[8.5rem_1fr] gap-2">
      <dt className="text-ink-soft">{k}</dt>
      <dd>{Array.isArray(v) ? <ul className="list-disc pl-4">{v.map((x, i) => <li key={i}>{typeof x === "string" ? x : JSON.stringify(x)}</li>)}</ul> : String(v)}</dd>
    </div>
  );
}

function Message({ m, onWhy }: { m: SimMessage; onWhy: (m: SimMessage) => void }) {
  const [open, setOpen] = useState(false);
  const c = m.content ?? {};
  const color = PLAYER_COLORS[m.slug];
  const line: string =
    c.huddle_line || c.proposed_play || c.revised_proposal || c.final_vote || (c.parse_error ? "The agent's reply could not be read as JSON." : "");
  return (
    <li className="rounded-md border border-rule bg-sheet" style={{ borderLeft: `5px solid ${color}` }}>
      <div className="p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h4 className="font-display text-2xl font-bold" style={{ color }}>{SHORT[m.slug]} agent</h4>
          {typeof c.confidence === "number" && <span className="tabular text-sm text-ink-soft">confidence {c.confidence}</span>}
        </div>
        <p className="mt-1 max-w-[70ch] text-lg leading-snug">{line}</p>
        {m.round === 1 && (c.primary_option || c.play_name) && (
          <p className="mt-2 text-sm text-ink-soft">
            {c.play_name && <><span className="font-semibold text-ink">{c.play_name}</span>. </>}
            {c.primary_option && <>Primary: {c.primary_option}. </>}
            {c.secondary_option && <>Then: {c.secondary_option}.</>}
          </p>
        )}
        {m.round === 2 && Array.isArray(c.evaluations) && (
          <ul className="mt-2 flex flex-wrap gap-1.5 text-xs">
            {c.evaluations.filter((e: any) => e && typeof e === "object").map((e: any, i: number) => {
              const s = slugFor(e.of_player);
              const mark = e.stance === "agree" ? "agrees with" : e.stance === "disagree" ? "disagrees with" : "partly agrees with";
              return (
                <li key={i} className="rounded-full border border-rule px-2 py-0.5" title={e.comment}>
                  {mark} <span style={{ color: s ? PLAYER_COLORS[s] : undefined }}>{s ? SHORT[s] : e.of_player}</span>
                </li>
              );
            })}
            {c.changed_position && <li className="rounded-full bg-board-2 px-2 py-0.5">changed position</li>}
          </ul>
        )}
        {m.round === 3 && c.preferred_primary_option && (
          <p className="mt-2 text-sm text-ink-soft">Wants the shot for: <span className="text-ink">{c.preferred_primary_option}</span></p>
        )}
        <div className="mt-3 flex flex-wrap gap-2 text-sm">
          <button type="button" onClick={() => setOpen((x) => !x)} aria-expanded={open}
            className="rounded border border-rule px-2.5 py-1 hover:border-ink">{open ? "Hide details" : "Show details"}</button>
          <button type="button" onClick={() => onWhy(m)} className="rounded border border-rule px-2.5 py-1 hover:border-ink">
            Why did {SHORT[m.slug]} say this?
          </button>
        </div>
      </div>
      {open && (
        <dl className="space-y-2 border-t border-rule p-4 text-sm">
          {m.round === 1 && <>
            <Detail k="Play" v={c.proposed_play} />
            <Detail k="Primary" v={c.primary_option} />
            <Detail k="Secondary" v={c.secondary_option} />
            <Detail k="Own role" v={c.your_role} />
            <Detail k="Reasoning" v={c.tactical_reasoning} />
            <Detail k="Risks" v={c.risks} />
          </>}
          {m.round === 2 && <>
            {Array.isArray(c.evaluations) && c.evaluations.map((e: any, i: number) => <Detail key={i} k={`On ${SHORT[slugFor(e?.of_player) ?? ""] ?? e?.of_player}`} v={`${e?.stance ?? ""}: ${e?.comment ?? ""}`} />)}
            <Detail k="Spacing" v={c.spacing_concerns} />
            <Detail k="Matchups" v={c.matchup_advantages} />
            <Detail k="Counters" v={c.defensive_counters} />
            <Detail k="Revised play" v={c.revised_proposal} />
          </>}
          {m.round === 3 && <>
            <Detail k="Vote" v={c.final_vote} />
            <Detail k="Backs" v={c.voted_for_proposal_of} />
            <Detail k="Reason" v={c.reason} />
          </>}
          <Detail k="Data cited" v={c.data_support} />
          {c.parse_error && <Detail k="Raw reply" v={c.raw} />}
        </dl>
      )}
    </li>
  );
}

export default function HuddleFeed({ messages, onWhy, currentRound }: {
  messages: SimMessage[]; onWhy: (m: SimMessage) => void; currentRound: number;
}) {
  const available = ROUNDS.filter((r) => messages.some((m) => m.round === r.n));
  const [sel, setSel] = useState<number | null>(null);
  const active = sel ?? (available.length ? available[available.length - 1].n : 1);
  const msgs = messages.filter((m) => m.round === active);
  const order = ["curry", "kobe", "jordan", "durant", "lebron"];
  msgs.sort((a, b) => order.indexOf(a.slug) - order.indexOf(b.slug));

  const votes = active === 3 ? msgs.reduce<Record<string, number>>((acc, m) => {
    const s = slugFor(m.content?.voted_for_proposal_of);
    if (s) acc[s] = (acc[s] ?? 0) + 1;
    return acc;
  }, {}) : null;

  return (
    <div>
      <div role="tablist" aria-label="Debate rounds" className="flex flex-wrap gap-x-6 gap-y-2 border-b border-rule">
        {ROUNDS.map((r) => {
          const has = messages.some((m) => m.round === r.n);
          const running = !has && currentRound === r.n;
          return (
            <button key={r.n} role="tab" type="button" aria-selected={active === r.n} disabled={!has}
              onClick={() => setSel(r.n)}
              className={`-mb-px border-b-[3px] pb-2 font-display text-xl font-semibold disabled:text-ink-soft/50 ${active === r.n ? "border-marker text-ink" : "border-transparent text-ink-soft"}`}>
              Round {r.n}: {r.name}{running ? " (in progress)" : ""}
            </button>
          );
        })}
      </div>
      <p className="mt-3 text-sm text-ink-soft">{ROUNDS.find((r) => r.n === active)?.blurb}</p>
      {votes && Object.keys(votes).length > 0 && (
        <p className="mt-2 text-sm">
          Votes backed:{" "}
          {Object.entries(votes).sort((a, b) => b[1] - a[1]).map(([s, n], i) => (
            <span key={s}>{i > 0 && ", "}<span className="font-semibold" style={{ color: PLAYER_COLORS[s] }}>{SHORT[s]}&apos;s proposal</span> {n}</span>
          ))}
        </p>
      )}
      <ul className="mt-4 space-y-3">
        {msgs.map((m) => <Message key={`${m.round}-${m.slug}`} m={m} onWhy={onWhy} />)}
        {!msgs.length && <li className="text-ink-soft">The agents are thinking…</li>}
      </ul>
    </div>
  );
}
