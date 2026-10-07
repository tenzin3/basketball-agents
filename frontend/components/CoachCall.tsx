import type { CoachDecisionT } from "@/lib/types";
import { PLAYER_COLORS, SHORT, slugFor } from "@/lib/format";
import Court from "./Court";

function Name({ n }: { n?: string | null }) {
  const s = slugFor(n);
  return <span className="font-semibold" style={{ color: s ? PLAYER_COLORS[s] : undefined }}>{s ? SHORT[s] : n}</span>;
}

export default function CoachCall({ d, model }: { d: CoachDecisionT; model?: string }) {
  if (d.parse_error) {
    return (
      <div className="rounded-md border border-marker-red/50 bg-sheet p-5">
        <p>The coach&apos;s reply could not be read as JSON. Raw reply:</p>
        <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap text-xs">{d.raw}</pre>
      </div>
    );
  }
  const rows: [string, string | undefined][] = [
    ["Primary", d.primary_option],
    ["Secondary", d.secondary_option],
    ["Third", d.third_option],
    ["Counter", d.counter],
  ];
  return (
    <div className="space-y-6">
      <div className="rounded-md border-2 border-ink bg-sheet p-5 sm:p-7">
        <p className="text-sm text-ink-soft">
          Play{d.ball_handler && <>, ball in <Name n={d.ball_handler} />&apos;s hands</>}
          {d.inbounder && <>, <Name n={d.inbounder} /> inbounds</>}
        </p>
        <h3 className="mt-1 font-display text-4xl font-bold sm:text-5xl">{d.play_name}</h3>
        <dl className="mt-5 grid gap-x-8 gap-y-3 sm:grid-cols-2">
          {rows.filter(([, v]) => v).map(([k, v]) => (
            <div key={k}>
              <dt className="font-display text-lg font-semibold text-ink-soft">{k}</dt>
              <dd className="text-lg leading-snug">{v}</dd>
            </div>
          ))}
        </dl>
        {!!d.off_ball_actions?.length && (
          <div className="mt-5">
            <h4 className="font-display text-lg font-semibold text-ink-soft">Off the ball</h4>
            <ul className="mt-1 list-disc pl-5">{d.off_ball_actions.map((x, i) => <li key={i}>{x}</li>)}</ul>
          </div>
        )}
        {d.player_roles && (
          <ul className="mt-5 grid gap-2 sm:grid-cols-5">
            {Object.entries(d.player_roles).map(([n, r]) => (
              <li key={n} className="rounded border border-rule p-2 text-sm">
                <Name n={n} />
                <p className="mt-0.5 leading-snug">{r}</p>
              </li>
            ))}
          </ul>
        )}
      </div>

      {d.court && <Court startPositions={d.court.start_positions} ballStartsWith={d.court.ball_starts_with} sequence={d.court.play_sequence ?? []} />}

      <div className="grid gap-6 lg:grid-cols-2">
        <section>
          <h4 className="font-display text-2xl font-semibold">Why this won</h4>
          <p className="mt-2 max-w-[70ch] leading-relaxed">{d.reasoning}</p>
          {d.vote_summary && <p className="mt-3 text-sm text-ink-soft">{d.vote_summary}</p>}
          {!!d.rejected_alternatives?.length && (
            <>
              <h5 className="mt-5 font-display text-xl font-semibold">Passed on</h5>
              <ul className="mt-2 space-y-2 text-sm">
                {d.rejected_alternatives.map((r, i) => (
                  <li key={i}>
                    <span className="font-semibold">{r.proposal}</span>
                    {r.proposed_by && <> (<Name n={r.proposed_by} />)</>}: {r.reason}
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
        <section>
          <h4 className="font-display text-2xl font-semibold">Career data considered</h4>
          <ul className="mt-2 space-y-1.5 text-sm">
            {(d.key_data_points ?? []).map((x, i) => (
              <li key={i} className="border-l-2 border-marker pl-2">{x.replace(/^\s*FACT\s*:\s*/i, "")}</li>
            ))}
          </ul>
          {!!d.career_data_considered?.length && (
            <p className="mt-3 text-sm text-ink-soft">Categories: {d.career_data_considered.join(", ")}</p>
          )}
          <p className="mt-3 text-sm text-ink-soft">
            {typeof d.confidence === "number" && <>Coach confidence {d.confidence}. </>}
            {model && <>Model: {model}.</>}
          </p>
        </section>
      </div>
    </div>
  );
}
