"""Runtime configuration (environment variables, with .env support if python-dotenv is installed)."""
from __future__ import annotations

import os
from pathlib import Path

try:  # optional
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except Exception:  # pragma: no cover
    pass

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent


def _path(env: str, default: Path) -> Path:
    return Path(os.environ.get(env, str(default))).expanduser().resolve()


DATA_DIR = _path("HOOP_DATA_DIR", PROJECT_DIR / "data")
RAW_CACHE_DIR = DATA_DIR / "raw"            # raw HTML/JSON exactly as retrieved
PROCESSED_DIR = DATA_DIR / "processed"      # parsed canonical datasets (one JSON per player)
REPORTS_DIR = DATA_DIR / "reports"          # data-quality reports
CONTEXT_CACHE_DIR = _path("HOOP_CONTEXT_CACHE_DIR", PROJECT_DIR / "career_context_cache")

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://hoop:hoop@localhost:5432/hoopcouncil"
)

# Politeness for Sports Reference sites: their published bot policy allows at most
# 20 requests/minute. We default to one request every 3.5 seconds (~17/min).
BREF_MIN_INTERVAL_S = float(os.environ.get("BREF_MIN_INTERVAL_S", "3.5"))
NBA_STATS_MIN_INTERVAL_S = float(os.environ.get("NBA_STATS_MIN_INTERVAL_S", "1.5"))
USER_AGENT = os.environ.get(
    "HOOP_USER_AGENT",
    "HoopCouncil-research-bot/0.1 (personal, non-commercial; respects rate limits)",
)

# LLM configuration. Player agents use the inexpensive tier, the coach the stronger tier.
LLM_PROVIDER = os.environ.get("HOOP_LLM_PROVIDER", "anthropic")          # anthropic|openai|gemini|local|mock
PLAYER_MODEL = os.environ.get("HOOP_PLAYER_MODEL", "")                    # blank = provider default (cheap tier)
COACH_PROVIDER = os.environ.get("HOOP_COACH_PROVIDER", "") or LLM_PROVIDER
COACH_MODEL = os.environ.get("HOOP_COACH_MODEL", "")                      # blank = provider default (strong tier)
LLM_TEMPERATURE = float(os.environ.get("HOOP_LLM_TEMPERATURE", "0.4"))
LLM_MAX_TOKENS = int(os.environ.get("HOOP_LLM_MAX_TOKENS", "2000"))
LOCAL_LLM_BASE_URL = os.environ.get("HOOP_LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")

# Optional embeddings for retrieval (BM25 is always available and is the default).
EMBEDDINGS_PROVIDER = os.environ.get("HOOP_EMBEDDINGS_PROVIDER", "none")  # none|openai|local

# Approximate token budget for each player's context (layer 1 + layer 2 + retrieved layer 3).
CONTEXT_TOKEN_BUDGET = int(os.environ.get("HOOP_CONTEXT_TOKEN_BUDGET", "9000"))

CORS_ORIGINS = os.environ.get("HOOP_CORS_ORIGINS", "http://localhost:3000").split(",")
