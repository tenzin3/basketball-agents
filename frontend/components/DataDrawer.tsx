"use client";

import { useEffect, useRef } from "react";
import type { SimMessage } from "@/lib/types";
import { PLAYER_COLORS, SHORT } from "@/lib/format";

export default function DataDrawer({ msg, onClose }: { msg: SimMessage | null; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (msg && !d.open) d.showModal();
    if (!msg && d.open) d.close();
  }, [msg]);

  const dc = msg?.data_considered ?? {};
  const support: string[] = Array.isArray(msg?.content?.data_support) ? msg!.content.data_support : [];
  const color = msg ? PLAYER_COLORS[msg.slug] : undefined;

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => { if (e.target === ref.current) onClose(); }}
      className="ml-auto mr-0 h-full max-h-none w-full max-w-md bg-sheet p-0 text-ink backdrop:bg-ink/30"
    >
      {msg && (
        <div className="flex h-full flex-col">
          <div className="flex items-start justify-between gap-4 border-b border-rule p-5" style={{ borderTop: `5px solid ${color}` }}>
            <div>
              <h2 className="font-display text-3xl font-bold">Why did the {SHORT[msg.slug]} agent say this?</h2>
              <p className="mt-1 text-sm text-ink-soft">Round {msg.round}. Data the agent was given, and what it cited.</p>
            </div>
            <button type="button" onClick={onClose} className="rounded border border-rule px-2 py-1 text-sm">Close</button>
          </div>
          <div className="flex-1 space-y-6 overflow-y-auto p-5 text-sm">
            {support.length > 0 && (
              <section>
                <h3 className="font-display text-xl font-semibold">Cited by the agent</h3>
                <ul className="mt-2 space-y-1.5">
                  {support.map((s, i) => {
                    const fact = /^\s*fact/i.test(s);
                    return (
                      <li key={i} className="border-l-2 pl-2" style={{ borderColor: fact ? color : "var(--color-rule)" }}>
                        <span className="text-xs text-ink-soft">{fact ? "Statistical fact" : "Basketball inference"}</span>
                        <br />{s.replace(/^\s*(FACT|INFERENCE)\s*:\s*/i, "")}
                      </li>
                    );
                  })}
                </ul>
              </section>
            )}
            {!!dc.retrieved_documents?.length && (
              <section>
                <h3 className="font-display text-xl font-semibold">Retrieved for this situation</h3>
                {!!dc.retrieval_intents?.length && (
                  <p className="mt-1 text-ink-soft">Matched: {dc.retrieval_intents.join(", ")}</p>
                )}
                <ul className="mt-2 space-y-1">
                  {dc.retrieved_documents.map((d) => (
                    <li key={d.title} className="flex justify-between gap-3">
                      <span>{d.title}</span>
                      {typeof d.score === "number" && <span className="tabular text-ink-soft">{d.score.toFixed(2)}</span>}
                    </li>
                  ))}
                </ul>
              </section>
            )}
            <section>
              <h3 className="font-display text-xl font-semibold">Career context sections</h3>
              <p className="mt-2 leading-relaxed">{(dc.sections ?? []).map((s) => s.toLowerCase()).join(", ") || "—"}</p>
              {!!dc.peak_seasons?.length && <p className="mt-2">Peak seasons in context: {dc.peak_seasons.join(", ")}</p>}
              {!!dc.layers?.length && <p className="mt-2 text-ink-soft">{dc.layers.join("; ")}{dc.approx_tokens ? `, about ${dc.approx_tokens.toLocaleString()} tokens` : ""}</p>}
            </section>
            {msg.model && <p className="text-xs text-ink-soft">Model: {msg.model}{msg.latency_ms ? `, ${(msg.latency_ms / 1000).toFixed(1)}s` : ""}</p>}
          </div>
        </div>
      )}
    </dialog>
  );
}
