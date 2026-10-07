"""Registry of the five fixed HoopCouncil players.

Only *identifiers* and agent configuration live here. No statistics, awards or
biographical facts are hard-coded: those come exclusively from ingested data.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PlayerConfig:
    slug: str                 # short key used across the app (curry, durant, ...)
    full_name: str
    bref_id: str              # Basketball Reference player id
    nba_id: int               # NBA.com stats person id
    lineup_slot: str          # default slot in the HoopCouncil lineup (can change per play)
    agent_name: str
    focus_areas: tuple = field(default_factory=tuple)

    @property
    def bref_url(self) -> str:
        return f"https://www.basketball-reference.com/players/{self.bref_id[0]}/{self.bref_id}.html"


PLAYERS: dict[str, PlayerConfig] = {
    "curry": PlayerConfig(
        slug="curry", full_name="Stephen Curry", bref_id="curryst01", nba_id=201939,
        lineup_slot="PG", agent_name="CurryAgent",
        focus_areas=("spacing", "shooting gravity", "movement", "screening interactions",
                     "pick-and-roll", "relocation", "defensive coverage manipulation"),
    ),
    "kobe": PlayerConfig(
        slug="kobe", full_name="Kobe Bryant", bref_id="bryanko01", nba_id=977,
        lineup_slot="SG", agent_name="KobeAgent",
        focus_areas=("isolation", "midrange creation", "post scoring", "difficult shot creation",
                     "late-clock situations", "footwork", "perimeter defense"),
    ),
    "jordan": PlayerConfig(
        slug="jordan", full_name="Michael Jordan", bref_id="jordami01", nba_id=893,
        lineup_slot="SF", agent_name="JordanAgent",
        focus_areas=("rim pressure", "midrange", "post-up scoring", "isolation", "transition",
                     "late-game creation", "perimeter defense"),
    ),
    "durant": PlayerConfig(
        slug="durant", full_name="Kevin Durant", bref_id="duranke01", nba_id=201142,
        lineup_slot="PF", agent_name="DurantAgent",
        focus_areas=("mismatch scoring", "isolation", "midrange", "pull-up shooting",
                     "size advantages", "weak-side scoring", "switch punishment"),
    ),
    "lebron": PlayerConfig(
        slug="lebron", full_name="LeBron James", bref_id="jamesle01", nba_id=2544,
        lineup_slot="C / Point Forward", agent_name="LeBronAgent",
        focus_areas=("playmaking", "rim pressure", "transition", "pick-and-roll",
                     "mismatch hunting", "passing reads", "offensive orchestration"),
    ),
}

# Display order on the main page / court.
DISPLAY_ORDER = ["curry", "kobe", "jordan", "durant", "lebron"]


def get_player(key: str) -> PlayerConfig:
    """Resolve a slug, full name, last name or bref id to a PlayerConfig."""
    k = key.strip().lower()
    if k in PLAYERS:
        return PLAYERS[k]
    for p in PLAYERS.values():
        if k in (p.full_name.lower(), p.bref_id, p.full_name.split()[-1].lower(), p.agent_name.lower()):
            return p
    if k == "james":
        return PLAYERS["lebron"]
    if k == "bryant":
        return PLAYERS["kobe"]
    raise KeyError(f"Unknown player: {key}")
