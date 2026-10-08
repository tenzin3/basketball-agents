"use client";

import { useState } from "react";
import Avatar from "./Avatar";
import Court from "./Court";
import type { CoachDecisionT, SimMessage, Simulation } from "@/lib/types";
import { PLAYER_COLORS, SHORT, slugFor, txt, txtList } from "@/lib/format";

const ORDER = ["curry", "kobe", "jordan", "durant", "lebron"];
const ROUND_TITLE: Record<number, string> = {
  1: "Round 1: first answers, given independently",
  2: "Round 2: debate",
  3: "Round 3: final word",
};

function messageText(m: SimMessage): string {
  const c = m.content ?? {};
  if (c.parse_error) return "This agent's reply couldn't be read. Try asking again.";
  // new chat fields first, then the earlier (scenario-form) fields so old debates still render
  return txt(c.message || c.huddle_line || c.proposed_play || c.revised_proposal || c.final_vote || "");
}

function Detail({ k, v }: { k: string; v: any }) {
  if (v == null || v === "" || (Array.isArray(v) && !v.length)) return null;
  return (
    <div className="grid grid-cols-[7.5rem_1fr] gap-2">
      <dt className="text-ink-soft">{k}</dt>
      <dd>{Array.isArray(v) ? <ul className="list-disc pl-4">{v.map((x, i) => <li key={i}>{txt(x)}</li>)}</ul> : txt(v)}</dd>
    </div>
  );
}

function AgentBubble({ m, onWhy }: { m: SimMessage; onWhy: (m: SimMessage) => void }) {
  const [open, setOpen] = useState(false);
  const c = m.content ?? {};
  const color = PLAYER_COLORS[m.slug];
  const play = c.play && typeof c.play === "object" && !Array.isArray(c.play) ? c.play : null;
  const evals: any[] = Array.isArray(c.evaluations) ? c.evaluations.filter((e: any) => e && typeof e === "object") : [];
  const backs = slugFor(txt(c.backs || c.voted_for_proposal_of));
  return (
    <li className="flex items-start gap-3">
      <Avatar slug={m.slug} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <span className="font-display text-lg font-bold" style={{ color }}>{SHORT[m.slug]} agent</span>
          {typeof c.confidence === "number" && <span className="tabular text-xs text-ink-soft">{c.confidence}% sure</span>}
        </div>
        <div className="mt-1 max-w-[68ch] rounded-2xl rounded-tl-sm border border-rule bg-sheet px-4 py-2.5 leading-relaxed">
          <p>{messageText(m)}</p>
          {m.round === 1 && play && (
            <p className="mt-2 rounded-md bg-board px-3 py-2 text-sm">
              <span className="font-semibold">{txt(play.play_name) || "Play"}.</span>{" "}
              {play.primary_option && <>First look: {txt(play.primary_option)}. </>}
              {play.secondary_option && <>Then: {txt(play.secondary_option)}.</>}
            </p>
          )}
          {m.round === 2 && evals.length > 0 && (
            <ul className="mt-2 flex flex-wrap gap-1.5 text-xs">
              {evals.map((e, i) => {
                const s = slugFor(txt(e.of_player));
                const verb = e.stance === "agree" ? "agrees with" : e.stance === "disagree" ? "disagrees with" : "partly agrees with";
                if (s === m.slug) return null;
                return (
                  <li key={i} title={txt(e.comment)} className="inline-flex items-center gap-1 rounded-full border border-rule bg-white py-0.5 pl-0.5 pr-2">
                    {s && <Avatar slug={s} size={18} />}
                    {verb} {s ? SHORT[s] : txt(e.of_player)}
                  </li>
                );
              })}
              {c.changed_position && <li className="rounded-full bg-board-2 px-2 py-0.5">changed its answer</li>}
            </ul>
          )}
          {m.round === 3 && backs && (
            <p className="mt-2 inline-flex items-center gap-1.5 rounded-full border border-rule bg-white py-0.5 pl-0.5 pr-2.5 text-xs">
              <Avatar slug={backs} size={18} /> backs {backs === m.slug ? "its own answer" : `the ${SHORT[backs]} agent`}
            </p>
          )}
        </div>
        <div className="mt-1 flex gap-3 text-xs">
          <button type="button" onClick={() => setOpen((x) => !x)} aria-expanded={open} className="text-ink-soft underline-offset-2 hover:underline">
            {open ? "Hide details" : "Details"}
          </button>
          <button type="button" onClick={() => onWhy(m)} className="text-marker underline-offset-2 hover:underline">
            Why did {SHORT[m.slug]} say this?
          </button>
        </div>
        {open && (
          <dl className="mt-2 max-w-[68ch] space-y-1.5 rounded-md border border-rule bg-white p-3 text-sm">
            <Detail k="Position" v={c.position || c.revised_position || c.final_answer} />
            <Detail k="Reasoning" v={c.reasoning || c.reason || c.tactical_reasoning} />
            {play && <Detail k="Own role" v={play.your_role} />}
            {evals.map((e, i) => <Detail key={i} k={`On ${SHORT[slugFor(txt(e.of_player)) ?? ""] ?? txt(e.of_player)}`} v={`${txt(e.stance)}: ${txt(e.comment)}`} />)}
            <Detail k="Risks" v={txtList(c.risks)} />
            <Detail k="Data cited" v={txtList(c.data_support)} />
            {c.parse_error && <Detail k="Raw reply" v={c.raw} />}
          </dl>
        )}
      </div>
    </li>
  );
}

