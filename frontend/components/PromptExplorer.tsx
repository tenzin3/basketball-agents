"use client";

import { Fragment, useEffect, useState } from "react";
import { API_URL, api } from "@/lib/api";
import { PLAYER_COLORS, SHORT } from "@/lib/format";
import type { PromptPlayer, PromptsResponse } from "@/lib/types";

type TabKey = "player_system" | "grounding_rules" | "round1" | "round2" | "round3" | "coach_system" | "coach_user";

const TABS: { key: TabKey; label: string; who: string; when: string }[] = [
  { key: "player_system", label: "Player system prompt", who: "Each of the five agents", when: "Sent with every round. This is where each agent's own career data goes." },
  { key: "grounding_rules", label: "Grounding rules", who: "Each of the five agents", when: "Inserted into the system prompt as {rules}. The coach gets a shorter version." },
  { key: "round1", label: "Round 1", who: "Each of the five agents", when: "First answers. Sent to all five at once; no agent sees another's answer." },
  { key: "round2", label: "Round 2", who: "Each of the five agents", when: "Debate. Every agent now gets all five Round 1 answers and replies to the group." },
  { key: "round3", label: "Round 3", who: "Each of the five agents", when: "Final word. Every agent gets Round 1 and Round 2, then commits and says whose case it backs." },
  { key: "coach_system", label: "Coach system prompt", who: "The coach (stronger model)", when: "Holds all five career summaries at once." },
  { key: "coach_user", label: "Coach task", who: "The coach (stronger model)", when: "All three rounds, plus the answer format. The play and court fields are only filled for questions about a play." },
];

/** What fills each {placeholder} in the templates. */
const FILLS: Record<string, string> = {
  name: "the player this agent represents (also used inside the grounding rules)",
  focus: "that agent's focus lenses (different for each player, listed below)",
  context: "that player's career context package: only its own data, never a teammate's",
  teammates: "the other four agents' names (no stats about them)",
  rules: "the grounding rules: identical for every agent apart from its own name",
  question: "your chat message, exactly as you typed it",
  lineup: "the five on the floor, in case the answer needs a play",
  proposals: "all five Round 1 answers, trimmed to the play, options, reasoning, data and risks",
  debate: "all five Round 2 answers",
  contexts: "all five players' career summaries (layer 1)",
  round1: "all five Round 1 answers",
  round2: "all five Round 2 answers",
  round3: "all five Round 3 votes",
  vocab: "the allowed court locations for the diagram",
};

/** Render a Python str.format template: highlight {placeholders}, show {{ }} as literal braces. */
function Template({ text }: { text: string }) {
  const parts = text.split(/(?<!\{)(\{[a-z_0-9]+\})(?!\})/g);
  return (
    <pre className="max-h-[28rem] overflow-auto whitespace-pre-wrap rounded-md border border-rule bg-white p-4 text-[13px] leading-relaxed">
      {parts.map((p, i) => {
        const m = p.match(/^\{([a-z_0-9]+)\}$/);
        if (m) {
          return (
            <mark key={i} title={FILLS[m[1]] ?? ""} className="rounded bg-marker/15 px-1 font-semibold text-marker">
              {p}
            </mark>
          );
        }
        return <Fragment key={i}>{p.replace(/\{\{/g, "{").replace(/\}\}/g, "}")}</Fragment>;
      })}
    </pre>
  );
}

