"""Generate SYNTHETIC Basketball-Reference-style HTML fixtures for parser tests.

Every number here is invented for testing the parsers and derivations. The player
("Synthetic Guard", id synthgu01) does not exist. Nothing in this file is used as data
for the real players.
"""
from __future__ import annotations

import random
from pathlib import Path

OUT = Path(__file__).parent / "html"

PLAYER_ID = "synthgu01"
SEASONS = [  # (season, team, end_year, games, minutes, awards)
    ("2012-13", "AAA", 2013, 70, 2300, "ROY-1"),
    ("2014-15", "AAA", 2015, 30, 1000, ""),
    ("2014-15", "BBB", 2015, 40, 1400, ""),
    ("2015-16", "BBB", 2016, 79, 2700, "MVP-1,AS,NBA1,DEF2"),
]
rng = random.Random(7)


def line(g, mp):
    fga = int(mp * 0.4)
    fg3a = int(fga * 0.4)
    fg2a = fga - fg3a
    fg3 = int(fg3a * 0.41)
    fg2 = int(fg2a * 0.52)
    fta = int(mp * 0.12)
    ft = int(fta * 0.9)
    orb, drb = int(mp * 0.015), int(mp * 0.1)
    t = dict(g=g, gs=g, mp=mp, fg=fg2 + fg3, fga=fga, fg3=fg3, fg3a=fg3a, fg2=fg2, fg2a=fg2a, ft=ft, fta=fta,
             orb=orb, drb=drb, trb=orb + drb, ast=int(mp * 0.18), stl=int(mp * 0.04), blk=int(mp * 0.006),
             tov=int(mp * 0.08), pf=int(mp * 0.05))
    t["pts"] = 2 * t["fg2"] + 3 * t["fg3"] + t["ft"]
    return t


def add(a, b):
    return {k: a.get(k, 0) + b[k] for k in b}


def pct(m, a):
    return "" if not a else f"{m / a:.3f}".lstrip("0")


BASIC_LABELS = ["G", "GS", "MP", "FG", "FGA", "FG%", "3P", "3PA", "3P%", "2P", "2PA", "2P%", "eFG%", "FT", "FTA",
                "FT%", "ORB", "DRB", "TRB", "AST", "STL", "BLK", "TOV", "PF", "PTS"]


def basic_cells(t, per_game, bold_pts=False):
    g = t["g"]

    def v(k):
        x = t[k]
        return f"{x / g:.1f}" if per_game else str(x)

    efg = (t["fg"] + 0.5 * t["fg3"]) / t["fga"]
    vals = [str(g), str(t["gs"]), v("mp"), v("fg"), v("fga"), pct(t["fg"], t["fga"]), v("fg3"), v("fg3a"),
            pct(t["fg3"], t["fg3a"]), v("fg2"), v("fg2a"), pct(t["fg2"], t["fg2a"]), f"{efg:.3f}".lstrip("0"),
            v("ft"), v("fta"), pct(t["ft"], t["fta"]), v("orb"), v("drb"), v("trb"), v("ast"), v("stl"), v("blk"),
            v("tov"), v("pf"), v("pts")]
    cells = []
    for lab, val in zip(BASIC_LABELS, vals):
        if lab == "PTS" and bold_pts:
            cells.append(f'<td class="right" data-stat="pts_per_g"><strong>{val}</strong></td>')
        else:
            cells.append(f'<td class="right" data-stat="x">{val}</td>')
    return "".join(cells)


def team_cell(team, end_year):
    if team.endswith("TM"):
        return f'<td data-stat="team_name_abbr">{team}</td>'
    return f'<td data-stat="team_name_abbr"><a href="/teams/{team}/{end_year}.html">{team}</a></td>'


def head(labels, extra_first=("Season", "Age", "Team", "Lg", "Pos"), over=None):
    th = "".join(f'<th data-stat="{l.lower()}">{l}</th>' for l in list(extra_first) + labels)
    over_row = ""
    if over:
        over_row = '<tr class="over_header">' + "".join(
            f'<th colspan="{n}">{name}</th>' for name, n in over) + "</tr>"
    return f"<thead>{over_row}<tr>{th}</tr></thead>"


