"""Integration tests for the curation API.

These are integration tests, not unit tests: they need the Docker stack running.
They are self-validating and independent, and each one leaves both stores empty.
"""

import pytest

from app.config import get_settings
from app.es_client import get_client
from app.models import Concept


# --------------------------------------------------------------------------
# health and lifecycle
# --------------------------------------------------------------------------


def test_health_reports_both_stores(api):
    body = api.get("/health").json()
    assert body["api"] == "ok"
    assert body["database"] == "ok"
    assert body["elasticsearch"] == "9.5.3"
    assert body["index_exists"] is True


# --------------------------------------------------------------------------
# CRUD
# --------------------------------------------------------------------------


def test_create_concept_indexes_it_immediately(api, sample_concept):
    response = api.post("/concepts", json=sample_concept)
    assert response.status_code == 201

    body = response.json()
    assert body["concept_id"] == "44054006"
    assert len(body["descriptions"]) == 3
    # The dirty flag was cleared, which only happens after Elasticsearch acked.
    assert body["pending_index"] is False
    assert body["indexed_at"] is not None


def test_duplicate_concept_id_is_rejected(api, sample_concept):
    api.post("/concepts", json=sample_concept)
    response = api.post("/concepts", json=sample_concept)
    assert response.status_code == 409


def test_unknown_concept_returns_404(api):
    assert api.get("/concepts/00000000").status_code == 404


def test_invalid_concept_id_is_rejected_by_the_schema(api, sample_concept):
    sample_concept["concept_id"] = "not-a-number"
    assert api.post("/concepts", json=sample_concept).status_code == 422


def test_invalid_curation_status_is_rejected(api, sample_concept):
    sample_concept["curation_status"] = "almost-approved"
    assert api.post("/concepts", json=sample_concept).status_code == 422


