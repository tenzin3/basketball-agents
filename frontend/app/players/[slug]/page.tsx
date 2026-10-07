"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArchetypeList, PeakChart, SeasonTable, ShotZones } from "@/components/ProfileParts";
import { api } from "@/lib/api";
import { PLAYER_COLORS, height, int, num, pct, signed } from "@/lib/format";
import type { CareerResponse, Profile, Summary } from "@/lib/types";

function SummaryRow({ title, s }: { title: string; s?: Summary }) {
  if (!s?.totals) return null;
  const pg = s.per_game ?? {}, sh = s.shooting ?? {}, adv = s.advanced ?? {};
  const cells: [string, string][] = [
    ["Games", int(s.totals.g)], ["PTS", num(pg.pts_per_g)], ["TRB", num(pg.trb_per_g)], ["AST", num(pg.ast_per_g)],
    ["STL", num(pg.stl_per_g)], ["BLK", num(pg.blk_per_g)], ["FG%", pct(sh.fg_pct)], ["3P%", pct(sh.fg3_pct)],
    ["FT%", pct(sh.ft_pct)], ["TS%", pct(sh.ts_pct)], ["USG%", pct(adv.usg_pct)], ["BPM", signed(adv.bpm)],
  ];
  return (
    <div>
      <h3 className="font-display text-xl font-semibold">{title}</h3>
      <dl className="tabular mt-2 grid grid-cols-4 gap-x-4 gap-y-3 sm:grid-cols-6 lg:grid-cols-12">
        {cells.map(([k, v]) => (
          <div key={k}>
            <dd className="font-display text-2xl font-semibold leading-none">{v}</dd>
            <dt className="mt-1 text-xs text-ink-soft">{k}</dt>
          </div>
        ))}
      </dl>
    </div>
  );
}

