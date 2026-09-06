"""Elasticsearch index definition for clinical concepts.

This file is the heart of the search behaviour, so it is worth reading slowly.

Three ways to treat the same term, on purpose:

- ``clinical_text``  stems and strips stopwords. "hipertensión arterial" and
  "hipertensivo arterial" both reduce to the same root, so recall is high.
  Good for the main search box.
- ``clinical_exact`` lowercases and folds accents but does NOT stem. It keeps
  "hipertensión" distinct from "hipertensivo". Used to boost precise hits above
  merely stemmed ones.
- ``clinical_keyword`` (a normalizer, not an analyzer) produces one single
  token for the whole string. Used for exact lookup, sorting and faceting.

``asciifolding`` matters more than it looks in Spanish clinical text: curators
type "hipertension" without the accent constantly, and without folding those
queries would silently return nothing.
"""

INDEX_SETTINGS: dict = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "filter": {
                "spanish_stop": {"type": "stop", "stopwords": "_spanish_"},
                "spanish_stemmer": {"type": "stemmer", "language": "light_spanish"},
            },
            "analyzer": {
                "clinical_text": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": [
                        "lowercase",
                        "asciifolding",
                        "spanish_stop",
                        "spanish_stemmer",
                    ],
                },
                "clinical_exact": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "asciifolding"],
                },
            },
            "normalizer": {
                "clinical_keyword": {
                    "type": "custom",
                    "filter": ["lowercase", "asciifolding"],
                }
            },
        },
    },
    "mappings": {
        "dynamic": "strict",
        "properties": {
            "concept_id": {"type": "keyword"},
            "fsn": {
                "type": "text",
                "analyzer": "clinical_text",
                "fields": {
                    "exact": {"type": "text", "analyzer": "clinical_exact"},
                    "raw": {"type": "keyword", "normalizer": "clinical_keyword"},
                },
            },
            "preferred_term": {
                "type": "text",
                "analyzer": "clinical_text",
                "fields": {
                    "exact": {"type": "text", "analyzer": "clinical_exact"},
                    "raw": {"type": "keyword", "normalizer": "clinical_keyword"},
                },
            },
            # Every active synonym, flattened. One field, many values: this is
            # how you search "all the ways a clinician might name the concept".
            "terms": {
                "type": "text",
                "analyzer": "clinical_text",
                "fields": {
                    "exact": {"type": "text", "analyzer": "clinical_exact"},
                },
            },
            # search_as_you_type builds its own _2gram/_3gram subfields, so it
            # must be a top-level field rather than a multi-field.
            "suggest": {"type": "search_as_you_type", "analyzer": "clinical_exact"},
            "semantic_tag": {"type": "keyword"},
            "module": {"type": "keyword"},
            "curation_status": {"type": "keyword"},
            "active": {"type": "boolean"},
            "effective_time": {"type": "date"},
            "indexed_at": {"type": "date"},
        },
    },
}

# Fields the main query searches, with their boosts. An exact (unstemmed) hit
# outranks a stemmed one, and the fully specified name outranks a synonym.
SEARCH_FIELDS = [
    "fsn.exact^6",
    "fsn^4",
    "preferred_term.exact^5",
    "preferred_term^3",
    "terms.exact^2",
    "terms^1",
]
