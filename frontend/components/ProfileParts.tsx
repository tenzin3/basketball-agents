import type { Archetype, PeakSeason, SeasonLine } from "@/lib/types";
import { num, pct, signed } from "@/lib/format";

/** Share of FGA by distance with FG% per zone (Basketball Reference shooting data). */
export function ShotZones({ sp, color }: { sp: Record<string, any>; color: string }) {
  const zones: [string, number | null, number | null][] = [
    ["At the rim (0–3 ft)", sp.rim_frequency, sp.rim_fg_pct],
    ["Short range (3–10 ft)", sp.short_midrange_frequency, null],
    ["Midrange (10 ft to the arc)", sp.midrange_frequency, sp.midrange_fg_pct],
    ["Three-pointers", sp.three_point_frequency, null],
  ];
  const any = zones.some(([, v]) => typeof v === "number");
  if (!any) return <p className="text-sm text-ink-soft">No shot-distance data stored for this player. {sp.coverage_note}</p>;
  return (
    <div>
      <ul className="space-y-2.5">
        {zones.map(([label, share, fg]) => (
          <li key={label}>
            <div className="flex justify-between text-sm">
              <span>{label}</span>
              <span className="tabular text-ink-soft">{pct(share)} of shots{typeof fg === "number" ? `, ${pct(fg)} made` : ""}</span>
            </div>
            <div className="mt-1 h-3 rounded-sm bg-board-2">
              <div className="h-3 rounded-sm" style={{ width: `${Math.min(100, (share ?? 0) * 100)}%`, background: color }} />
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-ink-soft">{sp.coverage_note}</p>
    </div>
  );
}

export function PeakChart({ scores, peaks, color }: { scores: PeakSeason[]; peaks: string[]; color: string }) {
  if (!scores?.length) return null;
  const w = 640, h = 170, pad = 22;
  const bw = Math.min(44, (w - pad * 2) / scores.length);
  return (
    <figure>
      <svg viewBox={`0 0 ${w} ${h + 34}`} className="w-full" role="img" aria-label="Peak score by season">
        {[0.25, 0.5, 0.75, 1].map((g) => (
          <g key={g}>
            <line x1={pad} x2={w - pad} y1={h - g * (h - 10)} y2={h - g * (h - 10)} stroke="var(--color-rule)" strokeDasharray="2 4" />
            <text x={0} y={h - g * (h - 10) + 4} fontSize={10} fill="var(--color-ink-soft)">{g.toFixed(2)}</text>
          </g>
        ))}
        {scores.map((s, i) => {
          const bh = s.peak_score * (h - 10);
          const isPeak = peaks.includes(s.season);
          return (
            <g key={s.season}>
              <title>{`${s.season}: ${s.peak_score.toFixed(3)}`}</title>
              <rect x={pad + i * bw + 2} y={h - bh} width={Math.max(2, bw - 4)} height={bh} rx={2}
                fill={isPeak ? color : "var(--color-rule)"} />
              {(i % Math.ceil(scores.length / 10) === 0 || isPeak) && (
                <text x={pad + i * bw + bw / 2} y={h + 14} fontSize={10} textAnchor="middle" fill="var(--color-ink-soft)">
                  {s.season.slice(2)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <figcaption className="text-xs text-ink-soft">Highlighted bars are the detected peak seasons.</figcaption>
    </figure>
  );
}

export function SeasonTable({ rows }: { rows: SeasonLine[] }) {
  return (
    <div className="overflow-x-auto rounded-md border border-rule bg-sheet">
      <table className="tabular w-full min-w-[760px] text-sm">
        <thead className="text-left text-ink-soft">
          <tr className="border-b border-rule">
            {["Season", "Team", "G", "MP", "PTS", "TRB", "AST", "STL", "BLK", "FG%", "3P%", "FT%", "TS%", "USG%", "BPM", "Peak"].map((h) => (
              <th key={h} className="px-2 py-2 font-semibold">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.season + (r.team ?? "")} className="border-b border-rule/60 last:border-0">
              <td className="px-2 py-1.5">
                {r.provenance?.source_url ? <a href={r.provenance.source_url} className="underline-offset-2 hover:underline" title={`Source: ${r.provenance.source}, retrieved ${r.provenance.retrieved_at}`}>{r.season}</a> : r.season}
              </td>
              <td className="px-2">{(r.teams ?? [r.team]).filter(Boolean).join("/")}</td>
              <td className="px-2">{r.per_game?.g ?? "—"}</td>
              <td className="px-2">{num(r.per_game?.mp_per_g)}</td>
              <td className="px-2 font-semibold">{num(r.per_game?.pts_per_g)}</td>
              <td className="px-2">{num(r.per_game?.trb_per_g)}</td>
              <td className="px-2">{num(r.per_game?.ast_per_g)}</td>
              <td className="px-2">{num(r.per_game?.stl_per_g)}</td>
              <td className="px-2">{num(r.per_game?.blk_per_g)}</td>
              <td className="px-2">{pct(r.per_game?.fg_pct)}</td>
              <td className="px-2">{pct(r.per_game?.fg3_pct)}</td>
              <td className="px-2">{pct(r.per_game?.ft_pct)}</td>
              <td className="px-2">{pct(r.advanced?.ts_pct)}</td>
              <td className="px-2">{pct(r.advanced?.usg_pct)}</td>
              <td className="px-2">{signed(r.advanced?.bpm)}</td>
              <td className="px-2">{typeof r.peak_score === "number" ? r.peak_score.toFixed(2) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const STATUS_LABEL: Record<Archetype["status"], string> = {
  supported: "Supported by the data",
  not_supported: "Not supported",
  insufficient_data: "Not testable with stored data",
};

export function ArchetypeList({ items, color }: { items: Archetype[]; color: string }) {
  const groups: Archetype["status"][] = ["supported", "not_supported", "insufficient_data"];
  return (
    <div className="space-y-5">
      {groups.map((g) => {
        const xs = items.filter((a) => a.status === g);
        if (!xs.length) return null;
        return (
          <div key={g}>
            <h4 className="font-display text-lg font-semibold">{STATUS_LABEL[g]}</h4>
            <ul className="mt-1.5 space-y-1.5 text-sm">
              {xs.map((a) => (
                <li key={a.archetype} className={g === "supported" ? "" : "text-ink-soft"}>
                  <details>
                    <summary className="cursor-pointer">
                      <span style={g === "supported" ? { color, fontWeight: 700 } : undefined}>{a.archetype}</span>
                      {g !== "insufficient_data" && <span className="ml-2">{a.evidence[0]}</span>}
                    </summary>
                    <div className="mt-1 pl-4">
                      <p>Rule: {a.rule}</p>
                      <ul className="list-disc pl-4">{a.evidence.map((e, i) => <li key={i}>{e}</li>)}</ul>
                    </div>
                  </details>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