export default function PlayerPage() {
  const { slug } = useParams<{ slug: string }>();
  const [p, setP] = useState<Profile | null>(null);
  const [career, setCareer] = useState<CareerResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState<"regular" | "playoffs">("regular");

  useEffect(() => {
    api.profile(slug).then(setP).catch((e) => setErr(e.message));
    api.career(slug).then(setCareer).catch(() => {});
  }, [slug]);

  if (err) return <p>{err}. <Link className="text-marker underline" href="/">Back to the lineup</Link></p>;
  if (!p) return <p className="text-ink-soft">Loading profile…</p>;
  const color = PLAYER_COLORS[slug] ?? "var(--color-marker)";
  const i = p.identity;
  const fin = p.finals_summary?.nba_finals;

  return (
    <article className="space-y-12">
      <header className="border-l-[6px] pl-4" style={{ borderColor: color }}>
        <Link href="/" className="text-sm text-marker underline-offset-2 hover:underline">The starting five</Link>
        <h1 className="mt-1 font-display text-6xl font-bold">{i.full_name}</h1>
        <p className="mt-2 text-ink-soft">
          {i.primary_position}{i.secondary_positions?.length ? ` (also ${i.secondary_positions.join(", ")})` : ""}, {height(i.height_in)}, {i.weight_lb ?? "—"} lb.
          {" "}Seasons {i.first_season} to {i.last_season} ({i.seasons_played}). Teams: {(i.teams ?? []).join(", ")}.
          {i.draft_year ? ` Drafted ${i.draft_year}, pick ${i.draft_pick}.` : ""}
          {i.hall_of_fame_inducted ? ` Hall of Fame ${i.hall_of_fame_inducted}.` : ""}
        </p>
      </header>

      <section className="space-y-6">
        <h2 className="font-display text-3xl font-bold">Statistics</h2>
        <SummaryRow title="Regular season" s={p.career_summary.regular_season} />
        <SummaryRow title="Playoffs" s={p.playoff_summary} />
        {fin && (
          <p className="text-sm">
            NBA Finals, from game logs: {fin.games} games ({fin.wins}-{fin.losses}), {num(fin.per_game?.pts_per_g)} PTS,{" "}
            {num(fin.per_game?.trb_per_g)} TRB, {num(fin.per_game?.ast_per_g)} AST, TS {pct(fin.shooting?.ts_pct)}.
          </p>
        )}
        {career && (
          <div>
            <div role="tablist" className="mb-2 flex gap-4">
              {(["regular", "playoffs"] as const).map((t) => (
                <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)} type="button"
                  className={`border-b-[3px] pb-1 font-display text-lg font-semibold ${tab === t ? "border-marker" : "border-transparent text-ink-soft"}`}>
                  {t === "regular" ? "Season by season" : "Playoffs by year"}
                </button>
              ))}
            </div>
            <SeasonTable rows={tab === "regular" ? career.regular_season : career.playoffs} />
          </div>
        )}
      </section>

      <section className="grid gap-10 lg:grid-cols-2">
        <div>
          <h2 className="font-display text-3xl font-bold">Achievements</h2>
          <ul className="mt-3 space-y-2">
            {p.achievements.map((a) => (
              <li key={a.achievement_type} className="grid grid-cols-[3rem_1fr] gap-2">
                <span className="tabular text-right font-display text-2xl font-semibold leading-none">{a.count}</span>
                <span>
                  {a.label}
                  {!!a.seasons.length && a.achievement_type !== "ALL_STAR" && (
                    <span className="block text-xs text-ink-soft">{a.seasons.join(", ")}</span>
                  )}
                </span>
              </li>
            ))}
            {!p.achievements.length && <li className="text-ink-soft">No award records stored.</li>}
          </ul>
        </div>
        <div>
          <h2 className="font-display text-3xl font-bold">Scoring zones</h2>
          <div className="mt-3"><ShotZones sp={p.shot_profile_summary} color={color} /></div>
          <h3 className="mt-8 font-display text-xl font-semibold">Play types</h3>
          {Object.keys(p.play_type_tendencies ?? {}).length ? (
            <ul className="mt-2 space-y-1 text-sm">
              {Object.entries(p.play_type_tendencies).sort((a, b) => b[1].frequency - a[1].frequency).map(([k, v]) => (
                <li key={k} className="flex justify-between"><span>{k}</span><span className="tabular text-ink-soft">{pct(v.frequency)} of possessions, {num(v.ppp, 2)} pts per play</span></li>
              ))}
            </ul>
          ) : <p className="mt-1 text-sm text-ink-soft">No play-type data stored (Synergy data starts in 2015-16 and is an optional source).</p>}
        </div>
      </section>

      <section>
        <h2 className="font-display text-3xl font-bold">Peak seasons</h2>
        <p className="mt-1 max-w-[75ch] text-sm text-ink-soft">{p.peak_formula}</p>
        <div className="mt-4"><PeakChart scores={career?.peak_scores ?? p.peak_seasons} peaks={p.peak_seasons.map((x) => x.season)} color={color} /></div>
        <ul className="mt-3 flex flex-wrap gap-3 text-sm">
          {p.peak_seasons.map((s) => (
            <li key={s.season} className="rounded border border-rule bg-sheet px-3 py-1.5">
              <span className="font-display text-xl font-semibold">{s.season}</span> <span className="tabular text-ink-soft">{s.peak_score.toFixed(3)}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="grid gap-10 lg:grid-cols-2">
        <div>
          <h2 className="font-display text-3xl font-bold">Play style</h2>
          <div className="mt-3"><ArchetypeList items={p.archetypes} color={color} /></div>
        </div>
        <div>
          <h2 className="font-display text-3xl font-bold">Career phases</h2>
          <ol className="mt-3 space-y-2 text-sm">
            {p.career_phases.map((ph) => (
              <li key={ph.phase_type + ph.name + ph.start_season} className="grid grid-cols-[7rem_1fr] gap-2">
                <span className="tabular text-ink-soft">{ph.start_season.slice(0, 4)}–{ph.end_season.slice(5)}</span>
                <span>
                  <span className="font-semibold">{ph.name}</span>{ph.phase_type === "statistical" ? " (by peak score)" : ""}:{" "}
                  {num(ph.summary?.per_game?.pts_per_g)} PTS, {num(ph.summary?.per_game?.ast_per_g)} AST, TS {pct(ph.summary?.shooting?.ts_pct)}
                </span>
              </li>
            ))}
          </ol>
          <h3 className="mt-8 font-display text-xl font-semibold">Strengths in the data</h3>
          <ul className="mt-1 list-disc pl-5 text-sm">{p.strengths.map((s) => <li key={s.label}>{s.label}: {s.evidence}</li>)}</ul>
          <h3 className="mt-5 font-display text-xl font-semibold">Limitations in the data</h3>
          <ul className="mt-1 list-disc pl-5 text-sm">
            {p.limitations.map((s) => <li key={s.label}>{s.label}: {s.evidence}</li>)}
            {!p.limitations.length && <li className="list-none text-ink-soft">None flagged by the rules.</li>}
          </ul>
        </div>
      </section>

      <section>
        <h2 className="font-display text-2xl font-bold">What the data can&apos;t tell us</h2>
        <ul className="mt-2 list-disc pl-5 text-sm text-ink-soft">{p.data_limitations.map((x) => <li key={x}>{x}</li>)}</ul>
      </section>
    </article>
  );
}
