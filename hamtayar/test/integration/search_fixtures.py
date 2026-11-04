"""Fixtures for search integration tests: a disposable, provisioned collection.

Isolation rules: the collection name is unique and test-owned (`hamtayar_search_<hex>`), it is
provisioned by `infra/qdrant/provision_search_indexes.py`, it is seeded through the existing
`store_chunks`, and it is deleted afterwards. The shared `hamtayar_test_chunks` collection and any
production collection are never read, written or dropped.
"""

from __future__ import annotations

import secrets
import uuid

import pytest
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

from packages.storage.qdrant.config import Distance, StorageConfig

QDRANT_URL = "http://127.0.0.1:6333"
VECTOR_NAME = "dense"
VECTOR_SIZE = 4


def engine_reachable() -> bool:
    try:
        QdrantClient(
            url=QDRANT_URL, timeout=2, check_compatibility=False
        ).get_collections()
        return True
    except Exception:  # noqa: BLE001 - any transport problem means "not reachable"
        return False


@pytest.fixture(scope="session")
def search_url() -> str:
    if not engine_reachable():
        pytest.skip(
            f"Qdrant is not reachable at {QDRANT_URL}; search tests are not passed"
        )
    return QDRANT_URL


@pytest.fixture
def search_collection(search_url):
    """Unique, provisioned, disposable search collection."""
    client = QdrantClient(url=search_url, timeout=10, check_compatibility=False)
    name = f"hamtayar_search_{secrets.token_hex(6)}"
    client.create_collection(
        collection_name=name,
        vectors_config={
            VECTOR_NAME: rest.VectorParams(
                size=VECTOR_SIZE, distance=rest.Distance.COSINE
            )
        },
    )
    try:
        # Same index configuration verified on server 1.20.0 (text + phrase matching + BM25 scoring).
        client.create_payload_index(
            collection_name=name,
            field_name="text",
            field_schema=rest.TextIndexParams(
                type=rest.TextIndexType.TEXT,
                tokenizer=rest.TokenizerType.WORD,
                lowercase=True,
                phrase_matching=True,
                scoring=rest.TextScoringParams(type=rest.TextScoringType.BM25),
            ),
        )
        for field in ("tenant_id", "acl_principals", "source_id"):
            client.create_payload_index(
                collection_name=name,
                field_name=field,
                field_schema=rest.KeywordIndexParams(
                    type=rest.KeywordIndexType.KEYWORD, is_tenant=(field == "tenant_id")
                ),
            )
        yield name
    finally:
        client.delete_collection(collection_name=name)
        client.close()


@pytest.fixture
def search_config(search_url, search_collection) -> StorageConfig:
    return StorageConfig(
        url=search_url,
        collection_name=search_collection,
        vector_name=VECTOR_NAME,
        vector_size=VECTOR_SIZE,
        distance=Distance.COSINE,
        batch_size=64,
    )


@pytest.fixture
def search_point_count(search_url):
    client = QdrantClient(url=search_url, timeout=10, check_compatibility=False)

    def count(collection_name: str) -> int:
        return client.count(collection_name=collection_name, exact=True).count

    yield count
    client.close()


@pytest.fixture
def point_id_for_chunk():
    """Deterministic point id, matching the storage adapter's identity rule."""
    from packages.storage.qdrant.adapter import point_id_for

    def build(
        source_id: str, version: str, generation_id: str, chunk_id: str
    ) -> uuid.UUID:
        return point_id_for(source_id, version, generation_id, chunk_id)

    return build
