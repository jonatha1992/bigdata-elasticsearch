"""Test fixtures.

The environment is set BEFORE importing anything from `app`, because the
settings object and the SQLAlchemy engine are built at import time. Tests get
their own SQLite file and their own Elasticsearch index, so a test run can
never touch the development data.
"""

import os
import tempfile
from pathlib import Path

import pytest

TEST_INDEX = "clinical-concepts-test"
_TEMP_DIR = Path(tempfile.mkdtemp(prefix="curation-tests-"))

os.environ["CONCEPT_INDEX"] = TEST_INDEX
os.environ["DATABASE_URL"] = f"sqlite:///{(_TEMP_DIR / 'test.db').as_posix()}"

from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.es_client import drop_index, ensure_index, get_client  # noqa: E402
from app.main import app  # noqa: E402


def _elasticsearch_available() -> bool:
    try:
        return bool(get_client().ping())
    except Exception:
        return False


@pytest.fixture(scope="session", autouse=True)
def _stack():
    if not _elasticsearch_available():
        pytest.skip(
            "Elasticsearch is not reachable; start it with `docker compose up -d`.",
            allow_module_level=True,
        )
    client = get_client()
    drop_index(client, TEST_INDEX)
    ensure_index(client, TEST_INDEX)
    Base.metadata.create_all(bind=engine)
    yield
    drop_index(client, TEST_INDEX)


@pytest.fixture
def api():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _clean_state(api):
    """Empty both stores between tests so each one starts from a known point."""
    yield
    existing = api.get("/concepts", params={"limit": 200}).json()["items"]
    for item in existing:
        api.delete(f"/concepts/{item['concept_id']}")


@pytest.fixture
def sample_concept() -> dict:
    return {
        "concept_id": "44054006",
        "fsn": "Diabetes mellitus tipo 2 (trastorno)",
        "semantic_tag": "trastorno",
        "curation_status": "approved",
        "descriptions": [
            {"term": "Diabetes mellitus tipo 2", "type": "fsn", "preferred": True},
            {"term": "DM2", "type": "synonym"},
            {"term": "Diabetes no insulinodependiente", "type": "synonym"},
        ],
    }