def test_patch_updates_the_record_and_the_index(api, sample_concept):
    api.post("/concepts", json=sample_concept)

    response = api.patch(
        "/concepts/44054006",
        json={"curation_status": "rejected", "curation_note": "Duplicado."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["curation_status"] == "rejected"
    assert body["pending_index"] is False
    # Untouched fields survive a partial update.
    assert body["fsn"] == sample_concept["fsn"]

    hits = api.get("/search", params={"q": "diabetes tipo 2"}).json()["hits"]
    assert hits[0]["curation_status"] == "rejected"


def test_delete_removes_from_both_stores(api, sample_concept):
    api.post("/concepts", json=sample_concept)
    assert api.delete("/concepts/44054006").status_code == 204
    assert api.get("/concepts/44054006").status_code == 404
    assert api.get("/search", params={"q": "diabetes"}).json()["total"] == 0


def test_listing_filters_and_paginates(api, sample_concept):
    api.post("/concepts", json=sample_concept)
    api.post(
        "/concepts",
        json={
            "concept_id": "386661006",
            "fsn": "Fiebre (hallazgo)",
            "semantic_tag": "hallazgo",
            "curation_status": "draft",
            "descriptions": [{"term": "Fiebre", "type": "fsn", "preferred": True}],
        },
    )

    everything = api.get("/concepts").json()
    assert everything["total"] == 2

    filtered = api.get("/concepts", params={"semantic_tag": "hallazgo"}).json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["concept_id"] == "386661006"

    page = api.get("/concepts", params={"limit": 1, "offset": 1}).json()
    assert page["total"] == 2
    assert len(page["items"]) == 1


# --------------------------------------------------------------------------
# search behaviour: the part worth understanding
# --------------------------------------------------------------------------


def test_search_ignores_missing_accents(api):
    """A curator typing "hipertension" must still find "Hipertensión"."""
    api.post(
        "/concepts",
        json={
            "concept_id": "38341003",
            "fsn": "Trastorno hipertensivo del sistema vascular arterial (trastorno)",
            "semantic_tag": "trastorno",
            "descriptions": [
                {"term": "Hipertensión arterial", "type": "fsn", "preferred": True}
            ],
        },
    )
    body = api.get("/search", params={"q": "hipertension arterial"}).json()
    assert body["total"] == 1
    assert body["hits"][0]["concept_id"] == "38341003"


def test_search_matches_a_synonym_not_present_in_the_fsn(api, sample_concept):
    """"DM2" appears only as a synonym, never in the fully specified name."""
    api.post("/concepts", json=sample_concept)
    body = api.get("/search", params={"q": "DM2"}).json()
    assert body["total"] == 1
    assert body["hits"][0]["concept_id"] == "44054006"


def test_search_tolerates_a_typo(api, sample_concept):
    api.post("/concepts", json=sample_concept)
    assert api.get("/search", params={"q": "diabetis"}).json()["total"] == 1


def test_filters_do_not_change_the_score(api, sample_concept):
    """A filter narrows the result set; it must not re-rank what survives."""
    api.post("/concepts", json=sample_concept)

    unfiltered = api.get("/search", params={"q": "diabetes"}).json()
    filtered = api.get(
        "/search", params={"q": "diabetes", "semantic_tag": "trastorno"}
    ).json()

    assert filtered["total"] == unfiltered["total"] == 1
    assert filtered["hits"][0]["score"] == unfiltered["hits"][0]["score"]


def test_filter_excludes_non_matching_concepts(api, sample_concept):
    api.post("/concepts", json=sample_concept)
    body = api.get(
        "/search", params={"q": "diabetes", "curation_status": "draft"}
    ).json()
    assert body["total"] == 0
    assert body["hits"] == []


def test_facets_count_the_whole_result_set(api, sample_concept):
    api.post("/concepts", json=sample_concept)
    api.post(
        "/concepts",
        json={
            "concept_id": "386661006",
            "fsn": "Fiebre (hallazgo)",
            "semantic_tag": "hallazgo",
            "curation_status": "draft",
            "descriptions": [{"term": "Fiebre", "type": "fsn", "preferred": True}],
        },
    )
    facets = api.get("/search", params={"q": ""}).json()["facets"]
    tags = {facet["value"]: facet["count"] for facet in facets["semantic_tag"]}
    assert tags == {"trastorno": 1, "hallazgo": 1}


def test_empty_query_returns_everything(api, sample_concept):
    api.post("/concepts", json=sample_concept)
    assert api.get("/search", params={"q": ""}).json()["total"] == 1


def test_search_with_no_match_is_an_explicit_empty_result(api, sample_concept):
    api.post("/concepts", json=sample_concept)
    body = api.get("/search", params={"q": "apendicectomia"}).json()
    assert body["total"] == 0
    assert body["hits"] == []


def test_highlight_marks_the_matched_fragment(api, sample_concept):
    api.post("/concepts", json=sample_concept)
    hit = api.get("/search", params={"q": "diabetes"}).json()["hits"][0]
    assert "<mark>" in " ".join(sum(hit["highlight"].values(), []))


# --------------------------------------------------------------------------
# autocomplete
# --------------------------------------------------------------------------


def test_suggest_matches_a_prefix_of_the_last_word(api, sample_concept):
    api.post("/concepts", json=sample_concept)
    items = api.get("/search/suggest", params={"q": "diabetes mel"}).json()["items"]
    assert [item["concept_id"] for item in items] == ["44054006"]


def test_suggest_requires_a_query(api):
    assert api.get("/search/suggest", params={"q": ""}).status_code == 422


# --------------------------------------------------------------------------
# analyzers
# --------------------------------------------------------------------------


def test_analyzers_treat_the_same_text_differently(api):
    text = "Enfermedades pulmonares crónicas"

    stemmed = api.get(
        "/search/analyze", params={"text": text, "analyzer": "clinical_text"}
    ).json()
    exact = api.get(
        "/search/analyze", params={"text": text, "analyzer": "clinical_exact"}
    ).json()

    stemmed_tokens = [token["token"] for token in stemmed["tokens"]]
    exact_tokens = [token["token"] for token in exact["tokens"]]

    # Both fold accents down to plain ASCII.
    assert "cronicas" in exact_tokens
    # Only the stemming analyzer collapses plural and gender variation.
    assert stemmed_tokens != exact_tokens
    assert all(token == token.lower() for token in stemmed_tokens)


def test_analyze_reports_token_positions(api):
    tokens = api.get(
        "/search/analyze", params={"text": "dolor toracico"}
    ).json()["tokens"]
    assert [token["position"] for token in tokens] == [0, 1]


# --------------------------------------------------------------------------
# reconciliation: the two-store problem
# --------------------------------------------------------------------------


def test_reconcile_reports_agreement(api, sample_concept):
    api.post("/concepts", json=sample_concept)
    body = api.get("/admin/reconcile").json()
    assert body["concepts_in_database"] == 1
    assert body["documents_in_index"] == 1
    assert body["pending_index"] == 0
    assert body["in_sync"] is True


def test_reconcile_detects_drift_and_reindex_repairs_it(api, sample_concept):
    """Simulate the failure the flags exist for: the index loses a document."""
    api.post("/concepts", json=sample_concept)

    # Delete straight from Elasticsearch, behind the API's back.
    settings = get_settings()
    client = get_client()
    client.delete(index=settings.concept_index, id="44054006", refresh=True)

    drifted = api.get("/admin/reconcile").json()
    assert drifted["concepts_in_database"] == 1
    assert drifted["documents_in_index"] == 0
    assert drifted["in_sync"] is False

    # only_pending=false rebuilds every document, not just the flagged ones.
    repaired = api.post("/admin/reindex", params={"only_pending": False}).json()
    assert repaired["indexed"] == 1
    assert repaired["failed"] == 0
    assert api.get("/admin/reconcile").json()["in_sync"] is True


def test_reindex_with_nothing_pending_is_a_no_op(api, sample_concept):
    api.post("/concepts", json=sample_concept)
    body = api.post("/admin/reindex").json()
    assert body == {"selected": 0, "indexed": 0, "failed": 0, "errors": []}


def test_creating_the_index_twice_is_idempotent(api):
    assert api.post("/admin/index").json()["created"] is False


# --------------------------------------------------------------------------
# projection
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("descriptions", "expected"),
    [
        ([], "Fiebre (hallazgo)"),
        ([{"term": "Fiebre", "type": "fsn", "preferred": True}], "Fiebre"),
        (
            [
                {"term": "Fiebre", "type": "fsn", "preferred": False},
                {"term": "Hipertermia", "type": "synonym", "preferred": True},
            ],
            "Hipertermia",
        ),
    ],
)
def test_preferred_term_falls_back_to_the_fsn(descriptions, expected):
    from app.models import Description

    concept = Concept(
        concept_id="386661006",
        fsn="Fiebre (hallazgo)",
        semantic_tag="hallazgo",
        descriptions=[Description(**d) for d in descriptions],
    )
    assert concept.preferred_term == expected
