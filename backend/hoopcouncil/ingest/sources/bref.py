"""Basketball Reference source.

Pages used (all public, fetched at <= ~17 requests/minute and cached on disk):
  /players/<l>/<id>.html                     bio, per-game, totals, advanced, shooting,
                                             play-by-play (regular season + playoffs), awards column
  /players/<l>/<id>/gamelog/<year>           regular-season game logs (one page per season)
  /players/<l>/<id>/gamelog-playoffs/        playoff game logs (whole career)
  /playoffs/                                 champions, runners-up, Finals MVPs by season
  /awards/{mvp,dpoy,roy,all_star_mvp,all_league,all_defense}.html   award lists
  /leagues/NBA_stats_per_game.html           league averages by season (era context)

Sports Reference's terms permit personal use of their pages but restrict automated
access to their published bot rate limit; review https://www.sports-reference.com/termsofuse.html
and https://www.sports-reference.com/bot-traffic.html before running.
"""
from __future__ import annotations

import logging
import re
from datetime import date

from bs4 import BeautifulSoup

from ...players import PlayerConfig
from .base import DataSource, provenance, season_from_end_year
from .bref_columns import map_row, row_meta
from .table_parse import Table, all_tables, find_table, parse_number, player_id_from_hrefs, team_from_hrefs

log = logging.getLogger(__name__)

BASE = "https://www.basketball-reference.com"
SOURCE = "Basketball Reference"

TABLE_IDS = {
    ("regular_season", "per_game"): ["per_game_stats", "per_game"],
    ("regular_season", "totals"): ["totals_stats", "totals"],
    ("regular_season", "advanced"): ["advanced", "advanced_stats"],
    ("regular_season", "shooting"): ["shooting", "shooting_stats"],
    ("regular_season", "pbp"): ["pbp", "pbp_stats"],
    ("regular_season", "per_poss"): ["per_poss_stats", "per_poss"],
    ("playoffs", "per_game"): ["per_game_stats_post", "playoffs_per_game"],
    ("playoffs", "totals"): ["totals_stats_post", "playoffs_totals"],
    ("playoffs", "advanced"): ["advanced_post", "playoffs_advanced"],
    ("playoffs", "shooting"): ["shooting_post", "playoffs_shooting"],
    ("playoffs", "pbp"): ["pbp_post", "playoffs_pbp"],
    ("playoffs", "per_poss"): ["per_poss_stats_post", "playoffs_per_poss"],
}
CAPTIONS = {
    ("regular_season", "per_game"): ["per game"],
    ("regular_season", "totals"): ["totals"],
    ("regular_season", "advanced"): ["advanced"],
    ("regular_season", "shooting"): ["shooting"],
    ("regular_season", "pbp"): ["play-by-play"],
    ("regular_season", "per_poss"): ["per 100"],
    ("playoffs", "per_game"): ["playoffs", "per game"],
    ("playoffs", "totals"): ["playoffs", "totals"],
    ("playoffs", "advanced"): ["playoffs", "advanced"],
    ("playoffs", "shooting"): ["playoffs", "shooting"],
    ("playoffs", "pbp"): ["playoffs", "play-by-play"],
    ("playoffs", "per_poss"): ["playoffs", "per 100"],
}
SEASON_RE = re.compile(r"^(\d{4})-(\d{2})$")
COMBINED_TEAM_RE = re.compile(r"^(TOT|\d+TM)$")

AWARD_TOKEN_MAP = {
    "AS": "ALL_STAR", "NBA1": "ALL_NBA_FIRST", "NBA2": "ALL_NBA_SECOND", "NBA3": "ALL_NBA_THIRD",
    "DEF1": "ALL_DEFENSIVE_FIRST", "DEF2": "ALL_DEFENSIVE_SECOND",
}
VOTED_AWARDS = {"MVP": "NBA_MVP", "DPOY": "DEFENSIVE_PLAYER_OF_THE_YEAR", "ROY": "ROOKIE_OF_THE_YEAR",
                "CPOY": "CLUTCH_PLAYER_OF_THE_YEAR", "6MOY": "SIXTH_MAN_OF_THE_YEAR", "MIP": "MOST_IMPROVED_PLAYER"}

# League-leader markers (bold cells in the regular-season per-game table).
LEADER_TITLES = {"pts_per_g": "SCORING_TITLE", "ast_per_g": "ASSIST_TITLE", "stl_per_g": "STEALS_TITLE",
                 "trb_per_g": "REBOUNDING_TITLE", "blk_per_g": "BLOCKS_TITLE"}