function Typing({ waitingFor }: { waitingFor: string[] }) {
  return (
    <li className="flex items-center gap-3 text-sm text-ink-soft" aria-live="polite">
      <span className="flex -space-x-2">
        {waitingFor.map((s) => (
          <span key={s} className="rounded-full ring-2 ring-board"><Avatar slug={s} size={30} /></span>
        ))}
      </span>
      <span className="inline-flex items-center gap-1">
        <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
      </span>
      <span>thinking</span>
    </li>
  );
}

function CoachAnswer({ d, model }: { d: CoachDecisionT; model?: string }) {
  if (d.parse_error) {
    return <p className="text-sm">The coach&apos;s reply couldn&apos;t be read. Raw reply: <span className="text-ink-soft">{d.raw?.slice(0, 600)}</span></p>;
  }
  // Older debates stored the play at the top level.
  const play = (d.play && typeof d.play === "object" ? d.play : null) ?? (d.play_name ? { play_name: d.play_name, ball_handler: d.ball_handler, primary_option: d.primary_option,
    secondary_option: d.secondary_option, third_option: d.third_option, counter: d.counter, player_roles: d.player_roles,
    off_ball_actions: d.off_ball_actions } : null);
  const court = d.court && Array.isArray(d.court.play_sequence) && d.court.play_sequence.length > 0 ? d.court : null;
  return (
    <div className="space-y-5">
      <div>
        <h3 className="font-display text-3xl font-bold leading-tight sm:text-4xl">{txt(d.verdict) || txt(play?.play_name)}</h3>
        {d.answer && <p className="mt-2 max-w-[70ch] text-lg leading-relaxed">{txt(d.answer)}</p>}
      </div>
      {play && (
        <div className="rounded-md border border-rule bg-white p-4">
          <p className="text-sm text-ink-soft">The play{play.ball_handler ? `, ball in ${SHORT[slugFor(txt(play.ball_handler)) ?? ""] ?? txt(play.ball_handler)}'s hands` : ""}</p>
          <p className="font-display text-2xl font-bold">{txt(play.play_name)}</p>
          <dl className="mt-3 grid gap-x-8 gap-y-2 sm:grid-cols-2">
            {([["First look", play.primary_option], ["Second look", play.secondary_option], ["Third look", play.third_option], ["If they take it away", play.counter]] as const)
              .filter(([, v]) => v).map(([k, v]) => (
                <div key={k}><dt className="text-sm font-semibold text-ink-soft">{k}</dt><dd>{txt(v)}</dd></div>
              ))}
          </dl>
          {play.player_roles && typeof play.player_roles === "object" && (
            <ul className="mt-4 grid gap-2 sm:grid-cols-5">
              {Object.entries(play.player_roles).map(([n, r]) => {
                const s = slugFor(n);
                return (
                  <li key={n} className="flex items-start gap-2 text-sm">
                    {s && <Avatar slug={s} size={26} />}
                    <span className="leading-snug">{txt(r)}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
      {court && <Court startPositions={court.start_positions} ballStartsWith={court.ball_starts_with} sequence={court.play_sequence ?? []} />}
      <div className="grid gap-6 lg:grid-cols-2">
        <section>
          <h4 className="font-display text-xl font-semibold">Why this answer</h4>
          <p className="mt-1 max-w-[70ch] leading-relaxed">{txt(d.reasoning)}</p>
          {d.vote_summary && <p className="mt-2 text-sm text-ink-soft">{txt(d.vote_summary)}</p>}
          {Array.isArray(d.rejected_alternatives) && d.rejected_alternatives.length > 0 && (
            <ul className="mt-3 space-y-1.5 text-sm">
              {d.rejected_alternatives.map((r, i) => {
                const rr = (r && typeof r === "object" ? r : { proposal: r }) as Record<string, unknown>;
                const s = slugFor(txt(rr.proposed_by));
                return (
                  <li key={i} className="flex items-start gap-2">
                    {s ? <Avatar slug={s} size={20} /> : <span className="w-5" />}
                    <span><span className="text-ink-soft">Passed on</span> {txt(rr.proposal)}{rr.reason ? `: ${txt(rr.reason)}` : ""}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
        <section>
          <h4 className="font-display text-xl font-semibold">Career data behind it</h4>
          <ul className="mt-1 space-y-1.5 text-sm">
            {txtList(d.key_data_points).map((x, i) => (
              <li key={i} className="border-l-2 border-marker pl-2">{x.replace(/^\s*FACT\s*:\s*/i, "")}</li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-ink-soft">
            {typeof d.confidence === "number" && <>Coach confidence {d.confidence}%. </>}{model && <>Model: {model}.</>}
          </p>
        </section>
      </div>
    </div>
  );
}

/** One question and the council's full discussion of it. */
export default function ChatExchange({ sim, onWhy }: { sim: Simulation; onWhy: (m: SimMessage) => void }) {
  const status = sim.status;
  const running = status !== "complete" && status !== "failed";
  const current = status.startsWith("round") ? Number(status.slice(5)) : status === "coach" ? 4 : status === "queued" ? 1 : 0;
  const rounds = [1, 2, 3].filter((r) => sim.messages.some((m) => m.round === r) || (running && current === r));
  const extras = Object.entries(sim.scenario ?? {}).filter(([k, v]) => k !== "question" && k !== "lineup" && v != null && v !== "");

  return (
    <article className="space-y-6">
      {/* the fan's question */}
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-ink px-4 py-2.5 text-board">
          <p className="leading-relaxed">{sim.scenario?.question}</p>
          {extras.length > 0 && <p className="mt-1 text-xs text-board/70">{extras.map(([k, v]) => `${k.replace(/_/g, " ")}: ${txt(v)}`).join("; ")}</p>}
        </div>
      </div>

      {rounds.map((r) => {
        const msgs = sim.messages.filter((m) => m.round === r).sort((a, b) => ORDER.indexOf(a.slug) - ORDER.indexOf(b.slug));
        const waiting = ORDER.filter((s) => !msgs.some((m) => m.slug === s));
        return (
          <section key={r} aria-label={ROUND_TITLE[r]}>
            <div className="mb-3 flex items-center gap-3 text-xs text-ink-soft">
              <span className="h-px flex-1 bg-rule" />
              <span>{ROUND_TITLE[r]}</span>
              <span className="h-px flex-1 bg-rule" />
            </div>
            <ul className="space-y-4">
              {msgs.map((m) => <AgentBubble key={`${m.round}-${m.slug}`} m={m} onWhy={onWhy} />)}
              {running && current === r && waiting.length > 0 && <Typing waitingFor={waiting} />}
            </ul>
          </section>
        );
      })}

      {(sim.coach_decision || (running && current === 4)) && (
        <section aria-label="Coach's answer">
          <div className="mb-3 flex items-center gap-3 text-xs text-ink-soft">
            <span className="h-px flex-1 bg-rule" /><span>The coach decides</span><span className="h-px flex-1 bg-rule" />
          </div>
          <div className="flex items-start gap-3">
            <Avatar slug="coach" size={48} />
            <div className="min-w-0 flex-1 rounded-2xl rounded-tl-sm border-2 border-ink bg-sheet p-4 sm:p-5">
              <p className="font-display text-lg font-bold">Coach</p>
              {sim.coach_decision ? (
                <CoachAnswer d={sim.coach_decision.decision} model={sim.coach_decision.model} />
              ) : (
                <p className="mt-1 inline-flex items-center gap-1 text-ink-soft">
                  <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
                  <span className="ml-1">reading the whole discussion</span>
                </p>
              )}
            </div>
          </div>
        </section>
      )}

      {status === "failed" && (
        <p role="alert" className="rounded-md border border-marker-red/40 bg-sheet p-3 text-sm text-marker-red">
          The council stopped: {sim.error ?? "unknown error"}
        </p>
      )}
    </article>
  );
}
