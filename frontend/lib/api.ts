import type { CareerResponse, PlayersResponse, Profile, PromptsResponse, Simulation } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!r.ok) {
    let detail = `${r.status} ${r.statusText}`;
    try {
      const j = await r.json();
      if (j?.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {}
    throw new Error(detail);
  }
  return r.json() as Promise<T>;
}

export const api = {
  players: () => get<PlayersResponse>("/players"),
  profile: (slug: string) => get<Profile>(`/players/${slug}`),
  career: (slug: string) => get<CareerResponse>(`/players/${slug}/career`),
  simulation: (id: string) => get<Simulation>(`/simulations/${id}`),
  prompts: (question?: string) =>
    get<PromptsResponse>(`/prompts${question ? `?question=${encodeURIComponent(question)}` : ""}`),
  async startSimulation(body: unknown): Promise<{ id: string; status: string }> {
    const r = await fetch(`${API_URL}/simulations`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof j?.detail === "string" ? j.detail : `Request failed (${r.status})`);
    return j;
  },
};
