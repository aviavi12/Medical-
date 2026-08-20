"""SQLAlchemy engine, session factory, and declarative base.

Engine is chosen by ``DATABASE_URL`` (PostgreSQL in prod). When unset, a local
SQLite file is used so the app and tests run with no external server. Business
logic never assumes a specific engine.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from apps.api.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    url = get_settings().database_url_resolved
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, future=True, connect_args=connect_args)


_engine = None
_SessionLocal: sessionmaker | None = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = _make_engine()
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)
    return _SessionLocal


def create_all() -> None:
    """Create all tables. Imports models so they register on the metadata."""
    from database import models  # noqa: F401  (registers tables)

    Base.metadata.create_all(bind=get_engine())


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a session with commit/rollback handling."""
    factory = get_session_factory()
    db = factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def reset_engine_for_tests() -> None:
    """Force re-creation of engine/session (used when tests point at a temp DB)."""
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None
