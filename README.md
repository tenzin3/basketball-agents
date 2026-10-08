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
Not necessarily. On your Mac you can use a free local model through [Ollama](https://ollama.com). Online, the app
uses [OpenRouter](https://openrouter.ai): one key that reaches many AI models, including free ones. HoopCouncil tries
the free models first and only falls back to a cheap paid model (about a cent per question) when no free one
answers. One question makes 16 AI calls: 5 players × 3 rounds, plus the Coach.

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
Yes, for free, on Vercel. See [Putting it online](#putting-it-online-vercel) below.

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
2. Watch the five players answer, argue and give their final word, then read the Coach's answer.
3. Click **Why did … say this?** under a message to see the data behind it, or click a player's picture at the top
   to see their full stats. **How it works** (top right) shows the exact instructions each AI gets.

You can also ask from the terminal:

```bash
cd backend
../backend/.venv/bin/python simulate.py "Who was the best playoff scorer of the five?" --provider local
```

### Choosing a model

Set `HOOP_LLM_PROVIDER` in `.env` and restart `make dev`. (In the terminal, `simulate.py --provider` picks one per question.)

| Choice | What you need | Good to know |
|---|---|---|
| `openrouter` (default) | `OPENROUTER_API_KEY` in `.env` | Free models first, then a cheap paid backup from your OpenRouter credit. Free models change often and can be slow or busy; the backup keeps answers coming. |
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
| A debate fails because of a missing API key | Your `.env` model needs a key (`OPENROUTER_API_KEY` for the default). Add it, or switch to `local` or `mock`. |
| The backend can't connect to the database | Open Docker Desktop, then run `make db`. |
| "No career data" or empty player pages | Run `make pipeline`. |
| Port 3000 or 8000 already in use | An old copy is still running. Stop it with Ctrl-C, or run `lsof -ti :8000 \| xargs kill`. |
| A reply "could not be read" | Small local models sometimes break the answer format. Ask again, or use a hosted model. |
| Changes don't show up | Restart `make dev`. The backend keeps the fact sheets in memory. |

**No Docker?** Put `DATABASE_URL=sqlite:///./hoopcouncil.db` in `.env` and skip `make db`. That's fine on your own
computer.

## Putting it online (Vercel)

Everything runs on [Vercel](https://vercel.com) for free: the website, the Python backend and a free Neon Postgres
database for the stats. Only the AI answers come from OpenRouter. The settings are already in the code
(`vercel.json`), so you only do the account and data steps below.

**What's different from your Mac:**

* **One round at a time.** On Vercel the backend only runs while it is answering a request (up to 5 minutes), so
  your browser asks for one round at a time: round 1, 2, 3, then the coach. If you close the tab mid-debate, it
  continues when you open it again. This switches on by itself.
* **No local model.** Ollama can't run on Vercel, so the hosted site uses OpenRouter.

### What it costs

* **Vercel and Neon:** free. Vercel's free Hobby plan is for personal, non-commercial projects.
* **OpenRouter:** free models cost nothing. They're limited to 50 requests a day, about 3 questions, until you've
  added $10 of credit once; after that, 1,000 a day, about 60 questions. The $10 isn't used up by free models. It
  pays for the backup model only when no free model answers, at about a cent per question.

### What you need

* The code on GitHub. Yours is at `github.com/tenzin3/basketball-agents`.
* A [Vercel](https://vercel.com) account. Sign up with GitHub.
* An [OpenRouter](https://openrouter.ai) account and an API key (in OpenRouter: your profile menu, **Keys**,
  **Create key**). Optional but recommended: add $10 of credit (**Credits**).
* Your local database with the stats, running (`make db`). You downloaded these once with `make pipeline`.

### Step by step

1. **Try OpenRouter on your Mac first.** Put your key in `.env`, run `make dev` and ask a question
   (the server uses OpenRouter by default; set `HOOP_LLM_PROVIDER=openrouter` if your `.env` says otherwise):
   ```bash
   OPENROUTER_API_KEY=sk-or-...
   ```
2. **Push the code to GitHub:**
   ```bash
   git add -A && git commit -m "Ready for Vercel" && git push
   ```
3. **Create the Vercel project.** On [vercel.com/new](https://vercel.com/new), import `basketball-agents`. Leave
   **Root Directory** as the top of the repository (`vercel.json` tells Vercel about the `frontend/` and `backend/`
   parts) and click **Deploy**. The site loads, but questions won't work until steps 4 to 7 are done.
4. **Add the database.** In the project, open **Storage**, create a **Neon** (Postgres) database on the free plan and
   connect it to the project. This adds a `DATABASE_URL` setting for you.
5. **Copy your stats into it.** Open the new database in **Storage** and copy its connection string (it starts with
   `postgresql://` or `postgres://`). On your Mac, with `make db` running:
   ```bash
   make copy-db TO="postgresql://...paste it here..."
   ```
   It creates the tables, copies every stats table and the five players' fact sheets, and prints how many rows went
   over. Your saved chats stay on your Mac.
6. **Add the settings** in **Settings > Environment Variables**:

   | Name | Value | Why |
   |---|---|---|
   | `OPENROUTER_API_KEY` | your key | lets the AI players and coach answer; only the backend can read it |
   | `HOOP_ACCESS_CODE` | a code you choose | **recommended**: only people with the code can ask, so strangers can't use up your free quota or credit |
   | `HOOP_DAILY_LIMIT` | e.g. `30` | optional: questions per 24 hours across all visitors. Hosted, it is 50 unless you change it (`0` = no cap) |

7. **Redeploy** so the settings take effect: **Deployments**, the menu (⋯) on the latest one, **Redeploy**.
8. **Check it.** Open `https://<your-project>.vercel.app/api/health`. It should show `"ok": true` and
   `"run_mode": "steps"`. Then open the site, type the access code under the chat box, and ask.

From now on, every `git push` redeploys. If you run `make pipeline` again, run `make copy-db` again to update the
hosted stats.

### If something goes wrong

| Problem | Fix |
|---|---|
| "Can't reach the server right now" | Open `/api/health` on your site. If that fails too, check the project's **Logs** in Vercel. |
| "No career data for: …" | Step 5 hasn't been done, or went to another database. Run `make copy-db` with the connection string of the database connected to this project. |
| "This council needs an access code" | Type the code from `HOOP_ACCESS_CODE` in the box under the chat. |
| A debate fails with `OPENROUTER_API_KEY is not set` | Add the key in Vercel's Environment Variables, then redeploy. |
| A debate fails with HTTP 402 or 429 from OpenRouter | 402: your OpenRouter balance is below zero or the backup needs credit. 429: the day's free requests are used up. Add credit, or wait until tomorrow. |
| Replies are slow or a round says it took too long | Free models can be slow or busy. The page retries by itself. To skip free models, set `HOOP_OPENROUTER_PLAYER_MODEL=meta-llama/llama-3.1-8b-instruct` (paid, about a cent per question). |
| The build fails on `services` in `vercel.json` | Running several parts in one Vercel project ("Services") is in beta. Instead, make two Vercel projects from the same repository, one with Root Directory `frontend` and one with `backend`. Connect the database and add the settings to the backend project. Set `NEXT_PUBLIC_API_URL` on the website project to the backend's address, and `HOOP_CORS_ORIGINS` on the backend project to the website's address. |

### Safety built in

* **Your key never reaches the browser.** It lives only in Vercel's settings and is used by the backend.
* **Visitors can't pick expensive models.** They can only choose between providers you have a key for, and
  requests naming specific models are refused when hosted (`HOOP_ALLOW_MODEL_OVERRIDE=1` turns this back on).
* **A daily cap of 50 questions** applies when hosted, unless you set `HOOP_DAILY_LIMIT`.
* **Visitors can't read each other's questions.** The list of recent debates is turned off when hosted; a single debate
  is only reachable through its long random link.
* **Error messages are cleaned** of anything that looks like a key, password or database address before visitors
  see them.
* **Choose a long access code** (a few random words). Each wrong guess is slowed down, but a short code can still be
  guessed.

### Changing the models

The players and the coach both start with `openrouter/free`, which picks a free model that is available right now.
The backups are `meta-llama/llama-3.1-8b-instruct` for players and `meta-llama/llama-3.3-70b-instruct` for the coach.
To choose different models, set any of these (model ids are listed on [openrouter.ai/models](https://openrouter.ai/models)):
`HOOP_OPENROUTER_PLAYER_MODEL`, `HOOP_OPENROUTER_COACH_MODEL`, `HOOP_OPENROUTER_PLAYER_FALLBACKS`,
`HOOP_OPENROUTER_COACH_FALLBACKS` (comma-separated). Free models can be removed at any time, and some free providers
may use prompts for training; OpenRouter's privacy settings let you exclude those.

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
| `hoop copy-db URL` / `make copy-db TO=URL` | Copy the local database (stats + fact sheets) to the hosted Postgres |

Model settings in `.env`: `HOOP_LLM_PROVIDER` (`openrouter`, `anthropic`, `openai`, `gemini`, `local`, `mock`). The
OpenRouter settings are described under [Changing the models](#changing-the-models). For the others, players default to
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
| `GET /config` | Run mode, model choices, whether an access code is needed |
| `POST /simulations` | Starts a debate; returns `{id, run_mode}`. Needs header `x-access-code` if `HOOP_ACCESS_CODE` is set |
| `POST /simulations/{id}/step` | Step mode: runs the next round (or the coach) and returns the debate |
| `GET /simulations/{id}` | Status, messages so far, coach decision |

Every route is also served under `/api` (for example `/api/players`), the path the website uses on Vercel.
Debates run in one of two modes (`HOOP_RUN_MODE`): `background`, the local default, where the API runs all rounds
itself, or `steps`, the default on Vercel, where the browser calls `/step` once per round. Each step rebuilds the
agents from the stored question and earlier rounds, and a row in `simulation_steps` stops two requests running the
same round. The five fact sheets are stored in the database (`context_packages`) as well as in
`career_context_cache/`, so the hosted backend needs nothing but `DATABASE_URL`.

### Where things live

```
backend/hoopcouncil/
  players.py              the five players (ids + focus areas; no stats)
  ingest/                 http cache + rate limit, Basketball Reference / NBA.com sources, pipeline
  db/                     SQLAlchemy models and loader
  derive/                 aggregates, features, peak score, phases, archetypes, strengths/limitations, milestones
  quality/validate.py     checks + per-player data-quality report
  context/                context builder, retrieval documents, BM25 retrieval, cache
  llm/providers.py        OpenRouter / Anthropic / OpenAI / Gemini / local / mock
  agents/                 prompts, player + coach agents, JSON parsing and clean-up, court validation
  orchestrator.py         Round 1 → 2 → 3 → Coach (rounds run the five players in parallel)
  api/                    FastAPI
backend/main.py           `app` entry point for Vercel
backend/simulate.py       terminal version of the chat
backend/tests/            tests on synthetic fixtures and the mock model
frontend/                 Next.js 15, React 19, TypeScript, Tailwind 4
scripts/dev.sh            the `make dev` launcher
vercel.json               one Vercel project: website at /, backend at /api
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

`cd backend && python -m pytest` (or `python -m unittest tests.test_pipeline`) runs 40 tests. They cover parsing
(traded seasons, did-not-play rows, tables hidden in HTML comments, old and new table ids), awards, playoff-round
inference, aggregates, validation (including deliberately broken data), the context builder, retrieval, prompt
templates, output clean-up, a full mock debate, the OpenRouter fallbacks, and the hosted setup (database URLs,
step-by-step debates through the API with an access code and daily limit, and `copy-db`). All tests use **synthetic** data, not real statistics.

The real pipeline (live download, PostgreSQL load, validation) has been run end to end. The website was checked in a
browser against the real backend in step mode (SQLite, mock model). Not yet run: a real Vercel deploy, `copy-db`
into Neon, a live OpenRouter call, and `next build`.
