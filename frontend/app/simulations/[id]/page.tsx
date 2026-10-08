"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import ChatExchange from "@/components/ChatExchange";
import DataDrawer from "@/components/DataDrawer";
import { api } from "@/lib/api";
import type { SimMessage, Simulation } from "@/lib/types";

/** A single council discussion on its own page (shareable link). */
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

  return (
    <div className="space-y-6">
      <Link href="/" className="text-sm text-marker underline-offset-2 hover:underline">Back to the chat</Link>
      {sim ? <ChatExchange sim={sim} onWhy={setWhy} /> : (
        <p className="text-ink-soft">{err ? `Couldn't load this discussion: ${err}` : "Loading…"}</p>
      )}
      <p className="text-sm text-ink-soft">
        AI simulation based on player statistics and career tendencies. Agents represent statistical profiles, not the real
        players, and their messages are not quotes.
      </p>
      <DataDrawer msg={why} onClose={() => setWhy(null)} />
    </div>
  );
}
