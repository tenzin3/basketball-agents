# Data sources and provenance

## Basketball Reference (default source)

| Page | Used for |
|---|---|
| `/players/<l>/<id>.html` | Bio (height, weight, position, draft, birth date, Hall of Fame) and site badges, used only for cross-checks. Per-game, totals, per-100, advanced, shooting and play-by-play tables for both regular season and playoffs, plus the awards column. League-leader markers come from bold per-game cells. |
| `/players/<l>/<id>/gamelog/<year>` | Regular-season game logs. The site's `robots.txt` currently disallows these pages, so the scraper checks once and skips them; reports show "PLAYOFFS ONLY". |
| `/players/<l>/<id>/gamelog-playoffs/` | Playoff game logs. Rounds come from the player page's `playoffs_series` table (WC1/WCS/WCF/FIN). |
| `/playoffs/` | Champion, runner-up and Finals MVP for each season |
| `/awards/{mvp,dpoy,roy,all_star_mvp,all_league,all_defense}.html` | Award winners, which are authoritative for those awards |
| `/leagues/NBA_stats_per_game.html` | League averages, for era-relative comparisons |

**Volume and rate limits.** The full run is about 110 pages. Requests are spaced 3.5 s apart, which stays under the
20 requests/minute in Sports Reference's [bot policy](https://www.sports-reference.com/bot-traffic.html).

**Caching and robots.txt.** Every response is cached raw under `data/raw/`. Re-runs don't touch the network, and
`--offline` re-parses from the cache only. `robots.txt` is honoured. A 429 response stops the run; cached pages are
kept, so the next run resumes.

**Terms.** Review the [terms of use](https://www.sports-reference.com/termsofuse.html) before running. This project
is meant for personal, non-commercial use.

## NBA.com stats (optional: `--with-nba-stats`)

* Clutch splits (last 5 minutes, within 5 points) from 1996-97.
* Synergy play types from 2015-16.
* Shot tracking from 2013-14: catch-and-shoot, pull-ups, shot-clock buckets.

This source is off by default. Review NBA.com's terms before enabling it. Seasons before each dataset begins stay
missing.

## Provenance fields

Every statistic row keeps the following:

```json
{"source": "Basketball Reference", "source_url": "https://…", "season": "2015-16",
 "retrieved_at": "2026-10-07T…Z", "stat_type": "regular_season"}
```

| Stat type | Origin |
|---|---|
| `regular_season`, `playoffs` | Source tables |
| `conference_finals`, `nba_finals` | Aggregated from playoff game logs (`player_finals_stats`, `player_career_aggregates`) |

## Known limitations, stated rather than patched

* **Wingspan.** Not published by these sources, so it is stored as `null`.
* **Shot distance.** Basketball Reference starts in 1996-97, so Jordan's coverage is partial.
* **Playoff rounds.** Labels come from the source's playoff-series table (`round_confidence = labeled`). Only if
  that table is missing does the pipeline fall back to opponent sequence in the game logs (`confirmed`,
  `consistent` or `inferred`).
* **Regular-season game logs.** Not collected because `robots.txt` disallows them. Career highs and 40-point
  games therefore come from playoff logs only, and the context says so.
* **Close games.** These are full-game box scores of games decided by 3 points or fewer. They are not late-game
  possessions.
* **Awards from the awards column.** Basketball Reference records voting finishes such as "MVP-3". Only rank 1
  becomes an award; other finishes are stored separately as `*_VOTING_FINISH`.

## Adding a source

1. Implement `ingest.sources.base.DataSource` so it returns a dataset fragment.
2. Merge the fragment in `ingest.dataset.assemble`.
3. Give every record a `provenance(...)` dict.

The loader, validation and context builder don't need changes for new rows of existing kinds.
