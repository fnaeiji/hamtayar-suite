"""Native Qdrant access filtering against the isolated local instance.

Scope note: this verifies that the stored payload CAN be filtered by tenant, ACL principals and
source ids at the database level. It does NOT mean production retrieval enforces `AccessScope` —
no retriever exists yet (see `packages/retrieval`, empty). Filtering happens in the test only.

Every collection is created and deleted by the `collection` fixture (uniquely named), so no shared
collection is read, written or dropped.
"""

import pytest
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

from packages.contracts.access import AccessMetadata
from packages.contracts.chunks import Chunk
from packages.contracts.common import SourceLocation, SourceRef, SourceVersion
from packages.contracts.indexing import EmbeddingRecord, IndexingRequest
from packages.storage.qdrant.adapter import point_id_for
from packages.storage.service import read_chunks, store_chunks

GENERATION = "gen-acl"
VECTOR = [0.1, 0.2, 0.3, 0.4]

# P1..P4 exactly as specified by the task
SAMPLES = (
    # chunk_id, tenant, principals, source_id
    ("P1", "tenant-A", ["finance"], "doc-1"),
    ("P2", "tenant-A", ["engineering"], "doc-2"),
    ("P3", "tenant-B", ["finance"], "doc-3"),
    ("P4", "tenant-A", ["finance", "management"], "doc-4"),
)


def a_chunk(chunk_id: str, tenant: str, principals: list[str], source_id: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        source=SourceVersion(
            source=SourceRef(source_id=source_id, knowledge_space_id="ks-1", source_type="document"),
            version="v1",
        ),
        kind="document",
        text=f"content of {chunk_id}",
        access=AccessMetadata(tenant_id=tenant, acl_principals=principals),
        location=SourceLocation(page=1),
    )


@pytest.fixture
def seeded(config):
    """Store the four sample points through the real storage service."""
    chunks = [a_chunk(*sample) for sample in SAMPLES]
    embeddings = [
        EmbeddingRecord(chunk_id=chunk.chunk_id, model_id="embed-4d", vector=VECTOR) for chunk in chunks
    ]
    request = IndexingRequest(
        source=chunks[0].source, generation_id=GENERATION, chunks=chunks, embeddings=embeddings
    )
    result = store_chunks(request, config=config)
    assert result.validated is True and result.indexed_count == 4
    return request


def hits(qdrant_url: str, collection: str, query_filter: rest.Filter) -> set[str]:
    """Run a real filtered query and return the chunk_ids it matched (test-side filtering)."""
    client = QdrantClient(url=qdrant_url, timeout=10, check_compatibility=False)
    try:
        response = client.query_points(
            collection_name=collection,
            query=VECTOR,
            using="dense",  # the collection uses a named dense vector
            query_filter=query_filter,
            limit=10,
            with_payload=True,
        )
        return {point.payload["chunk_id"] for point in response.points}
    finally:
        client.close()


def tenant_filter(*tenants: str) -> rest.Filter:
    return rest.Filter(
        must=[rest.FieldCondition(key="tenant_id", match=rest.MatchAny(any=list(tenants)))]
    )


def principals_filter(*principals: str) -> rest.FieldCondition:
    return rest.FieldCondition(key="acl_principals", match=rest.MatchAny(any=list(principals)))


def sources_filter(*source_ids: str) -> rest.FieldCondition:
    return rest.FieldCondition(key="source_id", match=rest.MatchAny(any=list(source_ids)))


# ---- the four scenarios + combinations


def test_tenant_isolation(seeded, config, collection, qdrant_url):
    assert hits(qdrant_url, collection, tenant_filter("tenant-A")) == {"P1", "P2", "P4"}
    assert hits(qdrant_url, collection, tenant_filter("tenant-B")) == {"P3"}

    tenant_a = hits(qdrant_url, collection, tenant_filter("tenant-A"))
    assert "P3" not in tenant_a, "tenant-A must not retrieve tenant-B data"


def test_principal_filtering(seeded, config, collection, qdrant_url):
    flt = rest.Filter(must=[*tenant_filter("tenant-A").must, principals_filter("finance")])

    assert hits(qdrant_url, collection, flt) == {"P1", "P4"}, "engineering-only data must not leak"


def test_multiple_principals_and_overlap(seeded, config, collection, qdrant_url):
    management = rest.Filter(must=[*tenant_filter("tenant-A").must, principals_filter("management")])
    either = rest.Filter(
        must=[*tenant_filter("tenant-A").must, principals_filter("finance", "engineering")]
    )

    assert hits(qdrant_url, collection, management) == {"P4"}
    assert hits(qdrant_url, collection, either) == {"P1", "P2", "P4"}


def test_combined_tenant_and_principal_filtering(seeded, config, collection, qdrant_url):
    flt = rest.Filter(must=[*tenant_filter("tenant-A").must, principals_filter("finance")])

    result = hits(qdrant_url, collection, flt)
    assert result == {"P1", "P4"}
    assert "P3" not in result, "P3 holds 'finance' but belongs to tenant-B"


def test_source_id_restriction(seeded, config, collection, qdrant_url):
    flt = rest.Filter(must=[*tenant_filter("tenant-A").must, sources_filter("doc-2", "doc-4")])

    assert hits(qdrant_url, collection, flt) == {"P2", "P4"}


def test_no_matching_authorized_result(seeded, config, collection, qdrant_url):
    flt = rest.Filter(must=[*tenant_filter("tenant-A").must, principals_filter("legal")])

    assert hits(qdrant_url, collection, flt) == set()


def test_access_metadata_is_unchanged_after_storage_and_read_back(seeded, config):
    ids = [
        point_id_for(chunk.source.source.source_id, chunk.source.version, GENERATION, chunk.chunk_id)
        for chunk in seeded.chunks
    ]

    records = {record.chunk_id: record for record in read_chunks(ids, config=config)}

    for chunk_id, tenant, principals, _source_id in SAMPLES:
        stored = records[chunk_id]
        assert stored.access.tenant_id == tenant
        assert list(stored.access.acl_principals) == principals


def test_unfiltered_query_sees_every_tenant(seeded, config, collection, qdrant_url):
    """Control: without a filter the same query returns all four points."""
    assert hits(qdrant_url, collection, rest.Filter()) == {"P1", "P2", "P3", "P4"}
