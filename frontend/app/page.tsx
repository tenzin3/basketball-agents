"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import Avatar from "@/components/Avatar";
import ChatExchange from "@/components/ChatExchange";
import DataDrawer from "@/components/DataDrawer";
import { API_URL, advance, api, getAccessCode, isRunning, setAccessCode } from "@/lib/api";
import { FULL_NAME } from "@/lib/format";
import type { SimMessage, Simulation, SiteConfig } from "@/lib/types";

const STORAGE_KEY = "hoopcouncil.chat.v1";
const MODEL_LABELS: Record<string, string> = {
  openrouter: "OpenRouter", anthropic: "Anthropic", openai: "OpenAI", gemini: "Gemini", local: "Local model (Ollama)",
  mock: "Mock (offline test)",
};
const ORDER = ["curry", "kobe", "jordan", "durant", "lebron"];
const SUGGESTIONS = [
  "We're down 1 with 9 seconds left and they switch everything. Who takes the last shot?",
  "Who was the best playoff scorer of the five, and why?",
  "Against a team that blitzes every pick-and-roll, who should run the offense?",
  "If you had to guard prime Kobe for one possession, who takes the assignment?",
  "Which of the five would you build a team around for one season, and why?",
];

function loadIds(): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    return Array.isArray(v) ? v.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}
function saveIds(ids: string[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids.slice(-30)));
  } catch {}
}

