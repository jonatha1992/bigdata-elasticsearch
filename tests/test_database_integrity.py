"""Referential integrity enforced by the database, not only by the ORM.

The ``cascade="all, delete-orphan"`` in models.py deletes child rows whenever a
write goes through SQLAlchemy. These tests cover the other path: raw SQL, which
the ORM never sees. Before ``PRAGMA foreign_keys=ON`` a raw DELETE left orphan
descriptions behind, because SQLite parses ``ON DELETE CASCADE`` and then
ignores it by default.
"""

from sqlalchemy import text

from app.db import engine


def test_foreign_keys_are_enabled_on_every_connection():
    """The pragma is per-connection, so a fresh connection must report it on."""
    with engine.connect() as connection:
        enabled = connection.execute(text("PRAGMA foreign_keys")).scalar()

    assert enabled == 1


def test_raw_sql_delete_cascades_to_descriptions(api, sample_concept):
    """A DELETE that bypasses the ORM must not leave orphan descriptions."""
    api.post("/concepts", json=sample_concept)
    concept_id = sample_concept["concept_id"]

    with engine.connect() as connection:
        before = connection.execute(
            text("SELECT COUNT(*) FROM descriptions WHERE concept_id = :id"),
            {"id": concept_id},
        ).scalar()
        assert before == len(sample_concept["descriptions"])

        connection.execute(
            text("DELETE FROM concepts WHERE concept_id = :id"), {"id": concept_id}
        )
        connection.commit()

        orphans = connection.execute(
            text("SELECT COUNT(*) FROM descriptions WHERE concept_id = :id"),
            {"id": concept_id},
        ).scalar()

    assert orphans == 0
