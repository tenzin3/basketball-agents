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

## Quick start (macOS)

You need Python 3.10+, Node 20+, and Docker (or any PostgreSQL 14+).

```bash
cp .env.example .env            # add ANTHROPIC_API_KEY (or OpenAI / Gemini / local model settings)
make setup                      # venv + pip install -e backend + npm install
make db                         # PostgreSQL in Docker (user/pass/db: hoop/hoop/hoopcouncil)
make pipeline                   # scrape → load → derive → validate → build context packages
make report                     # data-quality report per player
make simulate                   # Phase 3 CLI debate in the terminal
make api                        # FastAPI on http://localhost:8000  (docs at /docs)
make web                        # UI on http://localhost:3000
```

**First pipeline run.** Expect about 7 minutes, roughly 110 pages at one request every 3.5 s. That follows Sports
Reference's 20 requests/minute bot policy. Pages are cached in `data/raw/`, so later runs are instant, and
`hoop ingest --offline` re-parses from the cache only. If the site ever answers 429, the run stops, keeps what it
has, and resumes from the cache next time.

**Optional extra data.** `hoop pipeline --with-nba-stats` adds clutch splits (1996-97+), Synergy play types (2015-16+)
and shot tracking (2013-14+) from NBA.com. It's off by default; review NBA.com's terms first.

**No Docker?** Set `DATABASE_URL=sqlite:///./hoopcouncil.db` in `.env`. PostgreSQL is the target, and SQLite works
for local experiments.

**Trying the UI without API keys.** Choose "Mock (offline test)" in the model menu, or run
`python simulate.py --provider mock`. The mock produces clearly labelled placeholder reasoning; it still needs the
data pipeline to have run.

## Commands

| Command | What it does |
|---|---|
| `hoop ingest [--players curry,kobe] [--no-gamelogs] [--with-nba-stats] [--offline] [--refresh]` | Fetch and parse into `data/processed/<player>.json` |
| `hoop load` | Write processed datasets into PostgreSQL |
| `hoop derive` | Compute aggregates, Finals splits, peak scores, phases, archetypes, strengths/limitations and milestones; validate; write `data/reports/` |
| `hoop build-context` | Write `career_context_cache/<player>.json` and `<player>_context.txt` for manual inspection, plus retrieval documents |
| `hoop pipeline` | All four steps above |
| `python simulate.py --clock 8 --margin -1 --defense "switch everything" --question "Who gets the final shot?"` | CLI debate |
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
