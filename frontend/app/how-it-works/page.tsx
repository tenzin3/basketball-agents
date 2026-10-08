import type { Metadata } from "next";
import Link from "next/link";
import { FlowDiagramStacked, FlowDiagramWide } from "@/components/FlowDiagram";

export const metadata: Metadata = {
  title: "How it works · HoopCouncil",
  description: "How HoopCouncil turns career statistics into five debating agents and a coach's call.",
};

const ROUNDS = [
  {
    n: "Round 1",
    name: "Propose",
    body: "All five agents get the situation at the same time and answer independently. None of them can see the others. Each returns a play, a primary and secondary option, its own role, the risks, a confidence score, and the stats it relied on.",
  },
  {
    n: "Round 2",
    name: "Debate",
    body: "Every agent now sees all five proposals. It points out spacing problems, matchup advantages and how the defense would react, agrees or disagrees with each teammate, and may change its own plan. Disagreement isn't forced.",
  },
  {
    n: "Round 3",
    name: "Vote",
    body: "Each agent submits a final recommendation, says whose proposal it backs, and gives its reasons.",
  },
  {
    n: "Coach",
    name: "Make the call",
    body: "A separate agent on a stronger model reads all three rounds plus all five career summaries. It judges shot quality, spacing, clock, turnover risk and counters rather than counting votes, then returns the play, every player's role, why it won, which alternatives it rejected, and step-by-step instructions that the court diagram animates.",
  },
];

export default function HowItWorks() {
  return (
    <article className="space-y-14">
      <header className="max-w-3xl">
        <Link href="/" className="text-sm text-marker underline-offset-2 hover:underline">Back to the huddle</Link>
        <h1 className="mt-2 font-display text-5xl font-bold sm:text-6xl">How HoopCouncil works</h1>
        <p className="mt-3 text-lg text-ink-soft">
          It isn&apos;t one AI pretending to be five legends. Each agent reasons only from its own player&apos;s stored
          career data, they argue it out, and a coach agent decides.
        </p>
      </header>

      <section aria-labelledby="flow">
        <h2 id="flow" className="sr-only">The full flow</h2>
        <div className="hidden rounded-md border border-rule bg-board p-3 md:block">
          <FlowDiagramWide />
        </div>
        <div className="md:hidden">
          <FlowDiagramStacked />
        </div>
      </section>

      <section className="grid gap-10 lg:grid-cols-2">
        <div>
          <h2 className="font-display text-3xl font-bold">Where the facts come from</h2>
          <div className="mt-3 max-w-[65ch] space-y-3 leading-relaxed">
            <p>
              A scraper collects every season, playoff run, award and shot-distance profile for the five players from
              Basketball Reference. NBA.com clutch splits and play types are an optional extra. Requests are rate
              limited and every page is cached, so the data is gathered once.
            </p>
            <p>
              Before anything reaches an agent, it&apos;s checked. Career totals have to equal the sum of the seasons,
              award counts have to match the site&apos;s own summary, and percentages have to fall in valid ranges.
              Each player gets a data-quality report marking every category complete, partial or missing.
            </p>
            <p>
              Gaps stay gaps. If a stat doesn&apos;t exist for a season (shot zones before 1996-97, play types
              before 2015-16), the agent is told the data doesn&apos;t establish it. Nothing is filled in with an
              estimate.
            </p>
          </div>
        </div>
        <div>
          <h2 className="font-display text-3xl font-bold">What each agent knows</h2>
          <div className="mt-3 max-w-[65ch] space-y-3 leading-relaxed">
            <p>
              Each agent gets one context package, built from the database, with three layers:
            </p>
            <ul className="space-y-2">
              <li className="border-l-[3px] border-marker pl-3">
                <span className="font-semibold">Career summary.</span> Always included: totals, per-game and per-36
                averages, efficiency compared with the league in the same seasons, awards, peak seasons, career
                phases, strengths and limitations.
              </li>
              <li className="border-l-[3px] border-marker pl-3">
                <span className="font-semibold">Season history.</span> One line per season and per postseason, plus
                every conference finals and Finals series.
              </li>
              <li className="border-l-[3px] border-marker pl-3">
                <span className="font-semibold">Retrieved detail.</span> Picked for your question. A final-shot
                question pulls clutch, shot-creation and isolation data; a question about initiating the offense pulls
                playmaking and pick-and-roll data.
              </li>
            </ul>
            <p>
              Archetypes such as &quot;midrange scorer&quot; or &quot;isolation scorer&quot; are only claimed when a
              written statistical rule supports them. Every agent is told not to recommend itself by default and to
              mark each claim as a statistical fact or a basketball inference.
            </p>
          </div>
        </div>
      </section>

      <section aria-labelledby="rounds">
        <h2 id="rounds" className="font-display text-3xl font-bold">Inside a huddle</h2>
        <ol className="mt-5 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {ROUNDS.map((r) => (
            <li key={r.n} className={`rounded-md border bg-sheet p-4 ${r.n === "Coach" ? "border-2 border-ink" : "border-rule"}`}>
              <p className="text-sm text-ink-soft">{r.n}</p>
              <h3 className="font-display text-2xl font-bold">{r.name}</h3>
              <p className="mt-2 text-sm leading-relaxed">{r.body}</p>
            </li>
          ))}
        </ol>
        <p className="mt-5 max-w-[75ch] text-sm text-ink-soft">
          On the debate page, <span className="text-ink">Why did … say this?</span> opens the exact data that agent was
          given: the context sections, the documents retrieved for your question, and every stat it cited.
        </p>
      </section>

      <section className="rounded-md border border-rule bg-sheet p-5 sm:p-6">
        <h2 className="font-display text-2xl font-bold">What it isn&apos;t</h2>
        <ul className="mt-2 max-w-[75ch] list-disc space-y-1 pl-5 text-sm leading-relaxed">
          <li>The agents are statistical profiles, not the real players, and their lines are not quotes.</li>
          <li>The data has limits. For example, regular-season game logs aren&apos;t collected and Jordan&apos;s shot zones cover only his last four seasons. Each player&apos;s profile page lists what the data can&apos;t tell us.</li>
          <li>A small local model gives rougher reasoning than a hosted one. The data is the same, but the basketball judgment isn&apos;t.</li>
        </ul>
        <Link href="/" className="mt-5 inline-block rounded-md bg-marker px-5 py-2.5 font-display text-xl font-semibold text-white">
          Set a situation
        </Link>
      </section>
    </article>
  );
}
