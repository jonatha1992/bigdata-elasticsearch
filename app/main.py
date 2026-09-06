"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import Annotated

from elasticsearch import Elasticsearch
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import create_all, get_session
from app.es_client import ensure_index, get_client
from app.models import Concept
from app.schemas import HealthResponse
from app.routers import admin, concepts, search


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tables are cheap and idempotent to create. The index is best-effort: the
    # API must still start (and report unhealthy) when Elasticsearch is down.
    create_all()
    try:
        ensure_index()
    except Exception:
        pass
    yield


app = FastAPI(
    title="Clinical Terminology Curation API",
    description=(
        "Curation workflow over SNOMED CT-like clinical concepts, backed by "
        "SQLite for the editorial record and Elasticsearch for search."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# The React curation UI runs on its own dev server during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(concepts.router)
app.include_router(search.router)
app.include_router(admin.router)


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health(
    session: Annotated[Session, Depends(get_session)],
    client: Annotated[Elasticsearch, Depends(get_client)],
) -> HealthResponse:
    settings = get_settings()

    try:
        session.execute(text("SELECT 1"))
        database = "ok"
    except Exception as error:
        database = f"error: {type(error).__name__}"

    index_exists = False
    try:
        elasticsearch = client.info()["version"]["number"]
        # indices.exists() returns a HeadApiResponse, which is truthy but is not
        # a bool; coerce it before it reaches the response model.
        index_exists = bool(client.indices.exists(index=settings.concept_index))
    except Exception as error:
        elasticsearch = f"error: {type(error).__name__}"

    try:
        pending = (
            session.scalar(
                select(func.count())
                .select_from(Concept)
                .where(Concept.pending_index.is_(True))
            )
            or 0
        )
    except Exception:
        pending = -1

    return HealthResponse(
        api="ok",
        database=database,
        elasticsearch=elasticsearch,
        index=settings.concept_index,
        index_exists=index_exists,
        pending_index=pending,
    )
