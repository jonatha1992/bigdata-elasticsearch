"""CRUD endpoints for the curation workflow."""

from typing import Annotated

from elasticsearch import Elasticsearch
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.es_client import get_client
from app.indexer import delete_from_index, index_concept
from app.models import Concept, Description
from app.schemas import ConceptIn, ConceptOut, ConceptPage, ConceptUpdate

router = APIRouter(prefix="/concepts", tags=["concepts"])

SessionDep = Annotated[Session, Depends(get_session)]
ClientDep = Annotated[Elasticsearch, Depends(get_client)]


def _apply_descriptions(concept: Concept, descriptions) -> None:
    concept.descriptions.clear()
    for payload in descriptions:
        concept.descriptions.append(Description(**payload.model_dump()))


def _get_or_404(session: Session, concept_id: str) -> Concept:
    concept = session.get(Concept, concept_id)
    if concept is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Concept {concept_id} not found",
        )
    return concept


@router.post("", response_model=ConceptOut, status_code=status.HTTP_201_CREATED)
def create_concept(
    payload: ConceptIn, session: SessionDep, client: ClientDep
) -> Concept:
    if session.get(Concept, payload.concept_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Concept {payload.concept_id} already exists",
        )

    data = payload.model_dump(exclude={"descriptions"})
    concept = Concept(**data, pending_index=True)
    _apply_descriptions(concept, payload.descriptions)

    session.add(concept)
    session.commit()
    session.refresh(concept)

    index_concept(session, concept, client)
    return concept


@router.get("", response_model=ConceptPage)
def list_concepts(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    curation_status: str | None = None,
    semantic_tag: str | None = None,
    pending_index: bool | None = None,
) -> ConceptPage:
    statement = select(Concept)
    counter = select(func.count()).select_from(Concept)

    for column, value in (
        (Concept.curation_status, curation_status),
        (Concept.semantic_tag, semantic_tag),
        (Concept.pending_index, pending_index),
    ):
        if value is not None:
            statement = statement.where(column == value)
            counter = counter.where(column == value)

    total = session.scalar(counter) or 0
    items = list(
        session.scalars(
            statement.order_by(Concept.updated_at.desc()).limit(limit).offset(offset)
        )
    )
    return ConceptPage(total=total, limit=limit, offset=offset, items=items)


@router.get("/{concept_id}", response_model=ConceptOut)
def get_concept(concept_id: str, session: SessionDep) -> Concept:
    return _get_or_404(session, concept_id)


@router.patch("/{concept_id}", response_model=ConceptOut)
def update_concept(
    concept_id: str, payload: ConceptUpdate, session: SessionDep, client: ClientDep
) -> Concept:
    concept = _get_or_404(session, concept_id)
    changes = payload.model_dump(exclude_unset=True, exclude={"descriptions"})

    for field, value in changes.items():
        setattr(concept, field, value)
    if payload.descriptions is not None:
        _apply_descriptions(concept, payload.descriptions)

    # Mark dirty BEFORE indexing, so a crash leaves a repairable row.
    concept.pending_index = True
    session.commit()
    session.refresh(concept)

    index_concept(session, concept, client)
    return concept


@router.delete("/{concept_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_concept(
    concept_id: str, session: SessionDep, client: ClientDep
) -> Response:
    concept = _get_or_404(session, concept_id)
    session.delete(concept)
    session.commit()
    delete_from_index(concept_id, client)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
