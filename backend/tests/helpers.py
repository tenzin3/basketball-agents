"""Test helpers: a fetcher that serves SYNTHETIC fixture pages instead of the network."""
from __future__ import annotations

from pathlib import Path

from hoopcouncil.ingest.http import FetchResult
from hoopcouncil.players import PlayerConfig

FIX = Path(__file__).parent / "fixtures" / "html"
SYNTH = PlayerConfig(slug="synth", full_name="Synthetic Guard", bref_id="synthgu01", nba_id=1,
                     lineup_slot="PG", agent_name="SynthAgent", focus_areas=("testing",))

ROUTES = {
    "/players/s/synthgu01.html": "player.html",
    "/players/s/synthgu01/gamelog/2016": "gamelog_2016.html",
    "/players/s/synthgu01/gamelog-playoffs/": "gamelog_playoffs.html",
    "/playoffs/": "playoffs_index.html",
    "/awards/mvp.html": "awards_mvp.html",
    "/awards/all_league.html": "awards_all_league.html",
    "/leagues/NBA_stats_per_game.html": "league_averages.html",
}


class FixtureFetcher:
    def __init__(self, disallow_gamelogs: bool = False):
        self.requested = []
        self.disallow_gamelogs = disallow_gamelogs

    def allowed(self, url):
        return not (self.disallow_gamelogs and "/gamelog/" in url)

    def get(self, url, params=None, allow_404=True):
        self.requested.append(url)
        for suffix, name in ROUTES.items():
            if url.endswith(suffix):
                return FetchResult(url=url, status=200, text=(FIX / name).read_text(),
                                   retrieved_at="2026-10-07T00:00:00+00:00", from_cache=True)
        return None


_built = False


def ensure_fixtures():
    """Regenerate the synthetic fixtures once per test run so they never go stale."""
    global _built
    if not _built:
        from tests.fixtures.make_fixtures import build

        build()
        _built = True


def synthetic_dataset(disallow_gamelogs: bool = False):
    from hoopcouncil.ingest.dataset import assemble
    from hoopcouncil.ingest.sources.bref import BasketballReferenceSource

    ensure_fixtures()
    src = BasketballReferenceSource(FixtureFetcher(disallow_gamelogs))
    league = src.collect_league()
    frag = src.collect_player(SYNTH, league)
    return assemble(SYNTH, frag, league)
