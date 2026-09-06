"""SQLAlchemy engine and session wiring.

The engine is created from ``settings.database_url``. Nothing in this module or
in models.py is SQLite-specific, so moving to PostgreSQL is a URL change plus a
driver install, not a rewrite.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for every ORM model."""


def _engine_kwargs(url: str) -> dict:
    # SQLite refuses to reuse a connection across threads by default, and
    # FastAPI serves requests from a thread pool. PostgreSQL needs neither flag.
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


settings = get_settings()
engine = create_engine(settings.database_url, **_engine_kwargs(settings.database_url))
SessionFactory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped session."""
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()


def create_all() -> None:
    """Create tables for every imported model. Alembic replaces this later."""
    from app import models  # noqa: F401  (import registers the mappers)

    Base.metadata.create_all(bind=engine)