AWARD_PAGES = {
    "NBA_MVP": "/awards/mvp.html",
    "DEFENSIVE_PLAYER_OF_THE_YEAR": "/awards/dpoy.html",
    "ROOKIE_OF_THE_YEAR": "/awards/roy.html",
    "ALL_STAR_GAME_MVP": "/awards/all_star_mvp.html",
    "ALL_NBA": "/awards/all_league.html",
    "ALL_DEFENSIVE": "/awards/all_defense.html",
}


def _season_label(text: str) -> str | None:
    """Accept '2015-16' or a 4-digit end year '2016'."""
    t = (text or "").strip()
    m = SEASON_RE.match(t)
    if m:
        return t
    m = re.match(r"^(\d{4})$", t)
    if m:
        return season_from_end_year(int(m.group(1)))
    m = re.match(r"^(\d{4})-(\d{2})", t)
    return t[:7] if m else None


def parse_award_tokens(text: str | None) -> list:
    """'MVP-1,AS,NBA1' -> [{'achievement_type': 'NBA_MVP', ...}, ...]."""
    out = []
    if not text:
        return out
    for tok in [t.strip() for t in text.split(",") if t.strip()]:
        if tok in AWARD_TOKEN_MAP:
            out.append({"achievement_type": AWARD_TOKEN_MAP[tok], "detail": None, "token": tok})
            continue
        m = re.match(r"^([A-Z0-9]+)-(\d+)$", tok)
        if m and m.group(1) in VOTED_AWARDS:
            award, rank = VOTED_AWARDS[m.group(1)], int(m.group(2))
            out.append({"achievement_type": f"{award}_VOTING_FINISH", "detail": {"rank": rank}, "token": tok})
            if rank == 1:
                out.append({"achievement_type": award, "detail": None, "token": tok})
            continue
        out.append({"achievement_type": "OTHER_AWARD_TOKEN", "detail": {"token": tok}, "token": tok})
    return out


