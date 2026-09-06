"""Relational model for clinical concepts under curation.

The shape is deliberately SNOMED CT-like: a concept carries a fully specified
name plus a semantic tag, and owns many descriptions (synonyms) in one or more
languages. It is a simplified teaching model, not a SNOMED release format.

`pending_index` and `indexed_at` exist because the relational store and
Elasticsearch are two systems that can disagree. A write marks the row dirty
first; the indexer clears the flag only after Elasticsearch acknowledges. A
crash between the two leaves recoverable evidence instead of silent drift.
"""

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

CURATION_STATUSES = ("draft", "in_review", "approved", "rejected")
DESCRIPTION_TYPES = ("fsn", "synonym")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Concept(Base):
    __tablename__ = "concepts"

    concept_id: Mapped[str] = mapped_column(String(18), primary_key=True)
    fsn: Mapped[str] = mapped_column(String(512))
    semantic_tag: Mapped[str] = mapped_column(String(64), index=True)
    module: Mapped[str] = mapped_column(String(64), default="local-extension")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    curation_status: Mapped[str] = mapped_column(
        String(16), default="draft", index=True
    )
    curation_note: Mapped[str | None] = mapped_column(Text, default=None)
    effective_time: Mapped[date | None] = mapped_column(Date, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    pending_index: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    descriptions: Mapped[list["Description"]] = relationship(
        back_populates="concept",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def preferred_term(self) -> str:
        """The term a curator sees first: preferred synonym, else the FSN.

        Column defaults are applied by SQLAlchemy at INSERT time, so a
        Description that has not been flushed yet still holds None in `active`
        and `preferred`. None therefore means "whatever the column declares",
        not "false".
        """
        for description in self.descriptions:
            active = True if description.active is None else description.active
            preferred = bool(description.preferred)
            if active and preferred:
                return description.term
        return self.fsn


class Description(Base):
    __tablename__ = "descriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    concept_id: Mapped[str] = mapped_column(
        ForeignKey("concepts.concept_id", ondelete="CASCADE"), index=True
    )
    term: Mapped[str] = mapped_column(String(512))
    type: Mapped[str] = mapped_column(String(16), default="synonym")
    language: Mapped[str] = mapped_column(String(8), default="es")
    preferred: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    concept: Mapped[Concept] = relationship(back_populates="descriptions")
