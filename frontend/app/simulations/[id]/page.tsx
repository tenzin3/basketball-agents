"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import CoachCall from "@/components/CoachCall";
import DataDrawer from "@/components/DataDrawer";
import HuddleFeed from "@/components/HuddleFeed";
import { api } from "@/lib/api";
import type { SimMessage, Simulation } from "@/lib/types";

const STATUS: Record<string, string> = {
  queued: "Waiting to start",
  round1: "Round 1: agents are analysing independently",
  round2: "Round 2: agents are debating",
  round3: "Round 3: agents are voting",
  coach: "The coach is making the call",
  complete: "Final call made",
  failed: "The simulation stopped",
};

function scenarioLine(s: Record<string, any>) {
  const parts: string[] = [];
  if (typeof s.score_margin === "number") parts.push(s.score_margin === 0 ? "Tied" : s.score_margin < 0 ? `Down ${-s.score_margin}` : `Up ${s.score_margin}`);
  if (s.game_clock != null) parts.push(`${s.game_clock}s left in Q${s.quarter ?? 4}`);
  if (s.shot_clock != null) parts.push(`${s.shot_clock}s on the shot clock`);
  if (s.timeouts != null) parts.push(`${s.timeouts} timeout${s.timeouts === 1 ? "" : "s"}`);
  if (s.defensive_scheme) parts.push(`defense: ${s.defensive_scheme}`);
  return parts.join(", ");
}

export default function SimulationPage() {
  const { id } = useParams<{ id: string }>();
  const [sim, setSim] = useState<Simulation | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [why, setWhy] = useState<SimMessage | null>(null);

  useEffect(() => {
    let stop = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const s = await api.simulation(id);
        if (stop) return;
        setSim(s);
        setErr(null);
        if (s.status !== "complete" && s.status !== "failed") timer = setTimeout(poll, 1500);
      } catch (e: any) {
        if (!stop) { setErr(e.message ?? String(e)); timer = setTimeout(poll, 3000); }
      }
    };
    poll();
    return () => { stop = true; clearTimeout(timer); };
  }, [id]);

  if (!sim) return <p className="text-ink-soft">{err ? `Couldn't load the simulation: ${err}` : "Loading the huddle…"}</p>;

  const currentRound = sim.status.startsWith("round") ? Number(sim.status.slice(5)) : sim.status === "coach" ? 4 : 0;
  const done = sim.status === "complete";

  return (
    <div className="space-y-10">
      <section>
        <Link href="/" className="text-sm text-marker underline-offset-2 hover:underline">New situation</Link>
        <h1 className="mt-2 max-w-4xl font-display text-4xl font-bold sm:text-5xl">{sim.scenario.question}</h1>
        <p className="mt-2 text-ink-soft">{scenarioLine(sim.scenario)}</p>
        <p className={`mt-3 inline-block rounded px-2 py-1 text-sm ${sim.status === "failed" ? "bg-marker-red/10 text-marker-red" : "bg-board-2"}`} aria-live="polite">
          {STATUS[sim.status] ?? sim.status}
          {sim.error ? `: ${sim.error}` : ""}
        </p>
      </section>

      <section aria-labelledby="huddle">
        <h2 id="huddle" className="mb-3 font-display text-3xl font-bold">The huddle</h2>
        <HuddleFeed messages={sim.messages} onWhy={setWhy} currentRound={currentRound} />
      </section>

      <section aria-labelledby="coach">
        <h2 id="coach" className="mb-3 font-display text-3xl font-bold">Coach&apos;s call</h2>
        {sim.coach_decision ? (
          <CoachCall d={sim.coach_decision.decision} model={sim.coach_decision.model} />
        ) : (
          <p className="text-ink-soft">{done ? "No decision was recorded." : "The coach decides after the final votes."}</p>
        )}
      </section>

      <p className="text-sm text-ink-soft">
        AI simulation based on player statistics and career tendencies. Agents represent statistical profiles, not the real
        players, and their lines are not quotes.
      </p>
      <DataDrawer msg={why} onClose={() => setWhy(null)} />
    </div>
  );
}
