/* Diagram of how HoopCouncil works, drawn in the site's whiteboard style.
   Top row: the data side, built once with `make pipeline`.
   Bottom row: what happens on every huddle. */

const INK = "var(--color-ink)";
const SOFT = "var(--color-ink-soft)";
const RULE = "var(--color-rule)";
const MARKER = "var(--color-marker)";
const RED = "var(--color-marker-red)";

const PLAYERS = [
  { name: "Curry", c: "var(--color-p-curry)" },
  { name: "Kobe", c: "var(--color-p-kobe)" },
  { name: "Jordan", c: "var(--color-p-jordan)" },
  { name: "Durant", c: "var(--color-p-durant)" },
  { name: "LeBron", c: "var(--color-p-lebron)" },
];

function Box({ x, y, w, h, title, lines, accent = INK, dashed = false }: {
  x: number; y: number; w: number; h: number; title: string; lines: string[]; accent?: string; dashed?: boolean;
}) {
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={8} fill="var(--color-sheet)" stroke={accent} strokeWidth={2}
        strokeDasharray={dashed ? "6 5" : undefined} />
      <text x={x + 14} y={y + 30} className="font-display" fontSize={21} fontWeight={700} fill={INK}>{title}</text>
      {lines.map((l, i) => (
        <text key={i} x={x + 14} y={y + 54 + i * 19} fontSize={13.5} fill={SOFT}>{l}</text>
      ))}
    </g>
  );
}

function Arrow({ d, color = INK, dashed = false }: { d: string; color?: string; dashed?: boolean }) {
  return (
    <path d={d} fill="none" stroke={color} strokeWidth={2.5} strokeLinecap="round"
      strokeDasharray={dashed ? "7 6" : undefined} markerEnd="url(#flow-arrow)" />
  );
}

export function FlowDiagramWide() {
  return (
    <svg viewBox="0 0 1140 600" role="img" className="block w-full"
      aria-label="Data flows from Basketball Reference and NBA.com through a validated pipeline into a database, becomes a context package per player, and feeds five agents who debate in three rounds before a coach agent makes the call.">
      <defs>
        <marker id="flow-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M0,0 L10,5 L0,10 z" fill={INK} />
        </marker>
      </defs>

      {/* Row labels */}
      <text x={20} y={26} className="font-display" fontSize={18} fontWeight={600} fill={MARKER}>Built once, from real data</text>
      <text x={20} y={316} className="font-display" fontSize={18} fontWeight={600} fill={RED}>Every time you start a huddle</text>
      <line x1={20} x2={1120} y1={292} y2={292} stroke={RULE} strokeDasharray="3 6" />

      {/* Row A: data side */}
      <Box x={20} y={42} w={230} h={210} title="Sources" accent={MARKER}
        lines={["Basketball Reference:", "  seasons, playoffs, awards,", "  shot zones, play-by-play", "NBA.com (optional):", "  clutch splits, play types", "Rate-limited, cached on disk"]} />
      <Arrow d="M252,147 L292,147" />
      <Box x={296} y={42} w={240} h={210} title="Pipeline"
        lines={["Parse every table", "Validate: career totals = sum", "  of seasons, award counts,", "  valid percentages", "Derive: peak score, career", "  phases, archetypes"]} />
      <Arrow d="M538,147 L578,147" />
      <Box x={582} y={42} w={230} h={210} title="Database"
        lines={["PostgreSQL, one row per", "  season / award / game", "Every stat keeps its source,", "  URL and retrieval time", "Missing data stays missing:", "  never estimated"]} />
      <Arrow d="M814,147 L854,147" />
      <Box x={858} y={42} w={262} h={210} title="Context packages"
        lines={["One per player, three layers:", "1 · career summary (always)", "2 · season-by-season tables", "3 · detail retrieved for the", "     specific question", "Numbers, not vague prose"]} />

      {/* Row B: per huddle */}
      <Box x={20} y={336} w={190} h={180} title="Your situation" accent={RED}
        lines={["Score, clock, timeouts,", "defense, possession,", "and your question"]} />
      {/* scoreboard chip */}
      <g transform="translate(34,446)">
        <rect width={162} height={50} rx={6} fill={INK} />
        <text x={22} y={34} textAnchor="middle" className="font-display" fontSize={24} fontWeight={700} fill="#ffcf5c">-1</text>
        <text x={80} y={34} textAnchor="middle" className="font-display" fontSize={24} fontWeight={700} fill="#ffcf5c">0:09</text>
        <text x={138} y={34} textAnchor="middle" className="font-display" fontSize={24} fontWeight={700} fill="#ffcf5c">Q4</text>
      </g>
      <Arrow d="M212,426 L252,426" />
      <Box x={256} y={336} w={170} h={180} title="Retrieval"
        lines={["Question → topics", "\"final shot\" pulls clutch,", "  shot creation, isolation", "\"initiate\" pulls playmaking,", "  usage, pick-and-roll"]} />

      {/* context → agents */}
      <Arrow d="M989,254 C989,300 700,300 520,334" color={MARKER} dashed />
      <text x={700} y={272} fontSize={13} fill={MARKER}>each agent gets only its player&apos;s package</text>
      <Arrow d="M428,426 L462,426" />

      {/* five agents */}
      <g>
        <rect x={466} y={336} width={130} height={250} rx={8} fill="var(--color-sheet)" stroke={INK} strokeWidth={2} />
        <text x={480} y={362} className="font-display" fontSize={19} fontWeight={700} fill={INK}>Five agents</text>
        {PLAYERS.map((p, i) => (
          <g key={p.name} transform={`translate(492, ${392 + i * 40})`}>
            <circle r={13} fill={p.c} stroke="#fff" strokeWidth={2} />
            <text x={24} y={6} fontSize={15} fontWeight={700} fill={INK}>{p.name}</text>
          </g>
        ))}
      </g>

      {/* three rounds */}
      <Arrow d="M598,400 L636,372" />
      <Arrow d="M598,440 L636,450" />
      <Arrow d="M598,500 L636,528" />
      <Box x={640} y={336} w={226} h={70} title="1 · Propose" lines={["each alone, in parallel"]} />
      <Box x={640} y={418} w={226} h={70} title="2 · Debate" lines={["all five proposals revealed"]} />
      <Box x={640} y={500} w={226} h={70} title="3 · Vote" lines={["final positions + reasons"]} />
      <path d="M753,406 L753,416" stroke={INK} strokeWidth={2.5} markerEnd="url(#flow-arrow)" />
      <path d="M753,488 L753,498" stroke={INK} strokeWidth={2.5} markerEnd="url(#flow-arrow)" />

      {/* coach */}
      <Arrow d="M868,452 L902,452" />
      <g>
        <rect x={906} y={336} width={214} height={250} rx={8} fill="var(--color-sheet)" stroke={INK} strokeWidth={3} />
        <text x={920} y={364} className="font-display" fontSize={21} fontWeight={700} fill={INK}>Coach&apos;s call</text>
        <text x={920} y={386} fontSize={13.5} fill={SOFT}>Stronger model reads all</text>
        <text x={920} y={404} fontSize={13.5} fill={SOFT}>rounds + all five packages;</text>
        <text x={920} y={422} fontSize={13.5} fill={SOFT}>judges logic, not the vote</text>
        {/* mini half court */}
        <g transform="translate(934,436)">
          <rect width={158} height={136} rx={3} fill="var(--color-wood)" />
          <rect x={56} y={0} width={46} height={52} fill="#c4823f" opacity={0.6} />
          <path d="M10,0 L10,40 A70,70 0 0 0 148,40 L148,0" fill="none" stroke="#fffaf0" strokeWidth={2} />
          <circle cx={79} cy={14} r={4} fill="none" stroke="#e5582a" strokeWidth={2} />
          <path d="M79,106 L120,72" stroke="var(--color-p-curry)" strokeWidth={2.5} strokeDasharray="5 4" markerEnd="url(#flow-arrow)" />
          <path d="M120,72 L82,20" stroke="var(--color-p-durant)" strokeWidth={2} strokeDasharray="2 5" />
          <circle cx={79} cy={106} r={8} fill="var(--color-p-curry)" stroke="#fff" strokeWidth={1.5} />
          <circle cx={120} cy={72} r={8} fill="var(--color-p-durant)" stroke="#fff" strokeWidth={1.5} />
          <circle cx={36} cy={60} r={8} fill="var(--color-p-jordan)" stroke="#fff" strokeWidth={1.5} />
          <circle cx={16} cy={16} r={8} fill="var(--color-p-kobe)" stroke="#fff" strokeWidth={1.5} />
          <circle cx={100} cy={40} r={8} fill="var(--color-p-lebron)" stroke="#fff" strokeWidth={1.5} />
        </g>
      </g>
    </svg>
  );
}

