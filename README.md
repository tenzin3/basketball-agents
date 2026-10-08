# HoopCouncil

Five statistical player agents (Stephen Curry, Kobe Bryant, Michael Jordan, Kevin Durant and LeBron James) analyse a
basketball situation, debate it, and vote. A separate Coach agent then makes the final call and draws the play on a
half court.

> AI simulation based on player statistics and career tendencies. Agents represent statistical profiles, not the
> real players, and nothing they say is a quote.

Every basketball fact an agent sees comes from the project's own database, which is filled by a scraper with
provenance on every row. Nothing is written in by hand or taken from the LLM's memory.

```
Basketball Reference (+ optional NBA.com)          ─┐
        ↓  rate-limited scraper, raw HTML cache      │  backend/hoopcouncil/ingest
canonical dataset JSON  →  PostgreSQL (provenance)  ─┘
        ↓  aggregates · Finals splits · peak_score · phases · archetypes · validation   (derive/, quality/)
Career Context Builder → career_context_cache/<player>.json      (context/)
        ↓  layer 1 career summary + layer 2 seasons + layer 3 retrieval per scenario
Curry · Kobe · Jordan · Durant · LeBron agents  (cheap model, concurrent)   (agents/, orchestrator.py)
        ↓  Round 1 independent → Round 2 debate → Round 3 votes
Coach agent (stronger model) → play call + court instructions → FastAPI → Next.js huddle UI
```

## Starting the application (macOS)

