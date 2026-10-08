import type { CareerResponse, PlayersResponse, Profile, PromptsResponse, Simulation, SiteConfig } from "./types";

/** Where the backend lives. Locally http://localhost:8000; on Vercel the same domain under /api (see next.config.mjs). */
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const CODE_KEY = "hoopcouncil.accessCode";

/** The optional access code the site owner set (HOOP_ACCESS_CODE), remembered in this browser. */
export function getAccessCode(): string {
  try {
    return localStorage.getItem(CODE_KEY) ?? "";
  } catch {
    return "";
  }
}
export function setAccessCode(code: string) {
  try {
    if (code) localStorage.setItem(CODE_KEY, code);
    else localStorage.removeItem(CODE_KEY);
  } catch {}
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const code = getAccessCode();
  const r = await fetch(`${API_URL}${path}`, {
    cache: "no-store",
    ...init,
    headers: {
      ...(init?.body ? { "content-type": "application/json" } : {}),
      ...(code ? { "x-access-code": code } : {}),
      ...init?.headers,
    },
  });
  if (!r.ok) {
    let detail = `${r.status} ${r.statusText}`;
    try {
      const j = await r.json();
      if (j?.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {}
    if (r.status === 504) detail = "The server took too long on this round. It will try again.";
    throw new ApiError(detail, r.status);
  }
  return r.json() as Promise<T>;
}

const get = <T,>(path: string) => request<T>(path);
const post = <T,>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  config: () => get<SiteConfig>("/config"),
  players: () => get<PlayersResponse>("/players"),
  profile: (slug: string) => get<Profile>(`/players/${slug}`),
  career: (slug: string) => get<CareerResponse>(`/players/${slug}/career`),
  simulation: (id: string) => get<Simulation>(`/simulations/${id}`),
  /** Step mode (hosted on Vercel): run the next round on the server and get the updated discussion back. */
  step: (id: string) => post<Simulation>(`/simulations/${id}/step`),
  prompts: (question?: string) =>
    get<PromptsResponse>(`/prompts${question ? `?question=${encodeURIComponent(question)}` : ""}`),
  startSimulation: (body: unknown) => post<{ id: string; status: string; run_mode?: string }>("/simulations", body),
};

export const isRunning = (s?: Simulation | null) => !!s && s.status !== "complete" && s.status !== "failed";

/** Move a discussion forward once: in step mode ask the server to run the next round, otherwise just re-read it.
 *  Returns the updated discussion and how long to wait before the next call. */
export async function advance(s: Simulation): Promise<{ sim: Simulation; wait: number }> {
  if (s.run_mode === "steps") {
    const next = await api.step(s.id);
    // ran_stage null = another tab or request is running this round; check back shortly
    return { sim: next, wait: next.ran_stage ? 100 : 2000 };
  }
  return { sim: await api.simulation(s.id), wait: 2500 };
}
