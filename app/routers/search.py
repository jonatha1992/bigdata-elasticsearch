"""Search, autocomplete and analyzer-inspection endpoints."""

from typing import Annotated

from elasticsearch import Elasticsearch
from fastapi import APIRouter, Depends, Query

from app.es_client import get_client
from app.schemas import (
    AnalyzeResponse,
    AnalyzeToken,
    Facet,
    SearchHit,
    SearchResponse,
    SuggestItem,
    SuggestResponse,
)
from app.search import (
    analyze,
    build_filters,
    build_search_body,
    build_suggest_body,
    run_search,
)

router = APIRouter(prefix="/search", tags=["search"])

ClientDep = Annotated[Elasticsearch, Depends(get_client)]


def _facets(aggregations: dict) -> dict[str, list[Facet]]:
    result: dict[str, list[Facet]] = {}
    for name, payload in (aggregations or {}).items():
        result[name] = [
            Facet(value=str(bucket["key"]), count=bucket["doc_count"])
            for bucket in payload.get("buckets", [])
        ]
    return result


@router.get("", response_model=SearchResponse)
def search_concepts(
    client: ClientDep,
    q: str = "",
    semantic_tag: str | None = None,
    curation_status: str | None = None,
    active: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SearchResponse:
    filters = build_filters(
        semantic_tag=semantic_tag, curation_status=curation_status, active=active
    )
    body = build_search_body(q, filters=filters, limit=limit, offset=offset)
    response = run_search(client, body)

    hits = []
    for hit in response["hits"]["hits"]:
        source = hit["_source"]
        hits.append(
            SearchHit(
                concept_id=source["concept_id"],
                fsn=source["fsn"],
                preferred_term=source["preferred_term"],
                semantic_tag=source["semantic_tag"],
                curation_status=source["curation_status"],
                active=source["active"],
                score=hit["_score"] or 0.0,
                highlight=hit.get("highlight", {}),
            )
        )

    return SearchResponse(
        query=q,
        total=response["hits"]["total"]["value"],
        took_ms=response["took"],
        limit=limit,
        offset=offset,
        hits=hits,
        facets=_facets(response.get("aggregations", {})),
    )


@router.get("/suggest", response_model=SuggestResponse)
def suggest(
    client: ClientDep,
    q: Annotated[str, Query(min_length=1)],
    active: bool | None = True,
    limit: Annotated[int, Query(ge=1, le=25)] = 10,
) -> SuggestResponse:
    filters = build_filters(active=active)
    response = run_search(client, build_suggest_body(q, limit, filters))
    items = [
        SuggestItem(
            concept_id=hit["_source"]["concept_id"],
            label=hit["_source"]["preferred_term"],
            semantic_tag=hit["_source"]["semantic_tag"],
        )
        for hit in response["hits"]["hits"]
    ]
    return SuggestResponse(query=q, items=items)


@router.get("/analyze", response_model=AnalyzeResponse)
def analyze_text(
    client: ClientDep,
    text: Annotated[str, Query(min_length=1)],
    analyzer: str = "clinical_text",
) -> AnalyzeResponse:
    """Show the tokens an analyzer produces. The 'why did this not match' tool."""
    tokens = analyze(client, text, analyzer)
    return AnalyzeResponse(
        text=text,
        analyzer=analyzer,
        tokens=[
            AnalyzeToken(
                token=token["token"],
                position=token["position"],
                start_offset=token["start_offset"],
                end_offset=token["end_offset"],
                type=token["type"],
            )
            for token in tokens
        ],
    )
