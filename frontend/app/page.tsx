"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import PlayerCard from "@/components/PlayerCard";
import ScenarioForm, { type ScenarioState } from "@/components/ScenarioForm";
import { API_URL, api } from "@/lib/api";
import type { PlayersResponse } from "@/lib/types";

export default function Home() {
  const router = useRouter();
  const [data, setData] = useState<PlayersResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    api.players().then(setData).catch((e) => setLoadError(String(e.message ?? e)));
  }, []);

  async function start(s: ScenarioState, provider: string) {
    setBusy(true);
    setSubmitError(null);
    try {
      const { id } = await api.startSimulation({ scenario: s, provider: provider || undefined });
      router.push(`/simulations/${id}`);
    } catch (e: any) {
      setSubmitError(e.message ?? String(e));
      setBusy(false);
    }
  }

  return (
    <div className="space-y-12">
      <section>
        <h1 className="max-w-3xl font-display text-5xl font-bold sm:text-6xl">
          Five careers in one huddle. One coach makes the call.
        </h1>
        <p className="mt-3 max-w-2xl text-ink-soft">
          Each agent reasons from its player&apos;s stored career data: season stats, playoffs, awards, shot profile and
          peak seasons. They propose, argue, vote, and a separate coach agent picks the play.
        </p>
      </section>

      <section aria-labelledby="lineup">
        <h2 id="lineup" className="mb-3 font-display text-2xl font-semibold">The starting five</h2>
        {loadError && (
          <p className="rounded-md border border-marker-red/40 bg-sheet p-4 text-sm">
            Can&apos;t reach the API at {API_URL} ({loadError}). Start it with <code>make api</code>, then reload.
          </p>
        )}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {(data?.players ?? []).map((p) => <PlayerCard key={p.slug} p={p} />)}
          {!data && !loadError &&
            Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-64 animate-pulse rounded-md bg-board-2" />)}
        </div>
      </section>

      <section aria-labelledby="scenario">
        <h2 id="scenario" className="mb-3 font-display text-2xl font-semibold">Set the situation</h2>
        <ScenarioForm onSubmit={start} busy={busy} error={submitError} />
      </section>
    </div>
  );
}
