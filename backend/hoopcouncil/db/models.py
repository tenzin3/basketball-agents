"""SQLAlchemy 2.0 models. PostgreSQL is the target (JSONB); SQLite also works for quick local runs.

Every statistical row carries provenance columns (source, source_url, retrieved_at,
stat_type, season). Derived rows (aggregates, peak scores, archetypes, phases) record
the method/rule that produced them instead.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JSONType = JSON().with_variant(JSONB(), "postgresql")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ProvenanceMixin:
    source: Mapped[str | None] = mapped_column(String(80))
    source_url: Mapped[str | None] = mapped_column(Text)
    retrieved_at: Mapped[str | None] = mapped_column(String(40))
    stat_type: Mapped[str | None] = mapped_column(String(32), index=True)


class DataSource(Base):
    __tablename__ = "data_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    homepage: Mapped[str | None] = mapped_column(Text)
    terms_note: Mapped[str | None] = mapped_column(Text)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[dict | None] = mapped_column(JSONType)


class Player(Base):
    __tablename__ = "players"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    bref_id: Mapped[str | None] = mapped_column(String(16))
    nba_id: Mapped[int | None] = mapped_column(Integer)
    height_in: Mapped[int | None] = mapped_column(Integer)
    height_cm: Mapped[int | None] = mapped_column(Integer)
    weight_lb: Mapped[int | None] = mapped_column(Integer)
    weight_kg: Mapped[int | None] = mapped_column(Integer)
    wingspan_in: Mapped[float | None] = mapped_column(Float)
    primary_position: Mapped[str | None] = mapped_column(String(40))
    secondary_positions: Mapped[list | None] = mapped_column(JSONType)
    shoots: Mapped[str | None] = mapped_column(String(8))
    birth_date: Mapped[str | None] = mapped_column(String(10))
    draft_year: Mapped[int | None] = mapped_column(Integer)
    draft_team: Mapped[str | None] = mapped_column(String(80))
    draft_round: Mapped[int | None] = mapped_column(Integer)
    draft_pick: Mapped[int | None] = mapped_column(Integer)
    hall_of_fame_inducted: Mapped[int | None] = mapped_column(Integer)
    teams: Mapped[list | None] = mapped_column(JSONType)
    first_season: Mapped[str | None] = mapped_column(String(7))
    last_season: Mapped[str | None] = mapped_column(String(7))
    seasons_played: Mapped[int | None] = mapped_column(Integer)
    bio_provenance: Mapped[dict | None] = mapped_column(JSONType)
    bling: Mapped[list | None] = mapped_column(JSONType)          # site badges, used for cross-checks only
    raw_dataset_meta: Mapped[dict | None] = mapped_column(JSONType)  # sources, tables found, ingest errors
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    seasons: Mapped[list["PlayerSeason"]] = relationship(back_populates="player", cascade="all, delete-orphan")


class PlayerSeason(ProvenanceMixin, Base):
    """One row per (season, stat_type, team). Multi-team seasons have a combined row
    (is_combined) plus team split rows (is_team_split)."""
    __tablename__ = "player_seasons"
    __table_args__ = (UniqueConstraint("player_id", "season", "stat_type", "team"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    season: Mapped[str] = mapped_column(String(7), index=True)
    team: Mapped[str | None] = mapped_column(String(8))
    team_text: Mapped[str | None] = mapped_column(String(16))
    teams: Mapped[list | None] = mapped_column(JSONType)
    age: Mapped[float | None] = mapped_column(Float)
    league: Mapped[str | None] = mapped_column(String(8))
    pos: Mapped[str | None] = mapped_column(String(16))
    is_combined: Mapped[bool] = mapped_column(Boolean, default=True)
    is_team_split: Mapped[bool] = mapped_column(Boolean, default=False)
    awards_text: Mapped[str | None] = mapped_column(Text)
    league_leader_in: Mapped[list | None] = mapped_column(JSONType)
    peak_score: Mapped[float | None] = mapped_column(Float)
    peak_components: Mapped[dict | None] = mapped_column(JSONType)

    player: Mapped[Player] = relationship(back_populates="seasons")


class _StatLine(ProvenanceMixin):
    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[str] = mapped_column(String(7), index=True)
    team: Mapped[str | None] = mapped_column(String(8))
    is_combined: Mapped[bool] = mapped_column(Boolean, default=True)
    g: Mapped[int | None] = mapped_column(Integer)
    gs: Mapped[int | None] = mapped_column(Integer)
    mp_per_g: Mapped[float | None] = mapped_column(Float)
    pts_per_g: Mapped[float | None] = mapped_column(Float)
    trb_per_g: Mapped[float | None] = mapped_column(Float)
    ast_per_g: Mapped[float | None] = mapped_column(Float)
    stl_per_g: Mapped[float | None] = mapped_column(Float)
    blk_per_g: Mapped[float | None] = mapped_column(Float)
    tov_per_g: Mapped[float | None] = mapped_column(Float)
    fga_per_g: Mapped[float | None] = mapped_column(Float)
    fg_pct: Mapped[float | None] = mapped_column(Float)
    fg2a_per_g: Mapped[float | None] = mapped_column(Float)
    fg2_pct: Mapped[float | None] = mapped_column(Float)
    fg3a_per_g: Mapped[float | None] = mapped_column(Float)
    fg3_pct: Mapped[float | None] = mapped_column(Float)
    fta_per_g: Mapped[float | None] = mapped_column(Float)
    ft_pct: Mapped[float | None] = mapped_column(Float)
    efg_pct: Mapped[float | None] = mapped_column(Float)
    per_game: Mapped[dict | None] = mapped_column(JSONType)   # full per-game line as published
    totals: Mapped[dict | None] = mapped_column(JSONType)     # full totals line as published
    per_poss: Mapped[dict | None] = mapped_column(JSONType)   # per-100 line incl. ORtg/DRtg


class PlayerRegularSeasonStats(_StatLine, Base):
    __tablename__ = "player_regular_season_stats"
    __table_args__ = (UniqueConstraint("player_id", "season", "team"),)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)


class PlayerPlayoffStats(_StatLine, Base):
    __tablename__ = "player_playoff_stats"
    __table_args__ = (UniqueConstraint("player_id", "season", "team"),)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)


class PlayerFinalsStats(ProvenanceMixin, Base):
    """Per-series aggregates for nba_finals / conference_finals, computed from playoff game logs."""
    __tablename__ = "player_finals_stats"
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    season: Mapped[str] = mapped_column(String(7))
    playoff_round: Mapped[str] = mapped_column(String(32))
    team: Mapped[str | None] = mapped_column(String(8))
    opponent: Mapped[str | None] = mapped_column(String(8))
    games: Mapped[int] = mapped_column(Integer)
    wins: Mapped[int | None] = mapped_column(Integer)
    losses: Mapped[int | None] = mapped_column(Integer)
    round_confidence: Mapped[str | None] = mapped_column(String(16))
    totals: Mapped[dict | None] = mapped_column(JSONType)
    per_game: Mapped[dict | None] = mapped_column(JSONType)
    method: Mapped[str | None] = mapped_column(Text)


class PlayerAdvancedStats(ProvenanceMixin, Base):
    __tablename__ = "player_advanced_stats"
    __table_args__ = (UniqueConstraint("player_id", "season", "stat_type", "team"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    season: Mapped[str] = mapped_column(String(7), index=True)
    team: Mapped[str | None] = mapped_column(String(8))
    is_combined: Mapped[bool] = mapped_column(Boolean, default=True)
    per: Mapped[float | None] = mapped_column(Float)
    ts_pct: Mapped[float | None] = mapped_column(Float)
    usg_pct: Mapped[float | None] = mapped_column(Float)
    ast_pct: Mapped[float | None] = mapped_column(Float)
    trb_pct: Mapped[float | None] = mapped_column(Float)
    tov_pct: Mapped[float | None] = mapped_column(Float)
    stl_pct: Mapped[float | None] = mapped_column(Float)
    blk_pct: Mapped[float | None] = mapped_column(Float)
    ows: Mapped[float | None] = mapped_column(Float)
    dws: Mapped[float | None] = mapped_column(Float)
    ws: Mapped[float | None] = mapped_column(Float)
    ws_per_48: Mapped[float | None] = mapped_column(Float)
    obpm: Mapped[float | None] = mapped_column(Float)
    dbpm: Mapped[float | None] = mapped_column(Float)
    bpm: Mapped[float | None] = mapped_column(Float)
    vorp: Mapped[float | None] = mapped_column(Float)
    ortg: Mapped[float | None] = mapped_column(Float)
    drtg: Mapped[float | None] = mapped_column(Float)
    values: Mapped[dict | None] = mapped_column(JSONType)     # full advanced line
    pbp: Mapped[dict | None] = mapped_column(JSONType)        # play-by-play table (positions, on/off, and-1s...)


class PlayerShotProfile(ProvenanceMixin, Base):
    __tablename__ = "player_shot_profiles"
    __table_args__ = (UniqueConstraint("player_id", "season", "stat_type", "team"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    season: Mapped[str] = mapped_column(String(7), index=True)
    team: Mapped[str | None] = mapped_column(String(8))
    avg_shot_distance_ft: Mapped[float | None] = mapped_column(Float)
    rim_frequency: Mapped[float | None] = mapped_column(Float)            # share of FGA 0-3 ft
    short_midrange_frequency: Mapped[float | None] = mapped_column(Float) # 3-10 ft
    midrange_frequency: Mapped[float | None] = mapped_column(Float)       # 10 ft to 3P line
    long_midrange_frequency: Mapped[float | None] = mapped_column(Float)  # 16 ft to 3P line
    three_point_frequency: Mapped[float | None] = mapped_column(Float)
    corner_three_share_of_3pa: Mapped[float | None] = mapped_column(Float)
    rim_fg_pct: Mapped[float | None] = mapped_column(Float)
    midrange_fg_pct: Mapped[float | None] = mapped_column(Float)
    three_fg_pct: Mapped[float | None] = mapped_column(Float)
    corner_three_fg_pct: Mapped[float | None] = mapped_column(Float)
    assisted_share_2p: Mapped[float | None] = mapped_column(Float)
    assisted_share_3p: Mapped[float | None] = mapped_column(Float)
    catch_and_shoot_frequency: Mapped[float | None] = mapped_column(Float)  # tracking era only
    pull_up_frequency: Mapped[float | None] = mapped_column(Float)          # tracking era only
    values: Mapped[dict | None] = mapped_column(JSONType)                   # full shooting line


class PlayerTrackingShots(ProvenanceMixin, Base):
    __tablename__ = "player_tracking_shots"
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    season: Mapped[str] = mapped_column(String(7))
    category: Mapped[str] = mapped_column(String(40))
    label: Mapped[str | None] = mapped_column(String(60))
    values: Mapped[dict | None] = mapped_column(JSONType)


class PlayerPlayType(ProvenanceMixin, Base):
    __tablename__ = "player_play_types"
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    season: Mapped[str] = mapped_column(String(7))
    play_type: Mapped[str] = mapped_column(String(32))
    frequency: Mapped[float | None] = mapped_column(Float)
    ppp: Mapped[float | None] = mapped_column(Float)
    percentile: Mapped[float | None] = mapped_column(Float)
    possessions: Mapped[float | None] = mapped_column(Float)
    values: Mapped[dict | None] = mapped_column(JSONType)


class PlayerClutchStats(ProvenanceMixin, Base):
    __tablename__ = "player_clutch_stats"
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    season: Mapped[str] = mapped_column(String(7))
    definition: Mapped[str | None] = mapped_column(Text)
    gp: Mapped[int | None] = mapped_column(Integer)
    minutes: Mapped[float | None] = mapped_column(Float)
    pts: Mapped[float | None] = mapped_column(Float)
    fga: Mapped[float | None] = mapped_column(Float)
    fg_pct: Mapped[float | None] = mapped_column(Float)
    fg3a: Mapped[float | None] = mapped_column(Float)
    fg3_pct: Mapped[float | None] = mapped_column(Float)
    fta: Mapped[float | None] = mapped_column(Float)
    ft_pct: Mapped[float | None] = mapped_column(Float)
    ast: Mapped[float | None] = mapped_column(Float)
    tov: Mapped[float | None] = mapped_column(Float)
    plus_minus: Mapped[float | None] = mapped_column(Float)
    values: Mapped[dict | None] = mapped_column(JSONType)


class PlayerGameLog(ProvenanceMixin, Base):
    __tablename__ = "player_game_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    season: Mapped[str] = mapped_column(String(7), index=True)
    game_date: Mapped[str] = mapped_column(String(10))
    team: Mapped[str | None] = mapped_column(String(8))
    opponent: Mapped[str | None] = mapped_column(String(8))
    home: Mapped[bool | None] = mapped_column(Boolean)
    result: Mapped[str | None] = mapped_column(String(1))
    margin: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(String(80))
    series_index: Mapped[int | None] = mapped_column(Integer)
    playoff_round: Mapped[str | None] = mapped_column(String(32))
    round_confidence: Mapped[str | None] = mapped_column(String(16))
    mp: Mapped[float | None] = mapped_column(Float)
    pts: Mapped[int | None] = mapped_column(Integer)
    trb: Mapped[int | None] = mapped_column(Integer)
    ast: Mapped[int | None] = mapped_column(Integer)
    fg: Mapped[int | None] = mapped_column(Integer)
    fga: Mapped[int | None] = mapped_column(Integer)
    fg3: Mapped[int | None] = mapped_column(Integer)
    fg3a: Mapped[int | None] = mapped_column(Integer)
    ft: Mapped[int | None] = mapped_column(Integer)
    fta: Mapped[int | None] = mapped_column(Integer)
    stats: Mapped[dict | None] = mapped_column(JSONType)
    boxscore_url: Mapped[str | None] = mapped_column(Text)


class PlayerAchievement(ProvenanceMixin, Base):
    __tablename__ = "player_achievements"
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    achievement_type: Mapped[str] = mapped_column(String(64), index=True)
    season: Mapped[str | None] = mapped_column(String(7))
    count: Mapped[int] = mapped_column(Integer, default=1)
    detail: Mapped[dict | None] = mapped_column(JSONType)
    derived_from: Mapped[str | None] = mapped_column(Text)
    corroborated_by: Mapped[list | None] = mapped_column(JSONType)


class PlayerRecord(Base):
    """Raw statistical facts (milestones). `kind`='fact' rows are computed from stored data only;
    historical interpretation is never generated by the pipeline."""
    __tablename__ = "player_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16), default="fact")
    key: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(Text)
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(24))
    stat_type: Mapped[str | None] = mapped_column(String(32))
    season: Mapped[str | None] = mapped_column(String(7))
    computed_from: Mapped[str | None] = mapped_column(Text)


class PlayerCareerAggregate(Base):
    __tablename__ = "player_career_aggregates"
    __table_args__ = (UniqueConstraint("player_id", "scope", "stat_type"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    scope: Mapped[str] = mapped_column(String(64))       # career | phase:<name>
    stat_type: Mapped[str] = mapped_column(String(32))   # regular_season | playoffs | nba_finals | conference_finals
    values: Mapped[dict] = mapped_column(JSONType)       # totals, per_game, per36, efficiency
    method: Mapped[str | None] = mapped_column(Text)


class PlayerCareerPhase(Base):
    __tablename__ = "player_career_phases"
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    phase_type: Mapped[str] = mapped_column(String(24))  # team_stint | statistical
    name: Mapped[str] = mapped_column(String(80))
    start_season: Mapped[str] = mapped_column(String(7))
    end_season: Mapped[str] = mapped_column(String(7))
    seasons: Mapped[list] = mapped_column(JSONType)
    summary: Mapped[dict | None] = mapped_column(JSONType)
    method: Mapped[str | None] = mapped_column(Text)


class PlayerArchetype(Base):
    __tablename__ = "player_archetypes"
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    archetype: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24))      # supported | not_supported | insufficient_data
    score: Mapped[float | None] = mapped_column(Float)
    evidence: Mapped[list | None] = mapped_column(JSONType)
    rule: Mapped[str | None] = mapped_column(Text)


class PlayerDerivedProfile(Base):
    """strengths / limitations / shot profile summary / play-type summary / data quality."""
    __tablename__ = "player_derived_profiles"
    __table_args__ = (UniqueConstraint("player_id", "key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    value: Mapped[dict | list] = mapped_column(JSONType)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LeagueSeasonAverage(ProvenanceMixin, Base):
    __tablename__ = "league_season_averages"
    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[str] = mapped_column(String(7), unique=True)
    values: Mapped[dict] = mapped_column(JSONType)


class LeagueChampion(ProvenanceMixin, Base):
    __tablename__ = "league_champions"
    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[str] = mapped_column(String(7), unique=True)
    champion: Mapped[str | None] = mapped_column(String(8))
    runner_up: Mapped[str | None] = mapped_column(String(8))
    finals_mvp_ids: Mapped[list | None] = mapped_column(JSONType)


class DataQualityReport(Base):
    __tablename__ = "data_quality_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    report: Mapped[dict] = mapped_column(JSONType)


class CareerDocument(Base):
    """Retrieval documents (layer 3) generated from the database. Optional embedding vector."""
    __tablename__ = "career_documents"
    __table_args__ = (UniqueConstraint("player_id", "doc_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    doc_key: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(Text)
    topics: Mapped[list] = mapped_column(JSONType)
    season: Mapped[str | None] = mapped_column(String(7))
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list | None] = mapped_column(JSONType)


class Simulation(Base):
    __tablename__ = "simulations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    status: Mapped[str] = mapped_column(String(24), default="queued")   # queued|round1|round2|round3|coach|complete|failed
    scenario: Mapped[dict] = mapped_column(JSONType)
    llm_config: Mapped[dict | None] = mapped_column(JSONType)
    error: Mapped[str | None] = mapped_column(Text)

    rounds: Mapped[list["SimulationRound"]] = relationship(cascade="all, delete-orphan", order_by="SimulationRound.round_number")
    messages: Mapped[list["SimulationMessage"]] = relationship(cascade="all, delete-orphan", order_by="SimulationMessage.id")
    coach_decision: Mapped["CoachDecision | None"] = relationship(cascade="all, delete-orphan", uselist=False)


class SimulationRound(Base):
    __tablename__ = "simulation_rounds"
    id: Mapped[int] = mapped_column(primary_key=True)
    simulation_id: Mapped[str] = mapped_column(ForeignKey("simulations.id", ondelete="CASCADE"), index=True)
    round_number: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(40))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SimulationMessage(Base):
    __tablename__ = "simulation_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    simulation_id: Mapped[str] = mapped_column(ForeignKey("simulations.id", ondelete="CASCADE"), index=True)
    round_number: Mapped[int] = mapped_column(Integer)
    player: Mapped[str] = mapped_column(String(32))
    content: Mapped[dict] = mapped_column(JSONType)
    raw_text: Mapped[str | None] = mapped_column(Text)
    data_considered: Mapped[dict | None] = mapped_column(JSONType)
    model: Mapped[str | None] = mapped_column(String(80))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CoachDecision(Base):
    __tablename__ = "coach_decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    simulation_id: Mapped[str] = mapped_column(ForeignKey("simulations.id", ondelete="CASCADE"), unique=True)
    decision: Mapped[dict] = mapped_column(JSONType)
    raw_text: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
