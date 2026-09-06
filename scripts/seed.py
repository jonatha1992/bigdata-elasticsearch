"""Load the sample concept fixture into SQLite and Elasticsearch.

Usage:
    .\\.vennv\\Scripts\\python.exe -m scripts.seed [--reset]

`--reset` drops the index and clears the tables first, which is the only way to
apply a changed mapping: analysis settings and field types are immutable once
an index exists.
"""

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import delete

from app.config import PROJECT_ROOT, get_settings
from app.db import SessionFactory, create_all
from app.es_client import drop_index, ensure_index, get_client
from app.indexer import reindex_pending
from app.models import Concept, Description

FIXTURE = PROJECT_ROOT / "seed" / "concepts.json"


def load_fixture(path: Path = FIXTURE) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def seed(reset: bool = False) -> dict:
    settings = get_settings()
    client = get_client()

    create_all()
    session = SessionFactory()

    try:
        if reset:
            session.execute(delete(Description))
            session.execute(delete(Concept))
            session.commit()
            drop_index(client)

        created_index = ensure_index(client)

        records = load_fixture()
        inserted = 0
        for record in records:
            if session.get(Concept, record["concept_id"]) is not None:
                continue
            descriptions = record.pop("descriptions", [])
            concept = Concept(**record, pending_index=True)
            for description in descriptions:
                concept.descriptions.append(Description(**description))
            session.add(concept)
            inserted += 1
        session.commit()

        result = reindex_pending(session, client, only_pending=True)
        client.indices.refresh(index=settings.concept_index)

        return {
            "index": settings.concept_index,
            "index_created": created_index,
            "concepts_inserted": inserted,
            "concepts_in_fixture": len(records),
            **result,
        }
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed clinical concepts.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop the index and clear the tables before loading.",
    )
    arguments = parser.parse_args()

    summary = seed(reset=arguments.reset)
    for key, value in summary.items():
        if key == "errors" and not value:
            continue
        print(f"{key}: {value}")
    return 1 if summary.get("failed") else 0


if __name__ == "__main__":
    sys.exit(main())