function AgentCard({ p, open, onToggle }: { p: PromptPlayer; open: boolean; onToggle: () => void }) {
  const color = PLAYER_COLORS[p.slug];
  return (
    <li className="flex flex-col rounded-md border border-rule bg-sheet p-4" style={{ borderTop: `5px solid ${color}` }}>
      <h4 className="font-display text-2xl font-bold" style={{ color }}>{SHORT[p.slug]} agent</h4>
      <p className="text-xs text-ink-soft">{p.agent_name}, default slot {p.lineup_slot}</p>

      <h5 className="mt-3 text-sm font-semibold">Focus lenses</h5>
      <ul className="mt-1 flex flex-wrap gap-1">
        {p.focus_areas.map((f) => (
          <li key={f} className="rounded-full border border-rule px-2 py-0.5 text-xs">{f}</li>
        ))}
      </ul>

      {!p.data_available ? (
        <p className="mt-3 text-sm text-ink-soft">No career data loaded. Run the pipeline.</p>
      ) : (
        <>
          <h5 className="mt-3 text-sm font-semibold">What its own data supports</h5>
          <p className="text-sm">{p.archetypes?.length ? p.archetypes.join(", ") : "no archetypes supported"}</p>
          {!!p.strengths?.length && (
            <p className="mt-1 text-xs text-ink-soft">Strengths in the data: {p.strengths.join("; ")}</p>
          )}
          {!!p.limitations?.length && (
            <p className="mt-1 text-xs text-ink-soft">Limitations: {p.limitations.join("; ")}</p>
          )}
          <p className="mt-1 text-xs text-ink-soft">Peak seasons: {p.peak_seasons?.join(", ") || "none"}</p>
          {!!p.not_testable?.length && (
            <p className="mt-1 text-xs text-ink-soft">
              Told it can&apos;t claim (no data): {p.not_testable.join(", ")}
            </p>
          )}

          <h5 className="mt-3 text-sm font-semibold">Retrieved for the sample question</h5>
          <ul className="mt-1 space-y-0.5 text-xs">
            {(p.retrieved_for_sample ?? []).map((d) => (
              <li key={d.title} className="flex justify-between gap-2">
                <span>{d.title.replace(`${p.name} `, "")}</span>
                {typeof d.score === "number" && <span className="tabular text-ink-soft">{d.score.toFixed(2)}</span>}
              </li>
            ))}
            {!p.retrieved_for_sample?.length && <li className="text-ink-soft">nothing (no retrieval documents yet)</li>}
          </ul>
          <p className="mt-2 text-xs text-ink-soft">
            About {p.context_tokens_sent?.toLocaleString()} tokens of its own data per prompt
            {p.layers_sent?.some((l) => l.includes("omitted")) ? " (season tables trimmed to fit)" : ""}.
          </p>
          <button type="button" onClick={onToggle} aria-expanded={open} aria-controls="agent-context"
            className={`mt-3 self-start rounded border px-2.5 py-1 text-sm hover:border-ink ${open ? "border-ink bg-board-2" : "border-rule"}`}>
            {open ? "Hide its career summary" : "Read its career summary"}
          </button>
        </>
      )}
    </li>
  );
}

