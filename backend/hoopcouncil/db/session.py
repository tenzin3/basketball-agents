from __future__ import annotations

import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker

from .. import config
from .models import Base

_engine = None
_Session = None


def normalize_url(url: str) -> str:
    """Hosted Postgres (Neon, Vercel, Heroku) hands out postgres:// or postgresql:// URLs; use the psycopg 3 driver."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def serverless() -> bool:
    return bool(os.environ.get("VERCEL") or os.environ.get("HOOP_SERVERLESS"))


def make_engine(url: str):
    u = normalize_url(url)
    kw = {"future": True, "pool_pre_ping": True}
    if u.startswith("sqlite"):
        kw["connect_args"] = {"check_same_thread": False}
    elif serverless():
        # Short-lived function instances: don't hold connections open; Neon's pooler does the pooling.
        kw["poolclass"] = NullPool
        # Pooled connection strings go through PgBouncer; don't rely on server-side prepared statements.
        kw["connect_args"] = {"prepare_threshold": None}
    return create_engine(u, **kw)


def get_engine(url: str | None = None):
    global _engine, _Session
    if _engine is None or url is not None:
        u = url or config.DATABASE_URL
        _engine = make_engine(u)
        _Session = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def init_db(url: str | None = None) -> None:
    Base.metadata.create_all(get_engine(url))


_runtime_ready = False


def ensure_runtime_tables() -> None:
    """Create the small set of tables the API writes to (simulations, steps, context packages) if missing.
    Older local databases predate some of them; the stats tables are left alone."""
    global _runtime_ready
    if _runtime_ready:
        return
    from .models import RUNTIME_TABLES

    Base.metadata.create_all(get_engine(), tables=[Base.metadata.tables[t] for t in RUNTIME_TABLES])
    _runtime_ready = True


@contextmanager
def session_scope():
    get_engine()
    s = _Session()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
