from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .. import config
from .models import Base

_engine = None
_Session = None


def get_engine(url: str | None = None):
    global _engine, _Session
    if _engine is None or url is not None:
        u = url or config.DATABASE_URL
        kw = {"future": True, "pool_pre_ping": True}
        if u.startswith("sqlite"):
            kw["connect_args"] = {"check_same_thread": False}
        _engine = create_engine(u, **kw)
        _Session = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def init_db(url: str | None = None) -> None:
    Base.metadata.create_all(get_engine(url))


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
