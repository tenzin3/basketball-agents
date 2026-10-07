"""Optional NBA.com stats source (stats.nba.com JSON endpoints).

Provides data Basketball Reference does not publish:
  * clutch splits (last 5 minutes, score within 5)  - from 1996-97
  * Synergy play-type frequency / efficiency         - from 2015-16
  * tracking shot types: catch-and-shoot, pull-up, shot-clock buckets - from 2013-14

Disabled by default: enable with `--with-nba-stats` after reviewing NBA.com's Terms of
Use for your intended use. Requests are rate limited and cached like every other source.
Seasons before a dataset's start year are simply absent (stored as missing, never estimated).
"""
from __future__ import annotations

import logging

from ...players import PlayerConfig
from .base import DataSource, provenance, season_from_end_year

log = logging.getLogger(__name__)

STATS = "https://stats.nba.com/stats"
SOURCE = "NBA.com Stats"
HEADERS = {
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Accept": "application/json, text/plain, */*",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}
PLAY_TYPES = ["Isolation", "PRBallHandler", "PRRollman", "Postup", "Spotup", "Handoff", "Transition",
              "OffScreen", "Cut", "OffRebound", "Misc"]
CLUTCH_FIRST_END_YEAR = 1997
TRACKING_FIRST_END_YEAR = 2014
SYNERGY_FIRST_END_YEAR = 2016


def result_sets(payload: dict) -> dict:
    """{'resultSets': [{'name', 'headers', 'rowSet'}]} -> {name: [row dicts]}."""
    out = {}
    sets = payload.get("resultSets") or payload.get("resultSet") or []
    if isinstance(sets, dict):
        sets = [sets]
    for rs in sets:
        headers = rs.get("headers") or []
        if headers and isinstance(headers[0], dict):  # multi-level headers
            headers = headers[-1].get("columnNames", [])
        out[rs.get("name", "")] = [dict(zip(headers, r)) for r in rs.get("rowSet", [])]
    return out


class NBAStatsSource(DataSource):
    name = SOURCE
    homepage = "https://www.nba.com/stats"
    terms_note = "Optional; review NBA.com Terms of Use. Public JSON endpoints, rate limited."

    MAX_CONSECUTIVE_FAILURES = 2

    def _get(self, endpoint: str, params: dict):
        """Fetch one endpoint. After repeated failures (timeouts/blocks) the endpoint is skipped for
        the rest of the run instead of waiting on every request; the gap is reported, not filled."""
        import json

        if not hasattr(self, "_fails"):
            self._fails, self._dead = {}, set()
        if endpoint in self._dead:
            return None, None
        try:
            r = self.fetcher.get(f"{STATS}/{endpoint}", params=params)
        except Exception:
            self._fails[endpoint] = self._fails.get(endpoint, 0) + 1
            if self._fails[endpoint] >= self.MAX_CONSECUTIVE_FAILURES:
                self._dead.add(endpoint)
                log.warning("NBA.com endpoint %s failed %d times in a row; skipping it for the rest of this run",
                            endpoint, self._fails[endpoint])
            raise
        self._fails[endpoint] = 0
        if not r:
            return None, None
        try:
            return json.loads(r.text), r
        except ValueError:
            log.warning("non-JSON response from %s", r.url)
            return None, r

    def collect_player(self, player: PlayerConfig, league: dict) -> dict:
        seasons = league.get("player_end_years", {}).get(player.slug, [])
        frag = {"clutch": [], "play_types": [], "tracking_shots": [], "errors": []}
        for end_year in seasons:
            season = season_from_end_year(end_year)
            for season_type, st in (("Regular Season", "regular_season"), ("Playoffs", "playoffs")):
                if end_year >= CLUTCH_FIRST_END_YEAR:
                    self._clutch(player, season, season_type, st, frag)
                if end_year >= TRACKING_FIRST_END_YEAR:
                    self._tracking(player, season, season_type, st, frag)
                if end_year >= SYNERGY_FIRST_END_YEAR:
                    self._synergy(player, season, season_type, st, frag)
        return frag

    def _clutch(self, player, season, season_type, st, frag):
        params = {"ClutchTime": "Last 5 Minutes", "AheadBehind": "Ahead or Behind", "PointDiff": 5,
                  "College": "", "Conference": "", "Country": "", "DateFrom": "", "DateTo": "",
                  "Division": "", "DraftPick": "", "DraftYear": "", "GameScope": "", "GameSegment": "",
                  "Height": "", "LastNGames": 0, "LeagueID": "00", "Location": "", "MeasureType": "Base",
                  "Month": 0, "OpponentTeamID": 0, "Outcome": "", "PORound": 0, "PaceAdjust": "N",
                  "PerMode": "Totals", "Period": 0, "PlayerExperience": "", "PlayerPosition": "",
                  "PlusMinus": "N", "Rank": "N", "Season": season, "SeasonSegment": "",
                  "SeasonType": season_type, "ShotClockRange": "", "StarterBench": "", "TeamID": 0,
                  "VsConference": "", "VsDivision": "", "Weight": ""}
        try:
            data, r = self._get("leaguedashplayerclutch", params)
        except Exception as e:
            frag["errors"].append(f"clutch {season} {season_type}: {e}")
            return
        if not data:
            return
        for rows in result_sets(data).values():
            for row in rows:
                if row.get("PLAYER_ID") == player.nba_id:
                    frag["clutch"].append({
                        "season": season, "stat_type": st,
                        "definition": "last 5 minutes of 4th quarter/OT, score within 5",
                        "gp": row.get("GP"), "minutes": row.get("MIN"), "pts": row.get("PTS"),
                        "fgm": row.get("FGM"), "fga": row.get("FGA"), "fg_pct": row.get("FG_PCT"),
                        "fg3m": row.get("FG3M"), "fg3a": row.get("FG3A"), "fg3_pct": row.get("FG3_PCT"),
                        "ftm": row.get("FTM"), "fta": row.get("FTA"), "ft_pct": row.get("FT_PCT"),
                        "ast": row.get("AST"), "tov": row.get("TOV"), "plus_minus": row.get("PLUS_MINUS"),
                        "provenance": provenance(SOURCE, r.url, r.retrieved_at, season, st),
                    })

    def _tracking(self, player, season, season_type, st, frag):
        params = {"PlayerID": player.nba_id, "Season": season, "SeasonType": season_type, "LeagueID": "00",
                  "PerMode": "Totals", "TeamID": 0, "Outcome": "", "Location": "", "Month": 0,
                  "SeasonSegment": "", "DateFrom": "", "DateTo": "", "OpponentTeamID": 0, "VsConference": "",
                  "VsDivision": "", "GameSegment": "", "Period": 0, "LastNGames": 0}
        try:
            data, r = self._get("playerdashptshots", params)
        except Exception as e:
            frag["errors"].append(f"tracking {season} {season_type}: {e}")
            return
        if not data:
            return
        for set_name, rows in result_sets(data).items():
            if set_name not in ("GeneralShooting", "ShotClockShooting", "DribbleShooting", "ClosestDefenderShooting"):
                continue
            for row in rows:
                label = row.get("SHOT_TYPE") or row.get("SHOT_CLOCK_RANGE") or row.get("DRIBBLE_RANGE") or \
                    row.get("CLOSE_DEF_DIST_RANGE")
                frag["tracking_shots"].append({
                    "season": season, "stat_type": st, "category": set_name, "label": label,
                    "fga_frequency": row.get("FGA_FREQUENCY"), "fgm": row.get("FGM"), "fga": row.get("FGA"),
                    "fg_pct": row.get("FG_PCT"), "efg_pct": row.get("EFG_PCT"), "fg3a": row.get("FG3A"),
                    "fg3_pct": row.get("FG3_PCT"),
                    "provenance": provenance(SOURCE, r.url, r.retrieved_at, season, st),
                })

    def _synergy(self, player, season, season_type, st, frag):
        for pt in PLAY_TYPES:
            params = {"LeagueID": "00", "PerMode": "Totals", "PlayType": pt, "PlayerOrTeam": "P",
                      "SeasonType": season_type, "SeasonYear": season, "TypeGrouping": "offensive"}
            try:
                data, r = self._get("synergyplaytypes", params)
            except Exception as e:
                frag["errors"].append(f"synergy {pt} {season} {season_type}: {e}")
                continue
            if not data:
                continue
            for rows in result_sets(data).values():
                for row in rows:
                    if row.get("PLAYER_ID") == player.nba_id:
                        frag["play_types"].append({
                            "season": season, "stat_type": st, "play_type": pt,
                            "frequency": row.get("POSS_PCT"), "ppp": row.get("PPP"),
                            "percentile": row.get("PERCENTILE"), "possessions": row.get("POSS"),
                            "points": row.get("PTS"), "fg_pct": row.get("FG_PCT"), "efg_pct": row.get("EFG_PCT"),
                            "tov_freq": row.get("TOV_POSS_PCT"), "score_freq": row.get("SCORE_POSS_PCT"),
                            "provenance": provenance(SOURCE, r.url, r.retrieved_at, season, st),
                        })