def season_rows(rows, per_game, playoffs=False):
    """rows: list of (season, team, end_year, totals, awards, bold)"""
    out = []
    for season, team, ey, t, awards, bold in rows:
        out.append(f'<tr><th data-stat="year_id"><a href="/x">{season}</a></th><td>{int(season[:4]) - 1990}</td>'
                   f'{team_cell(team, ey)}<td>NBA</td><td>PG</td>{basic_cells(t, per_game, bold)}'
                   + (f'<td data-stat="awards">{awards}</td>' if not playoffs else "") + "</tr>")
    return "".join(out)


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    reg = {}
    for season, team, ey, g, mp, aw in SEASONS:
        reg[(season, team)] = (ey, line(g, mp), aw)
    tot1415 = add(reg[("2014-15", "AAA")][1], reg[("2014-15", "BBB")][1])
    rows = [
        ("2012-13", "AAA", 2013, reg[("2012-13", "AAA")][1], "ROY-1", False),
        ("2014-15", "2TM", 2015, tot1415, "", False),
        ("2014-15", "AAA", 2015, reg[("2014-15", "AAA")][1], "", False),
        ("2014-15", "BBB", 2015, reg[("2014-15", "BBB")][1], "", False),
        ("2015-16", "BBB", 2016, reg[("2015-16", "BBB")][1], "MVP-1,AS,NBA1,DEF2", True),
    ]
    career = reg[("2012-13", "AAA")][1]
    career = add(career, tot1415)
    career = add(career, reg[("2015-16", "BBB")][1])
    dnp = '<tr><th data-stat="year_id">2013-14</th><td>28</td><td colspan="27">Did not play (injury)</td></tr>'
    labels = BASIC_LABELS + ["Awards"]
    rows_html = season_rows(rows[:1], True) + dnp + season_rows(rows[1:], True)
    foot = f'<tfoot><tr><th>Career</th><td></td><td></td><td>NBA</td><td></td>{basic_cells(career, True)}<td></td></tr></tfoot>'
    per_game = f'<table id="per_game_stats"><caption>Per Game Table</caption>{head(labels)}<tbody>{rows_html}</tbody>{foot}</table>'
    # inject repeated header row like BR does mid-table
    per_game = per_game.replace(dnp, dnp + '<tr class="thead"><th>Season</th></tr>')
    totals_rows = season_rows(rows, False)
    totals = (f'<table id="totals_stats"><caption>Totals Table</caption>{head(labels)}<tbody>{totals_rows}</tbody>'
              f'<tfoot><tr><th>3 Yrs</th><td></td><td></td><td>NBA</td><td></td>{basic_cells(career, False)}<td></td></tr>'
              f'<tr><th>82 Game Avg</th><td></td><td></td><td></td><td></td>{basic_cells(career, True)}<td></td></tr></tfoot></table>')
    # advanced (inside a comment, with an empty spacer column)
    adv_labels = ["G", "MP", "PER", "TS%", "3PAr", "FTr", "ORB%", "DRB%", "TRB%", "AST%", "STL%", "BLK%", "TOV%",
                  "USG%", "", "OWS", "DWS", "WS", "WS/48", "", "OBPM", "DBPM", "BPM", "VORP"]
    adv_vals = {
        "2012-13": [70, 2300, 16.1, ".561", ".400", ".300", 2.1, 10.2, 6.1, 30.5, 1.9, 0.4, 14.0, 24.0, "", 3.1, 1.9, 5.0, ".104", "", 1.0, -0.5, 0.5, 1.4],
        "2014-15": [70, 2400, 18.0, ".580", ".410", ".310", 2.0, 10.0, 6.0, 31.0, 2.0, 0.5, 13.5, 26.0, "", 5.0, 2.0, 7.0, ".140", "", 3.0, 0.0, 3.0, 2.9],
        "2015-16": [79, 2700, 26.0, ".640", ".450", ".280", 2.2, 11.0, 6.5, 33.0, 2.4, 0.5, 12.5, 31.0, "", 12.0, 3.0, 15.0, ".267", "", 9.5, 0.5, 10.0, 7.5],
    }
    adv_rows = ""
    for season, team, ey in (("2012-13", "AAA", 2013), ("2014-15", "2TM", 2015), ("2015-16", "BBB", 2016)):
        tds = "".join(f"<td>{v}</td>" for v in adv_vals[season])
        adv_rows += f'<tr><th>{season}</th><td>{int(season[:4]) - 1990}</td>{team_cell(team, ey)}<td>NBA</td><td>PG</td>{tds}</tr>'
    adv = f'<div id="all_advanced"><!--<table id="advanced"><caption>Advanced Table</caption>{head(adv_labels)}<tbody>{adv_rows}</tbody></table>--></div>'
    # shooting with over headers and duplicate labels
    sh_labels = ["G", "MP", "FG%", "Dist.", "2P", "0-3", "3-10", "10-16", "16-3P", "3P", "2P", "0-3", "3-10",
                 "10-16", "16-3P", "3P", "2P", "3P", "%FGA", "#", "%3PA", "3P%"]
    over = [("", 7), ("", 2), ("% of FGA by Distance", 6), ("FG% by Distance", 6), ("% of FG Ast'd", 2),
            ("Dunks", 2), ("Corner 3s", 2)]
    sh = "".join(f"<td>{v}</td>" for v in [79, 2700, ".500", "16.0", ".550", ".200", ".100", ".080", ".170", ".450",
                                            ".560", ".700", ".450", ".480", ".470", ".440", ".400", ".500", ".010", 5, ".150", ".420"])
    shooting = (f'<!--<table id="shooting"><caption>Shooting Table</caption>{head(sh_labels, over=over)}<tbody>'
                f'<tr><th>2015-16</th><td>27</td>{team_cell("BBB", 2016)}<td>NBA</td><td>PG</td>{sh}</tr></tbody></table>-->')
    pbp_labels = ["G", "MP", "PG%", "SG%", "SF%", "PF%", "C%", "OnCourt", "On-Off", "BadPass", "LostBall", "Shoot",
                  "Off.", "Shoot", "Off.", "PGA", "And1", "Blkd"]
    pbp_over = [("", 7), ("Position Estimate", 5), ("+/- Per 100 Poss.", 2), ("Turnovers", 2),
                ("Fouls Committed", 2), ("Fouls Drawn", 2), ("Misc.", 3)]
    pv = "".join(f"<td>{v}</td>" for v in [79, 2700, "90%", "10%", "", "", "", "+12.0", "+15.5", 120, 80, 50, 10, 200, 30, 900, 40, 30])
    pbp = (f'<!--<table id="pbp_stats"><caption>Play-by-Play Table</caption>{head(pbp_labels, over=pbp_over)}<tbody>'
           f'<tr><th>2015-16</th><td>27</td>{team_cell("BBB", 2016)}<td>NBA</td><td>PG</td>{pv}</tr></tbody></table>-->')
    # playoffs (OLD table ids, to test fallbacks). 2014-15 with BBB, 2015-16 with BBB.
    po15, po16 = line(10, 380), line(20, 760)
    po_rows = season_rows([("2014-15", "BBB", 2015, po15, "", False), ("2015-16", "BBB", 2016, po16, "", False)], True, playoffs=True)
    po_car = add(po15, po16)
    po = (f'<!--<table id="playoffs_per_game"><caption>Playoffs Per Game Table</caption>{head(BASIC_LABELS)}<tbody>{po_rows}</tbody>'
          f'<tfoot><tr><th>Career</th><td></td><td></td><td>NBA</td><td></td>{basic_cells(po_car, True)}</tr></tfoot></table>-->')
    po_tot = (f'<!--<table id="playoffs_totals"><caption>Playoffs Totals Table</caption>{head(BASIC_LABELS)}<tbody>'
              f'{season_rows([("2014-15", "BBB", 2015, po15, "", False), ("2015-16", "BBB", 2016, po16, "", False)], False, playoffs=True)}</tbody>'
              f'<tfoot><tr><th>Career</th><td></td><td></td><td>NBA</td><td></td>{basic_cells(po_car, False)}</tr></tfoot></table>-->')
    po_adv_rows = ""
    for season, ey, vals in (("2014-15", 2015, [10, 380, 15.0, ".560", ".400", ".300", 2.0, 10.0, 6.0, 28.0, 2.0, 0.5, 14.0, 25.0, "", 0.5, 0.3, 0.8, ".101", "", 1.5, 0.0, 1.5, 0.2]),
                             ("2015-16", 2016, [20, 760, 22.0, ".610", ".440", ".290", 2.0, 11.0, 6.5, 31.0, 2.2, 0.5, 13.0, 30.0, "", 2.5, 0.8, 3.3, ".208", "", 7.0, 0.5, 7.5, 1.1])):
        po_adv_rows += f'<tr><th>{season}</th><td>{int(season[:4]) - 1990}</td>{team_cell("BBB", ey)}<td>NBA</td><td>PG</td>' + "".join(f"<td>{v}</td>" for v in vals) + "</tr>"
    po_adv = f'<!--<table id="playoffs_advanced"><caption>Playoffs Advanced</caption>{head(adv_labels)}<tbody>{po_adv_rows}</tbody></table>-->'
    meta = ('<div id="meta"><h1><span>Synthetic Guard</span></h1>'
            '<p><strong>Position:</strong> Point Guard and Shooting Guard ▪ <strong>Shoots:</strong> Right</p>'
            '<p><span>6-3</span>, <span>190lb</span> (191cm, 86kg)</p>'
            '<p><strong>Born:</strong> <span id="necro-birth" data-birth="1990-01-01">January 1, 1990</span></p>'
            '<p><strong>Draft:</strong> <a>Team Alpha</a>, 1st round (5th pick, 5th overall), <a>2012 NBA Draft</a></p>'
            '</div><ul id="bling"><li>1x MVP</li><li>1x All Star</li><li>1x NBA Champ</li><li>2015-16 Scoring Champ</li></ul>')
    ser_rows = "".join(
        f'<tr><th data-stat="year_id">2015-16</th><td>26</td><td><a href="/teams/BBB/2016.html">BBB</a></td><td>NBA</td>'
        f'<td data-stat="ps_round">{code}</td><td><a href="/teams/{opp}/2016.html">{opp}</a></td><td>W (4-1)</td></tr>'
        for code, opp in (("WC1", "XXX"), ("WCS", "YYY"), ("WCF", "ZZZ"), ("FIN", "CCC")))
    series = (f'<!--<table id="playoffs_series"><thead><tr><th>Season</th><th>Age</th><th>Team</th><th>Lg</th><th>Round</th>'
              f'<th>Opp</th><th>W/L</th></tr></thead><tbody>{ser_rows}</tbody></table>-->')
    page = f"<html><body>{meta}{series}{per_game}{totals}{adv}{shooting}{pbp}{po}{po_tot}{po_adv}</body></html>"
    (OUT / "player.html").write_text(page)

    # playoff game log: 2014-15 two series, 2015-16 four series (Finals vs CCC)
    def glrow(d, team, opp, at, res, pts):
        y, m, dd = d.split("-")
        return (f'<tr><th>{rng.randint(1, 999)}</th><td data-stat="date"><a href="/boxscores/{y}{m}{dd}0{opp}.html">{d}</a></td>'
                f'<td data-stat="team_name_abbr"><a href="/teams/{team}/{y}.html">{team}</a></td><td data-stat="game_location">{at}</td>'
                f'<td data-stat="opp_name_abbr"><a href="/teams/{opp}/{y}.html">{opp}</a></td><td data-stat="game_result">{res}</td>'
                f'<td>1</td><td>36:30</td><td>10</td><td>20</td><td>.500</td><td>4</td><td>9</td><td>.444</td><td>{pts - 24}</td><td>4</td>'
                f'<td>5</td><td>7</td><td>{pts}</td></tr>')
    gl_head = ('<thead><tr><th>Rk</th><th>Date</th><th>Team</th><th data-stat="game_location"></th><th>Opp</th>'
               '<th data-stat="game_result">Result</th><th>GS</th><th>MP</th><th>FG</th><th>FGA</th><th>FG%</th><th>3P</th>'
               '<th>3PA</th><th>3P%</th><th>FT</th><th>TRB</th><th>AST</th><th>TOV</th><th>PTS</th></tr></thead>')
    games = []
    sched = [("2015-04-20", "XXX"), ("2015-04-22", "XXX"), ("2015-04-25", "XXX"), ("2015-05-03", "YYY"), ("2015-05-05", "YYY"),
             ("2016-04-18", "XXX"), ("2016-04-20", "XXX"), ("2016-05-01", "YYY"), ("2016-05-03", "YYY"),
             ("2016-05-17", "ZZZ"), ("2016-05-19", "ZZZ"), ("2016-06-02", "CCC"), ("2016-06-05", "CCC"), ("2016-06-08", "CCC")]
    for i, (d, opp) in enumerate(sched):
        games.append(glrow(d, "BBB", opp, "@" if i % 2 else "", "W 100-90" if i % 3 else "L 95-99", 30 + i))
    games.insert(3, '<tr><th></th><td data-stat="date">2015-04-27</td><td colspan="20">Inactive</td></tr>')
    (OUT / "gamelog_playoffs.html").write_text(
        f'<html><body><table id="player_game_log_post">{gl_head}<tbody>{"".join(games)}</tbody></table></body></html>')
    reg_games = "".join(glrow(f"2015-1{m}-0{d}", "BBB", "XXX", "", "W 101-99", 30 + d) for m in (1, 2) for d in range(1, 4))
    (OUT / "gamelog_2016.html").write_text(
        f'<html><body><table id="player_game_log_reg">{gl_head}<tbody>{reg_games}</tbody></table></body></html>')
    # playoffs index
    idx = ('<table id="champions_index"><thead><tr><th>Year</th><th>Lg</th><th>Champion</th><th>Runner-Up</th>'
           '<th>Finals MVP</th></tr></thead><tbody>'
           '<tr><th><a href="/playoffs/NBA_2016.html">2016</a></th><td>NBA</td><td><a href="/teams/BBB/2016.html">Team Bravo</a></td>'
           '<td><a href="/teams/CCC/2016.html">Team Charlie</a></td><td><a href="/players/s/synthgu01.html">S. Guard</a></td></tr>'
           '<tr><th>2015</th><td>NBA</td><td><a href="/teams/QQQ/2015.html">Q</a></td><td><a href="/teams/RRR/2015.html">R</a></td>'
           '<td><a href="/players/o/other01.html">Other</a></td></tr></tbody></table>')
    (OUT / "playoffs_index.html").write_text(f"<html><body>{idx}</body></html>")
    mvp = ('<table id="mvp_NBA"><thead><tr><th>Season</th><th>Lg</th><th>Player</th></tr></thead><tbody>'
           '<tr><th>2015-16</th><td>NBA</td><td><a href="/players/s/synthgu01.html">Synthetic Guard</a></td></tr>'
           '<tr><th>2014-15</th><td>NBA</td><td><a href="/players/o/other01.html">Other</a></td></tr></tbody></table>')
    (OUT / "awards_mvp.html").write_text(f"<html><body>{mvp}</body></html>")
    al = ('<table id="awards_all_league"><thead><tr><th>Season</th><th>Lg</th><th>Tm</th><th></th><th></th></tr></thead><tbody>'
          '<tr><th>2015-16</th><td>NBA</td><td>1st</td><td><a href="/players/s/synthgu01.html">S</a></td><td><a href="/players/o/other01.html">O</a></td></tr>'
          '<tr><th>2014-15</th><td>NBA</td><td>3rd</td><td><a href="/players/s/synthgu01.html">S</a></td></tr></tbody></table>')
    (OUT / "awards_all_league.html").write_text(f"<html><body>{al}</body></html>")
    la_rows = "".join(
        f'<tr><th>{i}</th><td><a>{s}</a></td><td>NBA</td><td>100.0</td><td>83.0</td><td>{f3}</td><td>35.0</td><td>.350</td><td>.540</td><td>.500</td><td>.760</td></tr>'
        for i, (s, f3) in enumerate([("2015-16", "24.1"), ("2014-15", "22.4"), ("2012-13", "20.0")], 1))
    la = ('<table id="stats"><thead><tr><th>Rk</th><th>Season</th><th>Lg</th><th>PTS</th><th>FGA</th><th>3PA</th><th>FTA</th>'
          f'<th>3P%</th><th>TS%</th><th>eFG%</th><th>FT%</th></tr></thead><tbody>{la_rows}</tbody></table>')
    (OUT / "league_averages.html").write_text(f"<html><body>{la}</body></html>")


if __name__ == "__main__":
    build()
    print("fixtures written to", OUT)