export default function PromptExplorer() {
  const [data, setData] = useState<PromptsResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState<TabKey>("player_system");
  const [openSlug, setOpenSlug] = useState<string | null>(null);

  useEffect(() => {
    api.prompts().then(setData).catch((e) => setErr(e.message ?? String(e)));
  }, []);

  if (err) {
    return (
      <p className="rounded-md border border-marker-red/40 bg-sheet p-4 text-sm">
        The prompts load from the API at {API_URL} ({err}). Start it with <code>make api</code> and reload.
      </p>
    );
  }
  if (!data) return <div className="h-64 animate-pulse rounded-md bg-board-2" />;

  const active = TABS.find((t) => t.key === tab)!;
  const used = Array.from(new Set(Array.from(data.templates[tab].matchAll(/(?<!\{)\{([a-z_0-9]+)\}(?!\})/g)).map((m) => m[1])));

  return (
    <div className="space-y-12">
      <section aria-labelledby="prompts">
        <h2 id="prompts" className="font-display text-3xl font-bold">The prompts, round by round</h2>
        <p className="mt-2 max-w-[75ch] leading-relaxed text-ink-soft">
          These are the exact templates the backend sends, loaded live from the API. Blue <mark className="rounded bg-marker/15 px-1 text-marker">{"{placeholders}"}</mark> are
          filled in at run time; hover one to see what goes there. Every agent replies with JSON in the format shown. The
          &quot;message&quot; field becomes its chat bubble; the rest feeds the details panel and &quot;Why did … say this?&quot;.
        </p>
        <div role="tablist" aria-label="Prompt" className="mt-4 flex flex-wrap gap-x-5 gap-y-2 border-b border-rule">
          {TABS.map((t) => (
            <button key={t.key} role="tab" type="button" aria-selected={tab === t.key} onClick={() => setTab(t.key)}
              className={`-mb-px border-b-[3px] pb-2 font-display text-lg font-semibold ${tab === t.key ? "border-marker text-ink" : "border-transparent text-ink-soft"}`}>
              {t.label}
            </button>
          ))}
        </div>
        <div className="mt-4 grid gap-5 lg:grid-cols-[1fr_18rem]">
          <Template text={data.templates[tab]} />
          <aside className="text-sm">
            <p><span className="font-semibold">Sent to:</span> {active.who}</p>
            <p className="mt-1 text-ink-soft">{active.when}</p>
            {!!used.length && (
              <>
                <h3 className="mt-4 font-semibold">Filled in with</h3>
                <dl className="mt-1 space-y-1.5">
                  {used.map((u) => (
                    <div key={u}>
                      <dt className="font-mono text-xs text-marker">{`{${u}}`}</dt>
                      <dd className="text-ink-soft">{FILLS[u] ?? "—"}</dd>
                    </div>
                  ))}
                </dl>
              </>
            )}
            <p className="mt-4 text-xs text-ink-soft">
              Models: players use {data.models.player_provider} ({data.models.player_model}); the coach uses{" "}
              {data.models.coach_provider} ({data.models.coach_model}).
            </p>
          </aside>
        </div>
      </section>

      <section aria-labelledby="differ">
        <h2 id="differ" className="font-display text-3xl font-bold">How the five agents differ</h2>
        <div className="mt-2 max-w-[75ch] space-y-2 leading-relaxed">
          <p>
            All five agents get the same templates and the same rules. Three things differ, and they come from the data,
            not from a persona:
          </p>
          <ol className="list-decimal space-y-1 pl-5">
            <li><span className="font-semibold">Its own career context.</span> The <code>{"{context}"}</code> slot holds only that player&apos;s stats, awards, shot profile, peak seasons and limitations. An agent never sees a teammate&apos;s numbers; it only learns their ideas in Round 2.</li>
            <li><span className="font-semibold">Its focus lenses.</span> Curry&apos;s agent is asked to look at spacing and gravity, Kobe&apos;s at shot creation and footwork, LeBron&apos;s at playmaking. These are angles to examine the situation from, and the prompt says they aren&apos;t a reason to pick itself.</li>
            <li><span className="font-semibold">What retrieval pulls from its data.</span> The same question pulls different detail for each player, because each one&apos;s documents hold different numbers and have different coverage.</li>
          </ol>
          <p className="text-sm text-ink-soft">
            Sample question for the retrieval below: &quot;{data.sample.question}&quot; (matched: {data.sample.intents.join(", ")}).
          </p>
        </div>
        <ul className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          {data.players.map((p) => (
            <AgentCard key={p.slug} p={p} open={openSlug === p.slug}
              onToggle={() => setOpenSlug((x) => (x === p.slug ? null : p.slug))} />
          ))}
        </ul>
        {(() => {
          const sel = data.players.find((p) => p.slug === openSlug);
          if (!sel) return null;
          return (
            <div id="agent-context" className="mt-4">
              <h3 className="font-display text-xl font-bold" style={{ color: PLAYER_COLORS[sel.slug] }}>
                What the {SHORT[sel.slug]} agent reads in {"{context}"}: career summary, layer 1 of 3
              </h3>
              <p className="mt-1 text-sm text-ink-soft">
                Generated from the database. Season tables (layer 2) and the retrieved detail listed above come after this.
              </p>
              <pre className="mt-2 max-h-[32rem] overflow-auto whitespace-pre-wrap rounded-md border border-rule bg-white p-4 text-[12.5px] leading-relaxed">
                {sel.layer1_text}
              </pre>
            </div>
          );
        })()}
      </section>
    </div>
  );
}
