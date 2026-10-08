# HoopCouncil

Ask any basketball question and five AI players answer it: **Stephen Curry, Kobe Bryant, Michael Jordan, Kevin
Durant and LeBron James**. Each one argues only from its own real career stats. They answer, argue with each other,
and give a final word. Then an AI **Coach** reads the whole conversation and gives the final answer. If you asked
about a play, the Coach also draws it on a basketball court.

> These are AI characters built from statistics, not the real players. Nothing they say is a real quote.

## How it works, in four steps

1. **Collect the stats (done once).** A program downloads each player's seasons, playoffs, awards and shooting data
   from [Basketball Reference](https://www.basketball-reference.com). It goes slowly on purpose, to respect the site,
   and saves each page so it never downloads the same page twice.
2. **Check them.** Before anything is used, the numbers are checked. For example, career totals must equal the sum
   of the seasons, and percentages must make sense. Anything missing stays marked as missing; nothing is guessed.
3. **Make a fact sheet for each player.** The checked stats are turned into one fact sheet per player: a career
   summary, a line for every season, and extra detail picked to fit your question.
4. **Debate.** When you ask a question, each AI player gets only its own fact sheet and answers in three rounds.
   The Coach, a stronger AI model, then gives the final answer.

| Round | What happens |
|---|---|
| 1. First answers | All five answer at the same time, without seeing each other's answers. |
| 2. Debate | Each one reads all five answers, says who it agrees or disagrees with and why, and may change its mind. |
| 3. Final word | Each one gives its final answer and says whose argument it backs. |
| Coach's answer | The Coach weighs the evidence (not just the votes) and gives the answer, the reasons and the key numbers. |

Every reply has to use real numbers from the fact sheet and explain them so a fan without the data can follow. For
example, a reply might say something like "Curry made about 43% of his threes, while the league average in those
seasons was about 36%." Click **Why did …
say this?** under any message to see exactly which data that reply was built from.

## Common questions

**Do I need to pay for anything?**
No. You can run everything for free with a local AI model through [Ollama](https://ollama.com). Hosted models
(Anthropic, OpenAI, Google Gemini) give better answers but need an API key, and you pay the provider per use. One
question makes 16 AI calls: 5 players × 3 rounds, plus the Coach.

**Can the AI make up stats?**
It is told not to, and it is only given numbers from the checked database. Each number it uses is labelled as either
a fact from the data or a basketball opinion based on it. Smaller local models follow these rules less reliably than
hosted ones, so use **Why did … say this?** to check a claim.

**Why are the answers sometimes different if I ask the same thing twice?**
AI models don't give the exact same wording every time. The data behind them stays the same.

**Does it remember my earlier questions?**
No. Each question is debated fresh. Your chat stays visible in your browser until you click **Clear chat**.

**How long does one question take?**
With a hosted model, usually a minute or two. With a local model on a laptop, several minutes.

**Is any data missing?**
Yes, some. Older seasons have less detail. For example, shot locations only start in 1996-97, so Jordan's cover only
his last few seasons. Regular-season game logs aren't collected. Each player's profile page lists what the data can't
tell us, and the AI players are told to say so instead of guessing.

**Is downloading the stats allowed?**
The program follows the site's rules: one page every 3.5 seconds (the site allows up to 20 per minute), it skips
pages the site asks bots not to visit, and it saves every page so it only downloads once. NBA.com data is optional
and off by default; read NBA.com's terms before turning it on. If you put the app online publicly, check the data
sites' terms first.

**Can I put it online?**
Yes, see [Putting it online](#putting-it-online) below.

## Starting the app (Mac)

### What you need

* **Python 3.10 or newer** and **Node.js 20 or newer**.
* **Docker Desktop** to run the database. No Docker? See the tip under Troubleshooting.
* **Ollama** if you want the free local model. Optional.

### First time only

Open Terminal in the project folder (`basketball-agents/`) and run:

```bash
cp .env.example .env     # creates your settings file (pick a model in it, see "Choosing a model")
make setup               # installs everything the app needs
make db                  # starts the database
make pipeline            # downloads and checks the stats, builds the fact sheets (about 7 minutes)
```

You only run `make pipeline` once. Pages are saved in `data/raw/`, so running it again takes seconds and downloads
nothing new.

Optional extra stats from NBA.com (clutch numbers, play types, shot tracking; about 10 minutes):

```bash
cd backend && ../backend/.venv/bin/hoop pipeline --with-nba-stats && cd ..
```

### Every time

```bash
make dev
```

This one command starts the database, the local model (only if your settings use it and it isn't already running),
the backend and the website. Each log line is labelled `[api]`, `[web]` or `[ollama]`. When `[web]` says **Ready**,
open **http://localhost:3000**.

To stop, press **Ctrl-C**. The database keeps running quietly in Docker; stop it with `docker compose stop db`.
Your data is kept either way.

<details>
<summary>Prefer separate terminal tabs?</summary>

| Tab | Command | Ready when you see |
|---|---|---|
| 1. Database | `make db` | It returns straight away |
| 2. Local model (only if using `local`) | `OLLAMA_CONTEXT_LENGTH=16384 ollama serve` | `Listening on 127.0.0.1:11434` |
| 3. Backend | `make api` | `Uvicorn running on http://127.0.0.1:8000` |
| 4. Website | `make web` | `Ready` |

</details>

### Using it

1. Type any basketball question and press Enter, or click a suggestion. For example: "Who was the best playoff
   scorer of the five?" or "We're down 1 with 9 seconds left and they switch everything. Who takes the last shot?"
2. Choose a **Model** under the box.
3. Watch the five players answer, argue and give their final word, then read the Coach's answer.
4. Click **Why did … say this?** under a message to see the data behind it, or click a player's picture at the top
   to see their full stats. **How it works** (top right) shows the exact instructions each AI gets.

You can also ask from the terminal:

```bash
cd backend
../backend/.venv/bin/python simulate.py "Who was the best playoff scorer of the five?" --provider local
```

### Choosing a model

Set `HOOP_LLM_PROVIDER` in `.env`, or pick one from the **Model** menu on the website.

| Choice | What you need | Good to know |
|---|---|---|
| `local` | Ollama, then `ollama pull llama3.1` | Free and private, but slower and rougher answers. Ollama must run with `OLLAMA_CONTEXT_LENGTH=16384` (`make dev` does this), otherwise most of each player's data is silently cut off. |
| `anthropic` | `ANTHROPIC_API_KEY` in `.env` | Best answers. The players use a cheaper model and the Coach a stronger one, to keep costs down. |
| `openai` / `gemini` | `OPENAI_API_KEY` / `GEMINI_API_KEY` in `.env` | Same idea: cheaper model for players, stronger for the Coach. |
| `mock` | Nothing | Fake answers, only for testing the screens. |

To use a different Ollama model, set `HOOP_PLAYER_MODEL` and `HOOP_COACH_MODEL` in `.env` to a name from
`ollama list`, then restart.

### Troubleshooting

| Problem | Fix |
|---|---|
| Website says "Can't reach the API" | The backend isn't running. Start `make dev` (or `make api`) and reload the page. |
| `model 'llama3.1' not found` | Run `ollama pull llama3.1`, or set `HOOP_PLAYER_MODEL` / `HOOP_COACH_MODEL` to a model you have. |
| `ollama serve` says the address is already in use | Ollama is already running without the bigger context setting. Run `pkill ollama` (and quit the Ollama menu-bar app), then start again. |
| A debate fails because of a missing API key | Your `.env` model needs a key. Add it, or switch to `local` or `mock`. |
| The backend can't connect to the database | Open Docker Desktop, then run `make db`. |
| "No career data" or empty player pages | Run `make pipeline`. |
| Port 3000 or 8000 already in use | An old copy is still running. Stop it with Ctrl-C, or run `lsof -ti :8000 \| xargs kill`. |
| A reply "could not be read" | Small local models sometimes break the answer format. Ask again, or use a hosted model. |
| Changes don't show up | Restart `make dev`. The backend keeps the fact sheets in memory. |

**No Docker?** Put `DATABASE_URL=sqlite:///./hoopcouncil.db` in `.env` and skip `make db`. That's fine on your own
computer.

## Putting it online

Nothing is set up for this yet. The app has three parts: the website, the backend and the database. Two good ways to
host them:

| Option | What it looks like | Cost | Changes needed |
|---|---|---|---|
| **One small server** | Rent a small cloud server (Hetzner, DigitalOcean, AWS Lightsail) and run everything there with Docker. | About $5–12 a month | Very few: add Docker files and HTTPS. |
| **All on Vercel** | Website and backend on [Vercel](https://vercel.com), database on Neon (connected through Vercel). | Free tiers to start | Some code changes, listed below. |

**Why Vercel needs changes:** on Vercel, the backend only runs while it is answering a request (at most 5 minutes
on the free plan) and can't keep files. Today a debate keeps running in the background and is saved as a file. For
Vercel, each round would become its own request and debates would be saved in the database.

**Either way:**

* **Use a hosted AI model.** The local model can't run on these hosts, so you need an API key. Anyone with your link
  would spend it, so add a password or a limit on questions.
* **Don't run the stats download on the server.** Run it on your Mac, then copy the finished database up with
  `pg_dump` / `pg_restore`, and bring the `career_context_cache/` fact sheets. Git ignores them; `hoop build-context`
  rebuilds them from the database.
* **Two settings must point at each other:** `NEXT_PUBLIC_API_URL` on the website (the backend's web address) and
  `HOOP_CORS_ORIGINS` on the backend (the website's address).

---

## For developers

### The full data flow

```
Basketball Reference (+ optional NBA.com)          ─┐
        ↓  rate-limited scraper, raw HTML cache      │  backend/hoopcouncil/ingest
canonical dataset JSON  →  PostgreSQL (provenance)  ─┘
        ↓  aggregates · Finals splits · peak_score · phases · archetypes · validation   (derive/, quality/)
Career Context Builder → career_context_cache/<player>.json      (context/)
        ↓  layer 1 career summary + layer 2 seasons + layer 3 retrieval per question
Five player agents (cheaper model, run in parallel)   (agents/, orchestrator.py)
        ↓  Round 1 independent → Round 2 debate → Round 3 final word
Coach (stronger model) → answer (+ play call and court steps for play questions) → FastAPI → Next.js chat UI
```

### Commands

| Command | What it does |
|---|---|
| `make dev` | Database + Ollama (if `local`) + API + website in one terminal (`scripts/dev.sh`) |
| `hoop ingest [--players curry,kobe] [--no-gamelogs] [--with-nba-stats] [--offline] [--refresh]` | Fetch and parse into `data/processed/<player>.json` |
| `hoop load` | Write processed datasets into PostgreSQL |
| `hoop derive` | Aggregates, Finals splits, peak scores, phases, archetypes, strengths/limitations, milestones; validation; `data/reports/` |
| `hoop build-context` | `career_context_cache/<player>.json` and `<player>_context.txt`, plus retrieval documents |
| `hoop pipeline` | `ingest` + `load` + `derive` + `build-context` |
| `make report` | Data-quality report per player |
| `python simulate.py "question" [--provider local] [--context ...]` | Ask from the terminal |
| `hoop serve` / `make api` | API only |

Model settings in `.env`: `HOOP_LLM_PROVIDER` (`anthropic`, `openai`, `gemini`, `local`, `mock`). Players default to
the cheap tier (`claude-haiku-4-5-20251001` on Anthropic) and the coach to the strong tier (`claude-sonnet-5-5`).
Override with `HOOP_PLAYER_MODEL`, `HOOP_COACH_PROVIDER` and `HOOP_COACH_MODEL`. `local` is any OpenAI-compatible
server, such as Ollama.

### API

| Endpoint | Returns |
|---|---|
| `GET /players` | Player cards |
| `GET /players/{player}` | Full profile |
| `GET /players/{player}/career` | Seasons, playoffs, aggregates, Finals series, peak scores |
| `GET /players/{player}/achievements` | Structured award records |
| `GET /players/{player}/context` | The career context package |
| `GET /players/{player}/quality` | Data-quality report |
| `GET /prompts?question=` | Prompt templates, models and per-player retrieval (used by How it works) |
| `POST /simulations` | Starts a debate in the background; returns `{id}` |
| `GET /simulations/{id}` | Status, messages so far, coach decision |

### Where things live

```
backend/hoopcouncil/
  players.py              the five players (ids + focus areas; no stats)
  ingest/                 http cache + rate limit, Basketball Reference / NBA.com sources, pipeline
  db/                     SQLAlchemy models and loader
  derive/                 aggregates, features, peak score, phases, archetypes, strengths/limitations, milestones
  quality/validate.py     checks + per-player data-quality report
  context/                context builder, retrieval documents, BM25 retrieval, cache
  llm/providers.py        Anthropic / OpenAI / Gemini / local / mock
  agents/                 prompts, player + coach agents, JSON parsing and clean-up, court validation
  orchestrator.py         Round 1 → 2 → 3 → Coach (rounds run the five players in parallel)
  api/                    FastAPI
backend/simulate.py       terminal version of the chat
backend/tests/            tests on synthetic fixtures and the mock model
frontend/                 Next.js 15, React 19, TypeScript, Tailwind 4
scripts/dev.sh            the `make dev` launcher
docs/                     data sources, peak_score formula, archetype rules
career_context_cache/     generated by `hoop build-context` (don't edit by hand)
```

### Rules the AI players follow

* They only get database-built context and must cite numbers from it, explained in plain words (stat, value, time
  span, and a comparison such as the league average).
* They refer to players by name in the third person and never pretend to be the real person.
* Each cited number is tagged `FACT:` (straight from the data) or `INFERENCE:` (a basketball judgment from it).
* Missing data is reported as missing. Data-quality reports mark each category COMPLETE, PARTIAL or MISSING, and
  archetypes without data are labelled "insufficient data".
* Players don't see each other's confidence scores, only their arguments; the Coach sees everything.

### Testing

`cd backend && python -m pytest` (or `python -m unittest tests.test_pipeline`) runs 31 tests. They cover parsing
(traded seasons, did-not-play rows, tables hidden in HTML comments, old and new table ids), awards, playoff-round
inference, aggregates, validation (including deliberately broken data), the context builder, retrieval, prompt
templates, output clean-up and a full mock debate. All tests use **synthetic** data, not real statistics.

The real pipeline (live download, PostgreSQL load, validation) has been run end to end. The website was checked in a
browser against a mock backend. `next build` (a production build) hasn't been run yet.
