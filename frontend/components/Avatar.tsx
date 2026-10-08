import { PLAYER_COLORS, SHORT } from "@/lib/format";

const INITIALS: Record<string, string> = { curry: "SC", kobe: "KB", jordan: "MJ", durant: "KD", lebron: "LJ" };

/** Monogram avatar for an agent (no likenesses: initials on the agent's marker colour). */
export default function Avatar({ slug, size = 44, ring = false, title }: {
  slug: string | "coach"; size?: number; ring?: boolean; title?: string;
}) {
  const isCoach = slug === "coach";
  const bg = isCoach ? "var(--color-ink)" : PLAYER_COLORS[slug] ?? "var(--color-ink-soft)";
  const label = isCoach ? "Coach" : `${SHORT[slug] ?? slug} agent`;
  return (
    <span
      role="img"
      aria-label={title ?? label}
      title={title ?? label}
      className="relative inline-flex shrink-0 select-none items-center justify-center rounded-full font-display font-bold text-white"
      style={{
        width: size, height: size, background: bg, fontSize: size * 0.4, letterSpacing: "0.02em",
        boxShadow: ring ? `0 0 0 3px var(--color-board), 0 0 0 5px ${bg}` : "inset 0 -3px 0 rgba(0,0,0,0.15)",
      }}
    >
      {isCoach ? (
        // whistle mark
        <svg viewBox="0 0 24 24" width={size * 0.55} height={size * 0.55} aria-hidden fill="none" stroke="#fff" strokeWidth={2}
          strokeLinecap="round" strokeLinejoin="round">
          <circle cx="9" cy="14" r="5" />
          <path d="M13 10h8v3h-6M9 9V5M6 6l1.5 2" />
        </svg>
      ) : (
        INITIALS[slug] ?? slug.slice(0, 2).toUpperCase()
      )}
    </span>
  );
}
