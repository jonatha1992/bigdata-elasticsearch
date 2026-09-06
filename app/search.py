"""Query builders for concept search.

Filters go in `filter` context, not `must`. Filters answer yes/no and are
cacheable; they must not influence the relevance score. Only the free-text part
belongs in scoring context. Mixing the two is the classic way to get rankings
that quietly make no sense.
"""

from typing import Any

from elasticsearch import Elasticsearch

from app.config import get_settings
from app.es_index import SEARCH_FIELDS


def build_filters(
    *,
    semantic_tag: str | None = None,
    curation_status: str | None = None,
    active: bool | None = None,
) -> list[dict]:
    filters: list[dict] = []
    if semantic_tag:
        filters.append({"term": {"semantic_tag": semantic_tag}})
    if curation_status:
        filters.append({"term": {"curation_status": curation_status}})
    if active is not None:
        filters.append({"term": {"active": active}})
    return filters


def build_search_body(
    query: str,
    *,
    filters: list[dict],
    limit: int,
    offset: int,
) -> dict:
    if query.strip():
        # `best_fields` scores a document by its single strongest field rather
        # than summing them, which suits short clinical labels.
        # `fuzziness=AUTO` tolerates the typos curators actually make; it applies
        # only to the analysed text clause, never to the filters.
        text_clause: dict[str, Any] = {
            "multi_match": {
                "query": query,
                "fields": SEARCH_FIELDS,
                "type": "best_fields",
                "fuzziness": "AUTO",
                "prefix_length": 1,
            }
        }
    else:
        text_clause = {"match_all": {}}

    return {
        "query": {"bool": {"must": [text_clause], "filter": filters}},
        "from": offset,
        "size": limit,
        "highlight": {
            "fields": {"fsn": {}, "preferred_term": {}, "terms": {}},
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
        },
        "aggs": {
            "semantic_tag": {"terms": {"field": "semantic_tag", "size": 20}},
            "curation_status": {"terms": {"field": "curation_status", "size": 10}},
        },
        "track_total_hits": True,
    }


def build_suggest_body(query: str, limit: int, filters: list[dict]) -> dict:
    # bool_prefix matches every token as a full term except the last one, which
    # is matched as a prefix. That is exactly what typing into a box feels like.
    return {
        "query": {
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": query,
                            "type": "bool_prefix",
                            "fields": [
                                "suggest",
                                "suggest._2gram",
                                "suggest._3gram",
                            ],
                        }
                    }
                ],
                "filter": filters,
            }
        },
        "size": limit,
        "_source": ["concept_id", "preferred_term", "semantic_tag"],
    }


def run_search(client: Elasticsearch, body: dict, index: str | None = None) -> dict:
    index = index or get_settings().concept_index
    return client.search(index=index, body=body)


def analyze(
    client: Elasticsearch,
    text: str,
    analyzer: str,
    index: str | None = None,
) -> list[dict]:
    """Expose what the analyzer does to a string.

    This is the endpoint to open when someone asks why a query did not match.
    """
    index = index or get_settings().concept_index
    response = client.indices.analyze(index=index, analyzer=analyzer, text=text)
    return list(response.get("tokens", []))