export default function ChatPage() {
  const [ids, setIds] = useState<string[]>([]);
  const [sims, setSims] = useState<Record<string, Simulation>>({});
  const [text, setText] = useState("");
  const [provider, setProvider] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [why, setWhy] = useState<SimMessage | null>(null);
  const [site, setSite] = useState<SiteConfig | null>(null);
  const [code, setCode] = useState("");
  const [tick, setTick] = useState(0);
  const inFlight = useRef<Set<string>>(new Set());
  const bottom = useRef<HTMLDivElement>(null);
  const box = useRef<HTMLTextAreaElement>(null);

  // restore this browser's chat, and ask the server how it's set up (models, access code, run mode)
  useEffect(() => {
    setIds(loadIds());
    setCode(getAccessCode());
    api.config().then(setSite).catch(() => {});
  }, []);

  const refresh = useCallback(async (id: string) => {
    try {
      const s = await api.simulation(id);
      setSims((x) => ({ ...x, [id]: s }));
      return s;
    } catch {
      return null;
    }
  }, []);

  // load all, then poll the ones still running
  useEffect(() => {
    ids.forEach((id) => { if (!sims[id]) refresh(id); });
  }, [ids]); // eslint-disable-line react-hooks/exhaustive-deps

  // Keep running discussions moving. In step mode (hosted on Vercel) each call runs the next round on the server;
  // otherwise it just re-reads progress. One call per discussion at a time.
  useEffect(() => {
    for (const id of ids) {
      const s = sims[id];
      if (!isRunning(s) || inFlight.current.has(id)) continue;
      inFlight.current.add(id);
      (async () => {
        let wait = 2500;
        try {
          const r = await advance(s);
          wait = r.wait;
          setSims((x) => ({ ...x, [id]: r.sim }));
        } catch (e: any) {
          if (e?.status === 401) { setError(e.message); wait = 10000; }
        } finally {
          setTimeout(() => { inFlight.current.delete(id); setTick((t) => t + 1); }, wait);
        }
      })();
    }
  }, [ids, sims, tick]);

  // keep the newest message in view
  const lastCount = ids.length ? sims[ids[ids.length - 1]]?.messages.length ?? 0 : 0;
  const lastDone = ids.length ? !!sims[ids[ids.length - 1]]?.coach_decision : false;
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [ids.length, lastCount, lastDone]);

  async function ask(q?: string) {
    const question = (q ?? text).trim();
    if (!question || busy) return;
    setBusy(true);
    setError(null);
    try {
      setAccessCode(code.trim());
      const { id } = await api.startSimulation({ scenario: { question }, provider: provider || undefined });
      const next = [...ids, id];
      setIds(next);
      saveIds(next);
      setText("");
      refresh(id);
    } catch (e: any) {
      setError(e.message ?? String(e));
    } finally {
      setBusy(false);
      box.current?.focus();
    }
  }

  function clearChat() {
    setIds([]);
    setSims({});
    saveIds([]);
  }

  const anyRunning = ids.some((id) => isRunning(sims[id]));
  const providers = site?.providers ?? Object.keys(MODEL_LABELS);
  const needCode = !!site?.access_code_required;

  return (
    <div className="flex min-h-[calc(100vh-9rem)] flex-col">
      <section className="mb-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-5xl font-bold">Ask the council</h1>
            <p className="mt-1 max-w-2xl text-ink-soft">
              Ask any basketball question. Curry, Kobe, Jordan, Durant and LeBron each answer from their own career
              numbers, argue it out over three rounds, and the coach gives the final answer.
            </p>
          </div>
          {ids.length > 0 && (
            <button type="button" onClick={clearChat} className="text-sm text-ink-soft underline-offset-2 hover:underline">
              Clear chat
            </button>
          )}
        </div>
        <ul className="mt-5 flex flex-wrap gap-4">
          {ORDER.map((s) => (
            <li key={s}>
              <Link href={`/players/${s}`} className="group flex items-center gap-2 rounded-full pr-3 hover:bg-board-2">
                <Avatar slug={s} size={40} />
                <span className="font-display text-lg font-semibold group-hover:underline">{FULL_NAME[s]}</span>
              </Link>
            </li>
          ))}
          <li className="flex items-center gap-2 pr-3">
            <Avatar slug="coach" size={40} />
            <span className="font-display text-lg font-semibold">Coach</span>
          </li>
        </ul>
      </section>

      <div className="flex-1 space-y-12">
        {ids.length === 0 && (
          <div className="rounded-md border border-dashed border-rule p-6">
            <p className="font-display text-xl font-semibold">Try one of these, or ask your own</p>
            <ul className="mt-3 flex flex-col gap-2">
              {SUGGESTIONS.map((s) => (
                <li key={s}>
                  <button type="button" onClick={() => ask(s)} disabled={busy}
                    className="w-full rounded-lg border border-rule bg-sheet px-4 py-2.5 text-left hover:border-ink disabled:opacity-60">
                    {s}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {ids.map((id) =>
          sims[id] ? (
            <ChatExchange key={id} sim={sims[id]} onWhy={setWhy} />
          ) : (
            <p key={id} className="text-sm text-ink-soft">Loading…</p>
          ),
        )}
        <div ref={bottom} />
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); ask(); }}
        className="sticky bottom-0 mt-10 border-t border-rule bg-board/95 pb-4 pt-3 backdrop-blur"
      >
        {error && (
          <p role="alert" className="mb-2 text-sm text-marker-red">
            {/fetch|network/i.test(error)
              ? API_URL.startsWith("/") ? "Can't reach the server right now. Please try again in a moment." : `Can't reach the backend at ${API_URL}. Start it with make dev.`
              : error}
          </p>
        )}
        <div className="flex items-end gap-2">
          <label htmlFor="ask" className="sr-only">Your question</label>
          <textarea
            id="ask"
            ref={box}
            rows={1}
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              const el = e.target;
              el.style.height = "auto";
              el.style.height = `${Math.min(el.scrollHeight, 192)}px`;
            }}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(); } }}
            placeholder="Ask anything about basketball…"
            className="max-h-48 min-h-[3rem] flex-1 resize-none rounded-xl border border-rule bg-white px-4 py-3 text-base leading-snug"
          />
          <button type="submit" disabled={busy || !text.trim()}
            className="h-12 rounded-xl bg-marker px-5 font-display text-xl font-semibold text-white disabled:opacity-50">
            {busy ? "Sending…" : "Ask"}
          </button>
        </div>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-ink-soft">
          <label className="flex items-center gap-2">
            Model
            <select value={provider} onChange={(e) => setProvider(e.target.value)} className="rounded border border-rule bg-white px-2 py-1">
              <option value="">
                Default{site ? ` (${MODEL_LABELS[site.default_provider] ?? site.default_provider})` : ""}
              </option>
              {providers.filter((p) => p !== site?.default_provider).map((p) => (
                <option key={p} value={p}>{MODEL_LABELS[p] ?? p}</option>
              ))}
            </select>
          </label>
          {needCode && (
            <label className="flex items-center gap-2">
              Access code
              <input type="password" value={code} onChange={(e) => setCode(e.target.value)} autoComplete="off"
                className="w-28 rounded border border-rule bg-white px-2 py-1" />
            </label>
          )}
          <span>
            {anyRunning ? "The council is talking. A full discussion is 16 model calls." : "Enter to send, Shift+Enter for a new line."}
          </span>
        </div>
      </form>

      <DataDrawer msg={why} onClose={() => setWhy(null)} />
    </div>
  );
}
