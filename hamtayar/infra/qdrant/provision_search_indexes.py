"""Development/test support: provision the search indexes on a disposable collection.

Infrastructure owns provisioning (approved decision A): storage and retrieval never create or modify
indexes at runtime. This script is intentionally restricted to clearly disposable collections —
it refuses any name that does not start with `hamtayar_search_` or `hamtayar_bm25_verify_`, so the
shared `hamtayar_test_chunks` collection and any production collection cannot be touched by accident.

Usage:

    uv run python infra/qdrant/provision_search_indexes.py --collection hamtayar_search_dev
    uv run python infra/qdrant/provision_search_indexes.py --collection hamtayar_search_dev --verify
"""

from __future__ import annotations

import argparse
import sys

from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

ALLOWED_PREFIXES = ("hamtayar_search_", "hamtayar_bm25_verify_")
TEXT_FIELD = "text"
KEYWORD_FIELDS = ("tenant_id", "acl_principals", "source_id")


def _text_index() -> rest.TextIndexParams:
    """Full-text index with phrase matching and native BM25 scoring (verified on server 1.20.0)."""
    return rest.TextIndexParams(
        type=rest.TextIndexType.TEXT,
        tokenizer=rest.TokenizerType.WORD,
        lowercase=True,
        phrase_matching=True,
        scoring=rest.TextScoringParams(type=rest.TextScoringType.BM25),
    )


def _keyword_index(is_tenant: bool) -> rest.KeywordIndexParams:
    return rest.KeywordIndexParams(
        type=rest.KeywordIndexType.KEYWORD, is_tenant=is_tenant
    )


def guard_collection_name(name: str) -> None:
    if not name.startswith(ALLOWED_PREFIXES):
        raise SystemExit(
            f"refusing to provision {name!r}: only disposable collections "
            f"({', '.join(ALLOWED_PREFIXES)}) may be provisioned by this script"
        )


def provision(client: QdrantClient, collection: str) -> None:
    guard_collection_name(collection)
    if not client.collection_exists(collection):
        raise SystemExit(f"collection {collection!r} does not exist; create it first")

    client.create_payload_index(
        collection_name=collection, field_name=TEXT_FIELD, field_schema=_text_index()
    )
    for field in KEYWORD_FIELDS:
        client.create_payload_index(
            collection_name=collection,
            field_name=field,
            field_schema=_keyword_index(is_tenant=(field == "tenant_id")),
        )
    print(f"provisioned search indexes on {collection}")


def report(client: QdrantClient, collection: str) -> None:
    info = client.get_collection(collection)
    print(f"collection: {collection}")
    vectors = info.config.params.vectors
    if isinstance(vectors, dict):
        for name, params in vectors.items():
            distance = getattr(params.distance, "value", params.distance)
            print(f"  dense vector: {name} size={params.size} distance={distance}")
    for field, schema in sorted(info.payload_schema.items()):
        print(f"  payload index: {field} -> {schema}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:6333")
    parser.add_argument("--collection", required=True)
    parser.add_argument(
        "--verify", action="store_true", help="only print the current profile"
    )
    args = parser.parse_args(argv)

    guard_collection_name(args.collection)
    client = QdrantClient(url=args.url, timeout=20, check_compatibility=False)
    try:
        if not args.verify:
            provision(client, args.collection)
        report(client, args.collection)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - report, do not pretend success
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
