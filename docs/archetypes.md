# Data-backed archetypes

Implemented in `backend/hoopcouncil/derive/archetypes.py`. Each tag is evaluated by an explicit rule and stored in
`player_archetypes` with:

* `status`: `supported`, `not_supported` or `insufficient_data`
* `evidence`: the numbers behind the call, with season coverage
* `rule`: the threshold applied

Only `supported` tags are shown to agents as archetypes. `insufficient_data` tags are listed under DATA LIMITATIONS,
so an agent knows the data **does not establish** them. That's different from establishing that they're false.

All career values are minutes-weighted over the seasons that have the statistic. "League" means Basketball
Reference league averages for the same seasons.

| Tag | Rule | Data needed |
|---|---|---|
| high-volume shot creator | USG% ≥ 30% and (if available) ≤ 45% of made 2s assisted | advanced, shooting (1996-97+) |
| high-volume three-point shooter | 3PA rate ≥ 1.4× league and 3P% ≥ league + 3 pts | per game, league averages |
| midrange scorer | ≥ 30% of FGA from 10 ft to the arc, FG% there ≥ 42% | shooting (1996-97+) |
| rim attacker | ≥ 30% of FGA at 0–3 ft, or FTA/FGA ≥ 0.40 | shooting / advanced |
| three-level scorer | rim ≥ 15%, midrange ≥ 20%, threes ≥ 15% of FGA, TS ≥ league + 2 | shooting, league |
| primary playmaker | AST% ≥ 35% | advanced |
| secondary playmaker | 20% ≤ AST% < 35% | advanced |
| efficient volume scorer | TS ≥ league + 4 pts at USG% ≥ 25% | advanced, league |
| elite perimeter defender | (≥ 3 All-Defensive or a DPOY) and STL% ≥ 1.8% | awards, advanced |
| weak-side rim protector | BLK% ≥ 2.5% | advanced |
| rebounding forward/wing | TRB% ≥ 12% | advanced |
| foul-drawing pressure | FTA per 36 ≥ 7.0 | totals |
| positional versatility | ≥ 2 positions at ≥ 20% of minutes | play-by-play (2000-01+) |
| size mismatch scorer | listed ≥ 6-9, 3P% ≥ league, TS ≥ league + 3 | bio, league |
| isolation / pick-and-roll / post / transition / movement / spot-up | Synergy frequency thresholds (15% / 20% / 8% / 15% / 7% / 20%) | NBA.com Synergy (2015-16+, optional source) |
| late-clock creator | ≥ 8% of FGA with 4–0 s on the shot clock | NBA.com tracking (2013-14+) |
| pull-up scorer | pull-ups ≥ 35% of FGA | NBA.com tracking (2013-14+) |
| clutch scorer | ≥ 30 pts/36 over ≥ 100 clutch minutes | NBA.com clutch (1996-97+) |

## What this means for these five players

* **Michael Jordan.** Most of his seasons predate shot-distance and play-by-play data. Expect several tags to be
  `insufficient_data`; the archetypes from the spec, such as "post scorer", are not asserted.
* **Kobe Bryant.** Play-type data covers only 2015-16, his final season.
* **Data quality reports.** These show exactly which categories are PARTIAL for each player.

Thresholds are deliberately simple and live in one file, so they're easy to tune.
