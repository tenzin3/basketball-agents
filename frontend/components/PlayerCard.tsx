import Link from "next/link";
import type { PlayerCard as Card } from "@/lib/types";
import { PLAYER_COLORS, num } from "@/lib/format";

export default function PlayerCard({ p }: { p: Card }) {
  const color = PLAYER_COLORS[p.slug];
  return (
    <Link
      href={`/players/${p.slug}`}
      className="group flex flex-col rounded-md border border-rule bg-sheet p-4 transition-colors hover:border-ink"
      style={{ borderTop: `5px solid ${color}` }}
    >
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="font-display text-[1.7rem] font-bold leading-none">{p.name}</h2>
        <span className="font-display text-lg font-semibold text-ink-soft" title="Default lineup slot">
          {p.lineup_slot.split(" ")[0]}
        </span>
      </div>
      {p.data_available ? (
        <>
          <p className="mt-1 text-sm text-ink-soft">
            {p.position}, {p.career_years}
          </p>
          <dl className="tabular mt-4 grid grid-cols-4 gap-1 text-center">
            {[
              ["PTS", num(p.career_stats?.pts_per_g)],
              ["REB", num(p.career_stats?.trb_per_g)],
              ["AST", num(p.career_stats?.ast_per_g)],
              ["TS%", typeof p.career_stats?.ts_pct === "number" ? (p.career_stats.ts_pct * 100).toFixed(1) : "—"],
            ].map(([k, v]) => (
              <div key={k}>
                <dd className="font-display text-2xl font-semibold leading-none">{v}</dd>
                <dt className="mt-1 text-xs text-ink-soft">{k}</dt>
              </div>
            ))}
          </dl>
          {!!p.achievements?.length && (
            <ul className="mt-4 space-y-0.5 text-sm">
              {p.achievements.map((a) => (
                <li key={a.label} className="flex justify-between gap-2">
                  <span className="text-ink-soft">{a.label}</span>
                  <span className="tabular font-semibold">{a.count}</span>
                </li>
              ))}
            </ul>
          )}
          {!!p.archetypes?.length && (
            <ul className="mt-4 flex flex-wrap gap-1.5">
              {p.archetypes.map((a) => (
                <li key={a} className="rounded-full border border-rule px-2 py-0.5 text-xs" style={{ color }}>
                  {a}
                </li>
              ))}
            </ul>
          )}
        </>
      ) : (
        <p className="mt-3 text-sm text-ink-soft">
          No career data loaded yet. Run the data pipeline to build this agent.
        </p>
      )}
    </Link>
  );
}
