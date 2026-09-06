"""Pydantic request and response models.

These are the API contract. They are intentionally separate from the ORM models:
the database shape and the wire shape change for different reasons.
"""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

CurationStatus = Literal["draft", "in_review", "approved", "rejected"]
DescriptionType = Literal["fsn", "synonym"]


class DescriptionIn(BaseModel):
    term: Annotated[str, Field(min_length=1, max_length=512)]
    type: DescriptionType = "synonym"
    language: Annotated[str, Field(min_length=2, max_length=8)] = "es"
    preferred: bool = False
    active: bool = True


class DescriptionOut(DescriptionIn):
    model_config = ConfigDict(from_attributes=True)

    id: int


class ConceptIn(BaseModel):
    concept_id: Annotated[str, Field(min_length=1, max_length=18, pattern=r"^\d+$")]
    fsn: Annotated[str, Field(min_length=1, max_length=512)]
    semantic_tag: Annotated[str, Field(min_length=1, max_length=64)]
    module: Annotated[str, Field(max_length=64)] = "local-extension"
    active: bool = True
    curation_status: CurationStatus = "draft"
    curation_note: str | None = None
    effective_time: date | None = None
    descriptions: list[DescriptionIn] = Field(default_factory=list)


class ConceptUpdate(BaseModel):
    """Partial update. Unset fields are left alone; `descriptions` replaces all."""

    fsn: Annotated[str, Field(min_length=1, max_length=512)] | None = None
    semantic_tag: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    module: Annotated[str, Field(max_length=64)] | None = None
    active: bool | None = None
    curation_status: CurationStatus | None = None
    curation_note: str | None = None
    effective_time: date | None = None
    descriptions: list[DescriptionIn] | None = None


class ConceptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    concept_id: str
    fsn: str
    semantic_tag: str
    module: str
    active: bool
    curation_status: CurationStatus
    curation_note: str | None
    effective_time: date | None
    created_at: datetime
    updated_at: datetime
    pending_index: bool
    indexed_at: datetime | None
    descriptions: list[DescriptionOut]


class ConceptPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ConceptOut]


class SearchHit(BaseModel):
    concept_id: str
    fsn: str
    preferred_term: str
    semantic_tag: str
    curation_status: str
    active: bool
    score: float
    highlight: dict[str, list[str]] = Field(default_factory=dict)


class Facet(BaseModel):
    value: str
    count: int


class SearchResponse(BaseModel):
    query: str
    total: int
    took_ms: int
    limit: int
    offset: int
    hits: list[SearchHit]
    facets: dict[str, list[Facet]] = Field(default_factory=dict)


class SuggestItem(BaseModel):
    concept_id: str
    label: str
    semantic_tag: str


class SuggestResponse(BaseModel):
    query: str
    items: list[SuggestItem]


class AnalyzeToken(BaseModel):
    token: str
    position: int
    start_offset: int
    end_offset: int
    type: str


class AnalyzeResponse(BaseModel):
    text: str
    analyzer: str
    tokens: list[AnalyzeToken]


class ReindexResponse(BaseModel):
    selected: int
    indexed: int
    failed: int
    errors: list[dict] = Field(default_factory=list)


class HealthResponse(BaseModel):
    api: Literal["ok"]
    database: str
    elasticsearch: str
    index: str
    index_exists: bool
    pending_index: int
