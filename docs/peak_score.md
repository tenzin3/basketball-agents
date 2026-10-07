# Peak-season detection (`peak_score`)

Implemented in `backend/hoopcouncil/derive/peak.py`. A score from 0 to 1 is computed for every regular-season
(combined, non-split) row, then stored on `player_seasons.peak_score` with its components in
`player_seasons.peak_components`.

```
peak_score = sqrt(availability) × (0.35·impact + 0.15·scoring + 0.15·efficiency + 0.15·playoffs + 0.20·recognition)
```

| Component | Definition | Scale (clipped to 0–1) |
|---|---|---|
| availability | regular-season minutes | MP / 2800 |
| impact | mean of available box metrics | (BPM + 2) / 14, WS/48 / 0.30, (PER − 10) / 22 |
| scoring | points per game | (PPG − 10) / 25 |
| efficiency | TS% relative to that season's league TS% | (TS − leagueTS + 0.02) / 0.10; falls back to (TS − 0.50) / 0.15 if league average is missing |
| playoffs | same postseason's BPM and WS/48 | mean((pBPM + 2) / 14, pWS48 / 0.30) × min(1, playoff G / 16); 0 if no postseason |
| recognition | award points, capped at 1 | MVP .60, Finals MVP .40, title .25, All-NBA 1st/2nd/3rd .35/.20/.10, scoring title .15, DPOY .20, All-Defensive 1st/2nd .10/.05, MVP vote finish 2nd–5th .15 |

Design choices:

* **Awards are at most 20%.** A season can't become a peak on recognition alone, and a dominant season without
  awards still scores high through impact, efficiency and playoffs.
* **Fixed scales.** Components use absolute, cross-player scales, so scores are comparable between players. A
  within-career `career_rank` is stored too.
* **Availability uses a square root.** This dampens the effect so that a 60-game season isn't punished as hard
  as a 20-game one.
* **Missing components count as 0.** They're listed in `missing_components`, so the gap is visible and never
  filled with an estimate.

**Which seasons count as peaks.** A season is a peak when `peak_score >= max(0.55, 0.85 × career best)`. At most
five are kept, best first. If nothing clears the bar, the single best season is shown.

**Statistical career phases** (`derive/phases.py`) reuse the scores:

* **Peak** runs contiguously from the first to the last season scoring at least 0.85 × the career best.
* **Prime** extends Peak outward through adjacent seasons scoring at least 0.65 × the best. Seasons under 500
  minutes don't break the span.
* **Early** and **Late** are the seasons before and after Prime.

Team stints are computed separately, for example "LeBron James — CLE I / MIA / CLE II / LAL".
