import type { Num } from "./types";

export const pct = (x: Num, d = 1) => (typeof x === "number" ? `${(x * 100).toFixed(d)}%` : "—");
export const num = (x: Num, d = 1) => (typeof x === "number" ? x.toFixed(d) : "—");
export const int = (x: Num) => (typeof x === "number" ? Math.round(x).toLocaleString() : "—");
export const signed = (x: Num, d = 1) => (typeof x === "number" ? `${x >= 0 ? "+" : ""}${x.toFixed(d)}` : "—");
export const height = (h: Num) => (typeof h === "number" ? `${Math.floor(h / 12)}′${h % 12}″` : "—");

/** Marker colours per player (used for court dots and huddle bubbles). */
export const PLAYER_COLORS: Record<string, string> = {
  curry: "var(--color-p-curry)",
  kobe: "var(--color-p-kobe)",
  jordan: "var(--color-p-jordan)",
  durant: "var(--color-p-durant)",
  lebron: "var(--color-p-lebron)",
};

export const NAME_TO_SLUG: Record<string, string> = {
  "Stephen Curry": "curry",
  "Kobe Bryant": "kobe",
  "Michael Jordan": "jordan",
  "Kevin Durant": "durant",
  "LeBron James": "lebron",
};

export const SHORT: Record<string, string> = {
  curry: "Curry",
  kobe: "Kobe",
  jordan: "Jordan",
  durant: "Durant",
  lebron: "LeBron",
};

export function slugFor(name?: string | null): string | undefined {
  if (!name) return undefined;
  if (NAME_TO_SLUG[name]) return NAME_TO_SLUG[name];
  const n = name.toLowerCase();
  return Object.keys(SHORT).find((s) => n.includes(s) || n.includes(SHORT[s].toLowerCase()));
}
