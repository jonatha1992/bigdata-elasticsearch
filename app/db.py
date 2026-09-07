"""SQLAlchemy engine and session wiring.

The engine is created from ``settings.database_url``. Nothing in this module or
in models.py is SQLite-specific, so moving to PostgreSQL is a URL change plus a
driver install, not a rewrite.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine, event
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


if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
        """Turn on foreign key enforcement for every new SQLite connection.

        SQLite ships with ``PRAGMA foreign_keys = 0``, so the ``ON DELETE
        CASCADE`` declared in models.py is parsed and then ignored. Without this
        the referential integrity of the schema depends on every write going
        through SQLAlchemy, because the ORM-level ``cascade`` is what actually
        deletes the child rows. A raw SQL DELETE would leave orphans.

        The pragma is per-connection, not per-database, which is why it has to
        be re-applied on connect rather than set once at creation time. The
        listener is registered only for SQLite: other engines enforce foreign
        keys natively and would reject the statement.
        """
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


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
