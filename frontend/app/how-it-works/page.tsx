import type { Metadata } from "next";
import Link from "next/link";
import { FlowDiagramStacked, FlowDiagramWide } from "@/components/FlowDiagram";
import PromptExplorer from "@/components/PromptExplorer";

export const metadata: Metadata = {
  title: "How it works · HoopCouncil",
  description: "How HoopCouncil turns real career stats into five AI players who debate your question, and a coach who answers it.",
};

const ROUNDS = [
  {
    n: "Round 1",
    name: "First answers",
    body: "All five AI players get your question at the same time and answer on their own. None of them can see the others' answers yet, so nobody just copies the first reply.",
  },
  {
    n: "Round 2",
    name: "Debate",
    body: "Now each one reads all five answers. It says, by name, who it agrees or disagrees with and why, and it may change its mind. They don't have to disagree if the numbers point the same way.",
  },
  {
    n: "Round 3",
    name: "Final word",
    body: "Each one gives a short final answer and says whose argument it backs.",
  },
  {
    n: "Coach",
    name: "The answer",
    body: "A separate, stronger AI reads all three rounds and all five players' career summaries. It goes with the best evidence, not just the most votes, and explains why, with the key numbers and the ideas it turned down. If you asked about a play, it also draws the play on the court.",
  },
];

const FAQ = [
  {
    q: "Are these the real players talking?",
    a: "No. Each one is an AI that only knows that player's statistics. They talk about the player by name (\"Curry made...\"), never pretend to be him, and nothing they say is a real quote. The avatars are just initials.",
  },
  {
    q: "Can the AI make up stats?",
    a: "It's told not to, and it's only given numbers from the checked database. Each number it uses is marked as either a fact from the data or a basketball opinion based on it. Smaller local models follow the rules less reliably, so use \"Why did … say this?\" to check any claim.",
  },
  {
    q: "Why does each player give a different answer?",
    a: "Not because of a made-up personality. They differ in three ways: each sees only its own player's numbers, each is asked to look at the question from different angles (spacing for Curry, shot creation for Kobe, passing for LeBron), and the question pulls different detail out of each player's data.",
  },
  {
    q: "Does it remember my earlier questions?",
    a: "No. Every question is debated from scratch. Your chat stays on screen in this browser until you click Clear chat.",
  },
  {
    q: "Why might I get a different answer if I ask again?",
    a: "AI models don't word things the same way every time, and a close call can tip either way. The data behind the answers doesn't change.",
  },
  {
    q: "How long does a question take, and what does it cost?",
    a: "Each question makes 16 AI calls: 5 players × 3 rounds, plus the Coach. With a hosted model that's usually a minute or two and costs a little per question. A free local model runs on your own computer but takes several minutes and gives rougher answers.",
  },
  {
    q: "What can't the data tell us?",
    a: "Older seasons have less detail. Shot locations only start in 1996-97, so Jordan's cover just his last four seasons, and play-type data only starts in 2015-16. Regular-season game logs aren't collected. When something isn't in the data, the AI players are told to say so instead of guessing. Each player's profile page lists these gaps.",
  },
];

export default function HowItWorks() {
  return (
    <article className="space-y-14">
      <header className="max-w-3xl">
        <Link href="/" className="text-sm text-marker underline-offset-2 hover:underline">Back to the chat</Link>
        <h1 className="mt-2 font-display text-5xl font-bold sm:text-6xl">How HoopCouncil works</h1>
        <p className="mt-3 text-lg text-ink-soft">
          You ask any basketball question. Five AI players (Stephen Curry, Kobe Bryant, Michael Jordan, Kevin Durant and
          LeBron James) each answer using only that player&apos;s real career stats. They argue it out over three
          rounds, and then an AI coach gives the final answer.
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
          <h2 className="font-display text-3xl font-bold">Where the numbers come from</h2>
          <div className="mt-3 max-w-[65ch] space-y-3 leading-relaxed">
            <p>
              A program collects every season, playoff run, award and shooting profile for the five players from
              Basketball Reference. Extra stats from NBA.com, such as clutch numbers and play types, are optional. It
              downloads slowly on purpose, to respect the sites, and saves every page so it only downloads once.
            </p>
            <p>
              Then the numbers are checked. Career totals must equal the sum of the seasons, award counts must match
              the site&apos;s own totals, and percentages must make sense. Each player gets a report showing which
              kinds of data are complete, partial or missing.
            </p>
            <p>
              Missing stays missing. If a stat doesn&apos;t exist for a season, the AI player is told the data
              doesn&apos;t show it. Nothing is filled in with a guess.
            </p>
          </div>
        </div>
        <div>
          <h2 className="font-display text-3xl font-bold">What each AI player is given</h2>
          <div className="mt-3 max-w-[65ch] space-y-3 leading-relaxed">
            <p>Each AI player gets a fact sheet about its own player, built from the checked data, in three parts:</p>
            <ul className="space-y-2">
              <li className="border-l-[3px] border-marker pl-3">
                <span className="font-semibold">Career summary.</span> Always included: career totals, averages, how
                efficient he was compared with the rest of the league in the same years, awards, best seasons,
                strengths and weaknesses.
              </li>
              <li className="border-l-[3px] border-marker pl-3">
                <span className="font-semibold">Season by season.</span> One line for every season and playoff run,
                plus every conference finals and Finals series.
              </li>
              <li className="border-l-[3px] border-marker pl-3">
                <span className="font-semibold">Extra detail for your question.</span> A last-shot question pulls in
                clutch and one-on-one numbers. &quot;Who was the better scorer?&quot; pulls in scoring titles,
                efficiency and playoff numbers. A question about running the offense pulls in passing and
                pick-and-roll numbers.
              </li>
            </ul>
            <p>
              Labels like &quot;midrange scorer&quot; are only used when a written rule based on the stats supports
              them. Every AI player is told not to pick its own player just because it&apos;s him, and to explain
              every number in plain words for someone who hasn&apos;t seen the data.
            </p>
          </div>
        </div>
      </section>

      <section aria-labelledby="rounds">
        <h2 id="rounds" className="font-display text-3xl font-bold">What happens when you ask a question</h2>
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
          Under every message, <span className="text-ink">Why did … say this?</span> shows exactly what that reply was
          built from: which parts of the fact sheet it had, the extra detail picked for your question, and every number
          it cited.
        </p>
      </section>

      <PromptExplorer />

      <section aria-labelledby="faq">
        <h2 id="faq" className="font-display text-3xl font-bold">Common questions</h2>
        <dl className="mt-4 grid gap-x-10 gap-y-5 md:grid-cols-2">
          {FAQ.map((f) => (
            <div key={f.q} className="max-w-[65ch]">
              <dt className="font-semibold">{f.q}</dt>
              <dd className="mt-1 text-sm leading-relaxed text-ink-soft">{f.a}</dd>
            </div>
          ))}
        </dl>
        <Link href="/" className="mt-8 inline-block rounded-md bg-marker px-5 py-2.5 font-display text-xl font-semibold text-white">
          Ask the council
        </Link>
      </section>
    </article>
  );
}
