"""Index lifecycle and reconciliation endpoints."""

from typing import Annotated

from elasticsearch import Elasticsearch
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.es_client import ensure_index, get_client
from app.indexer import reindex_pending
from app.models import Concept
from app.schemas import ReindexResponse

router = APIRouter(prefix="/admin", tags=["admin"])

SessionDep = Annotated[Session, Depends(get_session)]
ClientDep = Annotated[Elasticsearch, Depends(get_client)]


@router.post("/index", response_model=dict)
def create_index(client: ClientDep) -> dict:
    """Create the concept index if missing. Existing indices are never patched."""
    created = ensure_index(client)
    return {"index": get_settings().concept_index, "created": created}


@router.post("/reindex", response_model=ReindexResponse)
def reindex(
    session: SessionDep,
    client: ClientDep,
    only_pending: Annotated[bool, Query()] = True,
) -> ReindexResponse:
    """Repair drift between the relational store and Elasticsearch.

    With `only_pending=false` it rebuilds every document, which is what you run
    after changing the mapping.
    """
    ensure_index(client)
    return ReindexResponse(
        **reindex_pending(session, client, only_pending=only_pending)
    )


@router.get("/reconcile", response_model=dict)
def reconcile(session: SessionDep, client: ClientDep) -> dict:
    """Compare relational and indexed counts. Disagreement is the signal."""
    settings = get_settings()
    ensure_index(client)
    client.indices.refresh(index=settings.concept_index)

    in_database = session.scalar(select(func.count()).select_from(Concept)) or 0
    pending = (
        session.scalar(
            select(func.count())
            .select_from(Concept)
            .where(Concept.pending_index.is_(True))
        )
        or 0
    )
    indexed = client.count(index=settings.concept_index)["count"]

    return {
        "index": settings.concept_index,
        "concepts_in_database": in_database,
        "documents_in_index": indexed,
        "pending_index": pending,
        "in_sync": in_database == indexed and pending == 0,
    }
