"""Data source interface + provenance helpers.

New sources (Kaggle dumps, public shot datasets, ...) implement `DataSource` and
return fragments of the canonical player dataset (see ingest/dataset.py). The
pipeline merges fragments, so sources stay independent of each other.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ...players import PlayerConfig
from ..http import PoliteFetcher


def provenance(source: str, source_url: str, retrieved_at: str, season: str | None = None,
               stat_type: str | None = None) -> dict:
    return {"source": source, "source_url": source_url, "season": season,
            "retrieved_at": retrieved_at, "stat_type": stat_type}


def season_from_end_year(y: int) -> str:
    """2016 -> '2015-16', 2000 -> '1999-00'."""
    return f"{y - 1}-{y % 100:02d}"


def end_year_from_season(season: str) -> int | None:
    """'2015-16' -> 2016, '1999-00' -> 2000."""
    try:
        start = int(season[:4])
        return start + 1
    except (ValueError, TypeError):
        return None


class DataSource(ABC):
    name: str = "abstract"
    homepage: str = ""
    terms_note: str = ""

    def __init__(self, fetcher: PoliteFetcher):
        self.fetcher = fetcher

    def collect_league(self) -> dict:
        """League-wide data shared by all players (award lists, champions, league averages)."""
        return {}

    @abstractmethod
    def collect_player(self, player: PlayerConfig, league: dict) -> dict:
        """Return a dataset fragment for one player."""
