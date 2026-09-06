"""Projection of relational concepts into Elasticsearch documents.

The write path is deliberately explicit about the two-store problem:

1. The API commits to the relational store with ``pending_index = True``.
2. It then tries to index into Elasticsearch.
3. Only an acknowledged index response clears the flag.

If step 3 never happens the row stays flagged, so ``POST /admin/reindex`` can
find and repair it later. That is the whole point: the drift is recorded, not
assumed away. A production system would move step 2 to a worker consuming an
outbox table; the recovery story is the same.
"""

from datetime import datetime, timezone

from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch.helpers import bulk
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Concept


def to_document(concept: Concept) -> dict:
    """Flatten a concept and its descriptions into the indexed shape."""
    active_terms = [d.term for d in concept.descriptions if d.active]
    preferred = concept.preferred_term
    return {
        "concept_id": concept.concept_id,
        "fsn": concept.fsn,
        "preferred_term": preferred,
        "terms": active_terms or [concept.fsn],
        "suggest": preferred,
        "semantic_tag": concept.semantic_tag,
        "module": concept.module,
        "curation_status": concept.curation_status,
        "active": concept.active,
        "effective_time": (
            concept.effective_time.isoformat() if concept.effective_time else None
        ),
        "indexed_at": datetime.now(timezone.utc).isoformat(),
    }


def index_concept(
    session: Session,
    concept: Concept,
    client: Elasticsearch,
    *,
    index: str | None = None,
    refresh: str | bool = "wait_for",
) -> bool:
    """Index one concept and clear its dirty flag on success.

    Returns True when Elasticsearch acknowledged the write. Failures are
    swallowed on purpose so an indexing outage cannot reject a curator's edit
    that is already committed; the row stays pending and is repaired later.
    """
    index = index or get_settings().concept_index
    try:
        client.index(
            index=index,
            id=concept.concept_id,
            document=to_document(concept),
            refresh=refresh,
        )
    except Exception:
        return False

    concept.pending_index = False
    concept.indexed_at = datetime.now(timezone.utc)
    session.commit()
    return True


def delete_from_index(
    concept_id: str,
    client: Elasticsearch,
    *,
    index: str | None = None,
    refresh: str | bool = "wait_for",
) -> bool:
    """Remove one concept from the index, tolerating an already-absent doc."""
    index = index or get_settings().concept_index
    try:
        client.delete(index=index, id=concept_id, refresh=refresh)
    except NotFoundError:
        # Already absent is the desired end state, not a failure.
        return True
    except Exception:
        return False
    return True


def reindex_pending(
    session: Session,
    client: Elasticsearch,
    *,
    index: str | None = None,
    only_pending: bool = True,
    batch_size: int = 500,
) -> dict:
    """Bulk-index concepts, inspecting every item rather than the request status.

    A bulk call can return HTTP 200 while individual documents fail. Reporting
    the request as successful would be a lie, so each item outcome is counted.
    """
    index = index or get_settings().concept_index
    statement = select(Concept)
    if only_pending:
        statement = statement.where(Concept.pending_index.is_(True))
    concepts = list(session.scalars(statement))

    if not concepts:
        return {"selected": 0, "indexed": 0, "failed": 0, "errors": []}

    by_id = {c.concept_id: c for c in concepts}
    actions = [
        {"_index": index, "_id": c.concept_id, "_source": to_document(c)}
        for c in concepts
    ]

    indexed, raw_errors = bulk(
        client,
        actions,
        chunk_size=batch_size,
        raise_on_error=False,
        refresh="wait_for",
    )

    failed_ids = set()
    errors = []
    for item in raw_errors:
        info = item.get("index") or item.get("create") or {}
        document_id = info.get("_id")
        failed_ids.add(document_id)
        errors.append({"concept_id": document_id, "error": info.get("error")})

    now = datetime.now(timezone.utc)
    for concept_id, concept in by_id.items():
        if concept_id in failed_ids:
            continue
        concept.pending_index = False
        concept.indexed_at = now
    session.commit()

    return {
        "selected": len(concepts),
        "indexed": indexed,
        "failed": len(failed_ids),
        "errors": errors[:20],
    }