const STEPS: { title: string; body: string; tone: "data" | "huddle" }[] = [
  { title: "Sources", tone: "data", body: "Basketball Reference seasons, playoffs, awards, shot zones and play-by-play; optional NBA.com clutch splits and play types. Rate-limited and cached." },
  { title: "Pipeline", tone: "data", body: "Parses every table, validates it (career totals match the seasons, award counts match, percentages are valid) and derives peak scores, career phases and archetypes." },
  { title: "Database", tone: "data", body: "PostgreSQL. Every stat keeps its source, URL and retrieval time. Missing data stays missing." },
  { title: "Context packages", tone: "data", body: "One per player: a career summary, season tables, and detail retrieved for your question." },
  { title: "Your situation", tone: "huddle", body: "Score, clock, timeouts, defense and your question decide which detail each agent pulls in." },
  { title: "Five agents, three rounds", tone: "huddle", body: "Each agent proposes a play alone, then sees all five proposals and debates, then casts a final vote." },
  { title: "Coach's call", tone: "huddle", body: "A stronger model reads everything and picks the play on basketball logic, not the majority, then draws it on the court." },
];

export function FlowDiagramStacked() {
  return (
    <ol className="space-y-0">
      {STEPS.map((s, i) => (
        <li key={s.title} className="relative pl-8 pb-5 last:pb-0">
          {i < STEPS.length - 1 && <span aria-hidden className="absolute left-[11px] top-6 h-full w-0.5 bg-rule" />}
          <span aria-hidden className="absolute left-0 top-1 h-6 w-6 rounded-full border-2 bg-sheet"
            style={{ borderColor: s.tone === "data" ? "var(--color-marker)" : "var(--color-marker-red)" }} />
          <h3 className="font-display text-xl font-bold">{s.title}</h3>
          <p className="text-sm text-ink-soft">{s.body}</p>
        </li>
      ))}
    </ol>
  );
}