def parse_bio(html: str, url: str, retrieved_at: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    meta = soup.find(id="meta") or soup
    text = re.sub(r"\s+", " ", meta.get_text(" ", strip=True))
    h1 = meta.find("h1")
    bio: dict = {"full_name": h1.get_text(" ", strip=True) if h1 else None}
    m = re.search(r"Position:\s*(.+?)(?:\s*▪|\s+Shoots:|$)", text)
    if m:
        parts = [p.strip() for p in re.split(r",| and ", m.group(1)) if p.strip()]
        bio["primary_position"] = parts[0] if parts else None
        bio["secondary_positions"] = parts[1:]
    m = re.search(r"Shoots:\s*(Right|Left)", text)
    bio["shoots"] = m.group(1) if m else None
    m = re.search(r"\b(\d)-(\d{1,2})\s*,\s*(\d{2,3})\s*lb", text)
    if m:
        bio["height_in"] = int(m.group(1)) * 12 + int(m.group(2))
        bio["weight_lb"] = int(m.group(3))
    m = re.search(r"\((\d{3})\s*cm,\s*(\d{2,3})\s*kg\)", text)
    if m:
        bio["height_cm"], bio["weight_kg"] = int(m.group(1)), int(m.group(2))
    birth = meta.find(id="necro-birth")
    bio["birth_date"] = birth.get("data-birth") if birth is not None and birth.get("data-birth") else None
    m = re.search(r"Draft:\s*(.+?),\s*(\d+)(?:st|nd|rd|th) round \((\d+)(?:st|nd|rd|th) pick,\s*(\d+)(?:st|nd|rd|th) overall\),\s*(\d{4}) NBA Draft", text)
    if m:
        bio.update({"draft_team": m.group(1).strip(), "draft_round": int(m.group(2)),
                    "draft_pick": int(m.group(4)), "draft_year": int(m.group(5))})
    m = re.search(r"Hall of Fame:\s*Inducted as Player in (\d{4})", text)
    bio["hall_of_fame_inducted"] = int(m.group(1)) if m else None
    bio["wingspan_in"] = None  # not published by this source; never estimated
    bling = soup.find(id="bling")
    bio["bling"] = [li.get_text(" ", strip=True) for li in bling.find_all("li")] if bling else []
    bio["provenance"] = provenance(SOURCE, url, retrieved_at, stat_type="biography")
    return bio


def _team_of(meta: dict) -> tuple:
    team_text = (meta.get("team") or "").strip()
    abbr, end_year = team_from_hrefs(meta.get("team_hrefs") or [])
    return (abbr or team_text or None), end_year, team_text


def parse_player_tables(html: str, url: str, retrieved_at: str) -> dict:
    """Parse all season tables of a player page into season records + source career rows."""
    tables = all_tables(html)
    seasons: dict = {}      # (stat_type, season, team) -> record
    career_rows: dict = {}  # stat_type -> kind -> values
    dnp: list = []
    found_tables: dict = {}
    for (stat_type, kind), ids in TABLE_IDS.items():
        t = find_table(tables, ids, CAPTIONS[(stat_type, kind)])
        if t is None:
            continue
        found_tables[f"{stat_type}.{kind}"] = t.id
        for row in t.body:
            meta = row_meta(row)
            season = _season_label(meta.get("season") or "")
            if not season:
                continue
            if row.special_text:
                if kind == "per_game":
                    dnp.append({"season": season, "stat_type": stat_type, "note": row.special_text,
                                "provenance": provenance(SOURCE, url, retrieved_at, season, stat_type)})
                continue
            team, _end, team_text = _team_of(meta)
            key = (stat_type, season, team)
            rec = seasons.setdefault(key, {
                "season": season, "stat_type": stat_type, "team": team, "team_text": team_text,
                "age": parse_number(meta.get("age")), "league": meta.get("league"), "pos": meta.get("pos"),
                "is_combined": bool(COMBINED_TEAM_RE.match(team_text or "")),
                "per_game": {}, "totals": {}, "advanced": {}, "shooting": {}, "pbp": {}, "per_poss": {},
                "awards_text": None, "league_leader_in": [],
                "provenance": provenance(SOURCE, url, retrieved_at, season, stat_type),
            })
            vals, leaders = map_row(row, kind)
            rec[kind] = vals
            if kind == "per_game":
                rec["league_leader_in"] = leaders
                if meta.get("awards"):
                    rec["awards_text"] = meta["awards"]
            elif meta.get("awards") and not rec.get("awards_text"):
                rec["awards_text"] = meta["awards"]
        for row in t.foot:
            first = row.first_text()
            if first.lower().startswith("career"):
                vals, _ = map_row(row, kind)
                career_rows.setdefault(stat_type, {})[kind] = vals
    # Seasons with several team rows: the combined row is the season record; team rows are splits.
    by_season: dict = {}
    for (st, season, _team), rec in seasons.items():
        by_season.setdefault((st, season), []).append(rec)
    out = []
    for (_st, _season), recs in by_season.items():
        if len(recs) == 1:
            recs[0]["is_combined"] = True
            recs[0]["is_team_split"] = False
            recs[0]["teams"] = [recs[0]["team"]]
        else:
            teams = [r["team"] for r in recs if not r["is_combined"]]
            for r in recs:
                r["is_team_split"] = not r["is_combined"]
                r["teams"] = teams if r["is_combined"] else [r["team"]]
        out.extend(recs)
    # All-Star table (fallback / cross-check for the awards column)
    all_star = []
    t = find_table(tables, ["all_star", "all_star_stats", "allstar"], ["all-star"])
    if t is not None:
        for row in t.body:
            s = _season_label(row.first_text())
            if s:
                all_star.append({"season": s, "note": row.special_text})
    return {"seasons": out, "career_rows": career_rows, "dnp_seasons": dnp, "all_star_rows": all_star,
            "tables_found": found_tables}


def _find_gamelog_table(tables: dict, ids: list) -> Table | None:
    t = find_table(tables, ids)
    if t is not None:
        return t
    cands = [t for t in tables.values() if {"Date", "Opp"} <= set(t.labels())]
    return max(cands, key=lambda t: len(t.body)) if cands else None


def parse_gamelog(html: str, url: str, retrieved_at: str, stat_type: str, season_hint: str | None = None) -> list:
    tables = all_tables(html)
    ids = ["player_game_log_reg", "pgl_basic"] if stat_type == "regular_season" else \
        ["player_game_log_post", "pgl_basic_playoffs"]
    t = _find_gamelog_table(tables, ids)
    if t is None:
        return []
    games = []
    for row in t.body:
        date_cell = row.get("Date") or row.by_stat("date", "date_game")
        if date_cell is None:
            continue
        dm = re.search(r"(\d{4})-(\d{2})-(\d{2})", date_cell.text)
        if not dm:
            for h in date_cell.hrefs:
                hm = re.search(r"/boxscores/(\d{4})(\d{2})(\d{2})0", h)
                if hm:
                    dm = hm
                    break
        if not dm:
            continue
        d = date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
        season = season_hint if stat_type == "regular_season" and season_hint else season_from_end_year(d.year if stat_type == "playoffs" or d.month < 9 else d.year + 1)
        team_cell = row.get("Team") or row.get("Tm") or row.by_stat("team_name_abbr", "team_id")
        opp_cell = row.get("Opp") or row.by_stat("opp_name_abbr", "opp_id")
        loc_cell = row.by_stat("game_location")
        res_cell = row.get("Result") or row.by_stat("game_result")
        series_cell = row.get("Series") or row.get("Rd") or row.by_stat("series", "round_id")
        res_text = res_cell.text if res_cell else ""
        rm = re.match(r"^\s*([WL])\b[ ,]*\(?([+-]?\d+)?", res_text)
        margin = None
        sm = re.search(r"(\d+)-(\d+)", res_text)
        if sm:
            margin = int(sm.group(1)) - int(sm.group(2))
        elif rm and rm.group(2):
            margin = int(rm.group(2))
        if row.special_text:
            team_cell = team_cell if team_cell is not None and team_cell.colspan < 4 else None
            opp_cell = opp_cell if opp_cell is not None and opp_cell.colspan < 4 else None
            res_text = ""
            rm = None
            margin = None
        g = {
            "season": season, "stat_type": stat_type, "date": d.isoformat(),
            "team": (team_from_hrefs(team_cell.hrefs)[0] or team_cell.text) if team_cell else None,
            "opponent": (team_from_hrefs(opp_cell.hrefs)[0] or opp_cell.text) if opp_cell else None,
            "home": (loc_cell.text.strip() != "@") if loc_cell is not None else None,
            "result": rm.group(1) if rm else None, "margin": margin,
            "series_label": series_cell.text if series_cell else None,
            "boxscore_url": next((BASE + h for h in date_cell.hrefs if "/boxscores/" in h), None),
            "status": "played", "stats": {},
            "provenance": provenance(SOURCE, url, retrieved_at, season, stat_type),
        }
        if row.special_text:
            g["status"] = row.special_text
        else:
            vals, _ = map_row(row, "totals")
            gs = row.get("GS")
            if gs is not None:
                vals["gs"] = 1 if gs.text.strip() in ("1", "*") else 0
            g["stats"] = vals
        games.append(g)
    return games


def parse_playoffs_index(html: str, url: str, retrieved_at: str) -> list:
    """Rows of /playoffs/: season, league, champion, runner-up, finals MVP."""
    tables = all_tables(html)
    t = find_table(tables, ["champions_index"]) or next(
        (t for t in tables.values() if "Champion" in t.labels()), None)
    out = []
    if t is None:
        return out
    for row in t.body:
        y = parse_number(row.first_text())
        if not isinstance(y, int):
            continue
        lg = row.get("Lg")
        if lg is not None and lg.text and lg.text != "NBA":
            continue
        champ, runner, fmvp = row.get("Champion"), row.get("Runner-Up"), row.get("Finals MVP")
        out.append({
            "season": season_from_end_year(y), "end_year": y,
            "champion": team_from_hrefs(champ.hrefs)[0] if champ else None,
            "champion_name": champ.text if champ else None,
            "runner_up": team_from_hrefs(runner.hrefs)[0] if runner else None,
            "runner_up_name": runner.text if runner else None,
            "finals_mvp_ids": player_id_from_hrefs(fmvp.hrefs) if fmvp else [],
            "provenance": provenance(SOURCE, url, retrieved_at, season_from_end_year(y), "league_history"),
        })
    return out


def parse_award_page(html: str, url: str, retrieved_at: str, award: str) -> list:
    """Generic: one row per season, winners linked as /players/... . For ALL_NBA / ALL_DEFENSIVE
    the team ('1st'/'2nd'/'3rd') is read from the row."""
    out = []
    for t in all_tables(html).values():
        for row in t.body:
            season = _season_label(row.first_text())
            if not season:
                continue
            lg = row.get("Lg")
            if lg is not None and lg.text and lg.text != "NBA":
                continue
            ids = []
            team_level = None
            for _col, cell in row.cells:
                ids.extend(player_id_from_hrefs(cell.hrefs))
                if cell.text in ("1st", "2nd", "3rd"):
                    team_level = cell.text
            atype = award
            if award in ("ALL_NBA", "ALL_DEFENSIVE"):
                if team_level is None:
                    continue
                level = {"1st": "FIRST", "2nd": "SECOND", "3rd": "THIRD"}[team_level]
                atype = f"{award}_{level}"
            for pid in ids:
                out.append({"achievement_type": atype, "season": season, "bref_id": pid,
                            "provenance": provenance(SOURCE, url, retrieved_at, season, "award")})
    # de-duplicate (multiple tables on one page can repeat rows)
    seen, uniq = set(), []
    for a in out:
        k = (a["achievement_type"], a["season"], a["bref_id"])
        if k not in seen:
            seen.add(k)
            uniq.append(a)
    return uniq


def parse_league_averages(html: str, url: str, retrieved_at: str) -> dict:
    tables = all_tables(html)
    t = find_table(tables, ["stats", "stats_per_game"]) or next(
        (t for t in tables.values() if "Season" in t.labels() and "PTS" in t.labels()), None)
    out: dict = {}
    if t is None:
        return out
    extra = {"Pace": "pace", "ORtg": "ortg", "TS%": "ts_pct", "FT/FGA": "ft_per_fga", "3PAr": "fg3a_rate",
             "TOV%": "tov_pct", "ORB%": "orb_pct", "eFG%": "efg_pct", "FG%": "fg_pct", "3P%": "fg3_pct",
             "FT%": "ft_pct"}
    for row in t.body:
        meta = row_meta(row)
        season = _season_label(meta.get("season") or "")
        if not season:
            continue
        lg = meta.get("league")
        if lg and lg != "NBA":
            continue
        vals, _ = map_row(row, "per_game")
        for col, cell in row.cells:
            if col is not None and col.label in extra and extra[col.label] not in vals:
                v = parse_number(cell.text)
                if extra[col.label] in ("tov_pct", "orb_pct") and v is not None and v > 1:
                    v = v / 100
                vals[extra[col.label]] = v
        if vals.get("fga_per_g") and vals.get("fg3a_per_g") is not None and vals.get("fg3a_rate") is None:
            vals["fg3a_rate"] = round(vals["fg3a_per_g"] / vals["fga_per_g"], 4)
        if vals.get("ts_pct") is None and vals.get("pts_per_g") and vals.get("fga_per_g") and vals.get("fta_per_g") is not None:
            vals["ts_pct"] = round(vals["pts_per_g"] / (2 * (vals["fga_per_g"] + 0.44 * vals["fta_per_g"])), 4)
        vals["provenance"] = provenance(SOURCE, url, retrieved_at, season, "league_average")
        out[season] = vals
    return out


class BasketballReferenceSource(DataSource):
    name = SOURCE
    homepage = BASE
    terms_note = "Personal, non-commercial use; <=20 requests/minute per Sports Reference bot policy."

    def __init__(self, fetcher, include_gamelogs: bool = True):
        super().__init__(fetcher)
        self.include_gamelogs = include_gamelogs

    def collect_league(self) -> dict:
        league: dict = {"champions": [], "awards": [], "league_averages": {}, "errors": []}
        r = self.fetcher.get(BASE + "/playoffs/")
        if r:
            league["champions"] = parse_playoffs_index(r.text, r.url, r.retrieved_at)
        for award, path in AWARD_PAGES.items():
            try:
                r = self.fetcher.get(BASE + path)
            except Exception as e:  # keep going; record the gap
                league["errors"].append(f"{path}: {e}")
                continue
            if r:
                league["awards"].extend(parse_award_page(r.text, r.url, r.retrieved_at, award))
        r = self.fetcher.get(BASE + "/leagues/NBA_stats_per_game.html")
        if r:
            league["league_averages"] = parse_league_averages(r.text, r.url, r.retrieved_at)
        return league

    def collect_player(self, player: PlayerConfig, league: dict) -> dict:
        r = self.fetcher.get(player.bref_url, allow_404=False)
        bio = parse_bio(r.text, r.url, r.retrieved_at)
        tables = parse_player_tables(r.text, r.url, r.retrieved_at)
        frag = {"bio": bio, **tables, "game_logs": [], "gamelog_errors": []}
        if self.include_gamelogs:
            base = player.bref_url[:-5]  # strip .html
            reg_seasons = sorted({s["season"] for s in tables["seasons"] if s["stat_type"] == "regular_season"})
            for season in reg_seasons:
                end_year = int(season[:4]) + 1
                url = f"{base}/gamelog/{end_year}"
                try:
                    g = self.fetcher.get(url)
                    if g:
                        frag["game_logs"].extend(parse_gamelog(g.text, g.url, g.retrieved_at, "regular_season", season))
                except Exception as e:
                    frag["gamelog_errors"].append(f"{url}: {e}")
                    if "429" in str(e):
                        raise
            url = f"{base}/gamelog-playoffs/"
            try:
                g = self.fetcher.get(url)
                if g:
                    frag["game_logs"].extend(parse_gamelog(g.text, g.url, g.retrieved_at, "playoffs"))
            except Exception as e:
                frag["gamelog_errors"].append(f"{url}: {e}")
                if "429" in str(e):
                    raise
        return frag
