"""Elasticsearch client factory and index lifecycle helpers."""

from functools import lru_cache

from elasticsearch import Elasticsearch

from app.config import get_settings
from app.es_index import INDEX_SETTINGS


@lru_cache
def get_client() -> Elasticsearch:
    """Return a cached Elasticsearch client built from settings."""
    settings = get_settings()
    if not settings.elastic_password:
        raise RuntimeError(
            "ELASTIC_PASSWORD is not set. Export it or keep it in the local .env "
            "file; the service refuses to talk to Elasticsearch anonymously."
        )
    return Elasticsearch(
        settings.elastic_url,
        basic_auth=settings.elastic_auth,
        request_timeout=settings.elastic_timeout,
    )


def ensure_index(client: Elasticsearch | None = None, index: str | None = None) -> bool:
    """Create the concept index if it does not exist.

    Returns True when the index was created by this call, False when it already
    existed. Existing indices are left untouched: analysis settings and field
    types are immutable, so changing them means reindexing, not patching.
    """
    client = client or get_client()
    index = index or get_settings().concept_index
    if client.indices.exists(index=index):
        return False
    client.indices.create(index=index, **INDEX_SETTINGS)
    return True


def drop_index(client: Elasticsearch | None = None, index: str | None = None) -> bool:
    """Delete the concept index. Returns False when there was nothing to drop."""
    client = client or get_client()
    index = index or get_settings().concept_index
    if not client.indices.exists(index=index):
        return False
    client.indices.delete(index=index)
    return True
