"""Fixtures for the S-02 integration suite.

Real local Qdrant only. The fixture creates a unique collection per run and deletes it afterwards;
when the service is unreachable the tests are SKIPPED with a reason, never silently passed.
This is test support code, so importing the SDK here is allowed (the production boundary covers
packages/ and apps/ only).
"""

import uuid

import pytest
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

from packages.storage.qdrant.config import Distance, StorageConfig

QDRANT_URL = "http://127.0.0.1:6333"
VECTOR_NAME = "dense"
VECTOR_SIZE = 4


def reachable() -> bool:
    try:
        QdrantClient(url=QDRANT_URL, timeout=2).get_collections()
        return True
    except Exception:  # noqa: BLE001 - any transport/problem means "not reachable"
        return False


@pytest.fixture(scope="session")
def qdrant_url() -> str:
    if not reachable():
        pytest.skip(f"Qdrant is not reachable at {QDRANT_URL}; integration tests are not passed")
    return QDRANT_URL


@pytest.fixture
def collection(qdrant_url):
    """Unique collection per test, removed afterwards."""
    client = QdrantClient(url=qdrant_url, timeout=10)
    name = f"hamtayar_s02_{uuid.uuid4().hex[:12]}"
    client.create_collection(
        collection_name=name,
        vectors_config={
            VECTOR_NAME: rest.VectorParams(size=VECTOR_SIZE, distance=rest.Distance.COSINE)
        },
    )
    try:
        yield name
    finally:
        client.delete_collection(collection_name=name)
        client.close()


@pytest.fixture
def config(qdrant_url, collection) -> StorageConfig:
    return StorageConfig(
        url=qdrant_url,
        collection_name=collection,
        vector_name=VECTOR_NAME,
        vector_size=VECTOR_SIZE,
        distance=Distance.COSINE,
        batch_size=64,
    )


@pytest.fixture
def point_count(qdrant_url):
    client = QdrantClient(url=qdrant_url, timeout=10)

    def count(collection_name: str) -> int:
        return client.count(collection_name=collection_name, exact=True).count

    yield count
    client.close()