You need Python 3.10+, Node 20+, and Docker Desktop (or any PostgreSQL 14+). For free local models you also need
[Ollama](https://ollama.com).

### 1. One-time setup

Run these from the project folder (`basketball-agents/`):

```bash
cp .env.example .env     # then pick a model provider (see step 3)
make setup               # Python venv + backend install + frontend npm install
make db                  # start PostgreSQL in Docker (user/pass/db: hoop/hoop/hoopcouncil)
make pipeline            # scrape → database → derive → validate → build context packages (~7 min first time)
make report              # optional: data-quality report for each player
```

`make pipeline` only needs to run once. It caches every page in `data/raw/`, so later runs take seconds and make no
new requests. For clutch splits, play types and shot tracking from NBA.com, run the opt-in source once (about 10 min;
review NBA.com's terms first):

```bash
cd backend && ../backend/.venv/bin/hoop pipeline --with-nba-stats && cd ..
```

### 2. Every time you want to use it

One command starts everything in a single terminal:

```bash
make dev
```

It starts PostgreSQL in Docker (and waits until it accepts connections), starts Ollama if `.env` uses the `local`
provider and Ollama isn't already running, then runs the API and the website. Each output line is tagged `[api]`,
`[web]` or `[ollama]`. Open **http://localhost:3000** once `[web]` prints `Ready`. Ctrl-C stops everything except
the database, which keeps running in Docker.

If you prefer separate tabs (handy for reading one log at a time), run the pieces yourself:

| Tab | Command | Wait for |
|---|---|---|
| 1. Database | `make db` | Returns straight away; Docker keeps PostgreSQL running |
| 2. Local model (only if using `local`) | `OLLAMA_CONTEXT_LENGTH=16384 ollama serve` | `Listening on 127.0.0.1:11434` |
| 3. API | `make api` | `Uvicorn running on http://127.0.0.1:8000` |
| 4. Website | `make web` | `Ready` |

Then open **http://localhost:3000**:

1. Type any basketball question in the chat box and press Enter, or click one of the suggestions. For example,
   "Who was the best playoff scorer of the five?" or "We're down 1 with 9 seconds left and they switch everything.
   Who takes the last shot?"
2. Pick a **Model** under the box first (for example **Local model**).
3. Watch the agents answer as chat messages, each with its own avatar: first answers (given independently), then the
   debate, then each agent's final word. Use **Why did … say this?** under any message to see the data that agent
   used.
4. The **Coach** gives the final answer. Questions about a play also get the full play call and an animated court
   diagram.

Each question is discussed fresh; the agents don't remember earlier questions. Your chat is kept in this browser
until you click **Clear chat**. Click an avatar at the top to open that player's data profile, or use **How it
works** (top right) to see the prompts each agent gets.

You can also ask from the terminal without the website:

```bash
cd backend
../backend/.venv/bin/python simulate.py "Who was the best playoff scorer of the five?" --provider local
../backend/.venv/bin/python simulate.py "Down 3 with 5 seconds. Who shoots?" --provider local
```

### 3. Choosing a model

Set `HOOP_LLM_PROVIDER` in `.env`, or pick a model per debate from the **Model** menu on the website or with
`--provider` in the terminal.

| Provider | Needs | Notes |
|---|---|---|
| `local` | Ollama + `ollama pull llama3.1` | Free and private. Start Ollama with `OLLAMA_CONTEXT_LENGTH=16384`; at the default context length, most of each agent's career data is silently cut off. A full debate (16 model calls) takes several minutes on a laptop. |
| `anthropic` | `ANTHROPIC_API_KEY` in `.env` | Best reasoning. Player agents use a cheap model, the coach a stronger one. |
| `openai` / `gemini` | `OPENAI_API_KEY` / `GEMINI_API_KEY` | Same tiering. |
| `mock` | Nothing | Offline placeholder. Every agent gives the same canned answer; useful only for checking the UI. |

To use a different Ollama model, set `HOOP_PLAYER_MODEL` and `HOOP_COACH_MODEL` to a name from `ollama list`, then
restart `make api`.

### 4. Stopping

Press Ctrl-C in the `make dev` terminal (or in each tab). To stop the database, run `docker compose stop db`. Your data stays in
the Docker volume and `data/`.

### Troubleshooting

| Symptom | Fix |
|---|---|
| Website says "Can't reach the API" | Start `make api` (tab 3), then reload the page. |
| Debate stops with `model 'llama3.1' not found` | Run `ollama pull llama3.1`, or set `HOOP_PLAYER_MODEL` / `HOOP_COACH_MODEL` to a model you already have. |
| `ollama serve` says the address is already in use | Ollama is already running. Run `pkill ollama` (and quit the menu-bar app), then start it again with the context setting. |
| Debate fails on a missing API key | The provider in `.env` (default `anthropic`) has no key. Add one, or pick `local` / `mock`. |
| `make api` can't connect to the database | Start Docker Desktop, then run `make db`. |
| "No career data" or empty player cards | Run `make pipeline`. |
| Port 3000 or 8000 already in use | An old server is still running. Stop it with Ctrl-C in its tab, or run `lsof -ti :8000 \| xargs kill`. |
| An agent's reply "could not be read as JSON" | Small local models sometimes break the format. Run the debate again, or use a hosted model. |
| Data or code changed but the site looks stale | Restart `make api`. It caches the context packages in memory. |

**No Docker?** Set `DATABASE_URL=sqlite:///./hoopcouncil.db` in `.env` and skip `make db`. PostgreSQL is the target,
and SQLite is fine for local use.

## Commands

| Command | What it does |
|---|---|
| `hoop ingest [--players curry,kobe] [--no-gamelogs] [--with-nba-stats] [--offline] [--refresh]` | Fetch and parse into `data/processed/<player>.json` |
| `hoop load` | Write processed datasets into PostgreSQL |
| `hoop derive` | Compute aggregates, Finals splits, peak scores, phases, archetypes, strengths/limitations and milestones; validate; write `data/reports/` |
| `hoop build-context` | Write `career_context_cache/<player>.json` and `<player>_context.txt` for manual inspection, plus retrieval documents |
| `hoop pipeline` | All four steps above |
| `python simulate.py "any basketball question" --provider local` | Ask the council from the terminal |
| `hoop serve` | API |

Model settings live in `.env`:

* `HOOP_LLM_PROVIDER`: `anthropic`, `openai`, `gemini`, `local` or `mock`.
* Player agents default to the cheap tier (`claude-haiku-4-5-20251001` on Anthropic).
* The coach defaults to the strong tier (`claude-sonnet-5-5`).
* Override with `HOOP_PLAYER_MODEL`, `HOOP_COACH_PROVIDER` and `HOOP_COACH_MODEL`.
* `local` is any OpenAI-compatible server, such as Ollama.

## API

| Endpoint | Returns |
|---|---|
| `GET /players` | Player cards |
| `GET /players/{player}` | Full profile |
| `GET /players/{player}/career` | Seasons, playoffs, aggregates, Finals series, peak scores |
| `GET /players/{player}/achievements` | Structured award records |
| `GET /players/{player}/context` | The Career Context Package |
| `GET /players/{player}/quality` | Data-quality report |
| `POST /simulations` | Starts a debate in the background; returns `{id}` |
| `GET /simulations/{id}` | Status, transcript, coach decision |

## Where things live

```
backend/hoopcouncil/
  players.py              the five fixed players (ids + agent focus areas; no stats)
  ingest/                 http cache + rate limit, Basketball Reference / NBA.com sources, dataset assembly, pipeline
  db/                     SQLAlchemy models (all tables from the spec + league averages, champions, documents), loader
  derive/                 aggregates, features, peak score, phases, archetypes, strengths/limitations, milestones
  quality/validate.py     checks + per-player data-quality report
  context/                career_context_builder, retrieval documents, BM25/embeddings retrieval, cache
  llm/providers.py        Anthropic / OpenAI / Gemini / local / mock
  agents/                 prompts, player + coach agents, JSON parsing, court-instruction validation
  orchestrator.py         Round 1 → 2 → 3 → Coach (asyncio.gather per round)
  api/                    FastAPI
backend/simulate.py       Phase 3 CLI
backend/tests/            unit + end-to-end tests on SYNTHETIC fixtures and the mock LLM
frontend/                 Next.js 15 + React 19 + TypeScript + Tailwind 4
docs/                     data sources, peak_score formula, archetype rules
career_context_cache/     generated by `hoop build-context` (never edit by hand)
```

## Grounding rules (enforced in prompts and data)

* Agents get only database-derived context and must cite numbers from it.
* `data_support` items are tagged `FACT:` or `INFERENCE:`.
* Missing data is reported as missing. Data-quality reports mark each category COMPLETE, PARTIAL or MISSING.
* Archetypes without data are labelled "insufficient data" and never asserted.
* Award records are structured and queryable, one row per award per season, with source URLs. The source's summary
  badges are used only to cross-check counts.

## Testing status

`cd backend && python -m pytest` runs 24 tests. They cover parsing (including traded seasons, did-not-play rows,
commented tables and old/new table ids), awards, playoff-round inference, aggregates, validation (including
deliberately corrupted data), the context builder, retrieval, and a full mock debate. All tests use **synthetic**
fixtures, not real statistics.

The UI was rendered and screenshot-checked against a mock API. Not yet exercised end to end:

* **Live scrape.** Parsers target Basketball Reference's current and previous table layouts. If a page has changed,
  `data/reports/<player>.txt` and the `tables_found` field show which tables were matched.
* **PostgreSQL loader and repository.**
* **`next build`.**
