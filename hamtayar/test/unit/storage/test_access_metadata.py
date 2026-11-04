"""Access metadata as it actually reaches Qdrant: payload copies and read-back reconstruction.

The contracts themselves (`AccessMetadata`, `TrustedAccessContext`, `AccessScope`) are covered by
`test/contracts/test_access.py`; these tests cover what the storage layer does with them.
"""

import uuid

import pytest

from packages.contracts.access import AccessMetadata
from packages.contracts.chunks import Chunk
from packages.contracts.common import SourceLocation, SourceRef, SourceVersion
from packages.contracts.indexing import EmbeddingRecord
from packages.contracts.storage import PayloadField
from packages.storage import service
from packages.storage.qdrant import adapter as adapter_module
from packages.storage.qdrant.adapter import build_payload
from packages.storage.qdrant.config import StorageConfig


def a_chunk(chunk_id: str, *, tenant: str, principals: list[str], source_id: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        source=SourceVersion(
            source=SourceRef(source_id=source_id, knowledge_space_id="ks-1", source_type="document"),
            version="v1",
        ),
        kind="document",
        text="متن فارسی English",
        access=AccessMetadata(tenant_id=tenant, acl_principals=principals),
        location=SourceLocation(page=1),
    )


def an_embedding(chunk_id: str) -> EmbeddingRecord:
    return EmbeddingRecord(chunk_id=chunk_id, model_id="embed-4d", vector=[0.1, 0.2, 0.3, 0.4])


# ---- payload construction


def test_tenant_and_principals_are_copied_into_the_payload():
    chunk = a_chunk("c1", tenant="tenant-A", principals=["finance"], source_id="doc-1")

    payload = build_payload(chunk, an_embedding("c1"), "gen-1")

    assert payload[PayloadField.TENANT_ID] == "tenant-A"
    assert payload[PayloadField.ACL_PRINCIPALS] == ["finance"]


def test_multiple_principals_are_preserved_in_order():
    principals = ["finance", "management", "u:42"]
    chunk = a_chunk("c1", tenant="tenant-A", principals=principals, source_id="doc-1")

    payload = build_payload(chunk, an_embedding("c1"), "gen-1")

    assert payload[PayloadField.ACL_PRINCIPALS] == principals
    assert isinstance(payload[PayloadField.ACL_PRINCIPALS], list)


def test_different_tenants_reach_the_payload_unchanged():
    first = build_payload(
        a_chunk("c1", tenant="tenant-A", principals=["finance"], source_id="doc-1"),
        an_embedding("c1"),
        "gen-1",
    )
    second = build_payload(
        a_chunk("c2", tenant="tenant-B", principals=["finance"], source_id="doc-2"),
        an_embedding("c2"),
        "gen-1",
    )

    assert first[PayloadField.TENANT_ID] == "tenant-A"
    assert second[PayloadField.TENANT_ID] == "tenant-B"
    assert first[PayloadField.TENANT_ID] != second[PayloadField.TENANT_ID]


def test_the_payload_holds_a_copy_not_the_caller_list():
    principals = ["finance"]
    chunk = a_chunk("c1", tenant="tenant-A", principals=principals, source_id="doc-1")

    payload = build_payload(chunk, an_embedding("c1"), "gen-1")
    principals.append("management")

    assert payload[PayloadField.ACL_PRINCIPALS] == ["finance"]


# ---- read-back reconstruction


class PayloadOnlyAdapter:
    """Returns the payloads it was given; enough to exercise `read_chunks` reconstruction."""

    payloads: dict = {}

    def __init__(self, config):
        self.config = config

    def read(self, ids):
        return {point_id: (self.payloads[point_id], [0.1, 0.2, 0.3, 0.4])
                for point_id in ids if point_id in self.payloads}


@pytest.fixture
def adapter_with_payloads(monkeypatch):
    PayloadOnlyAdapter.payloads = {}
    monkeypatch.setattr(service, "QdrantAdapter", PayloadOnlyAdapter)

    def register(chunk: Chunk, point_id=None):
        from packages.storage.qdrant.adapter import point_id_for

        pid = point_id or point_id_for(
            chunk.source.source.source_id, chunk.source.version, "gen-1", chunk.chunk_id
        )
        PayloadOnlyAdapter.payloads[pid] = build_payload(chunk, an_embedding(chunk.chunk_id), "gen-1")
        return pid

    return register


def test_read_back_restores_tenant_and_principals(adapter_with_payloads):
    chunk = a_chunk("c1", tenant="tenant-A", principals=["finance", "management"], source_id="doc-1")
    point_id = adapter_with_payloads(chunk)

    records = service.read_chunks([point_id], config=StorageConfig())

    assert len(records) == 1
    assert records[0].access.tenant_id == "tenant-A"
    assert list(records[0].access.acl_principals) == ["finance", "management"]


def test_read_back_keeps_tenants_separate(adapter_with_payloads):
    first = a_chunk("c1", tenant="tenant-A", principals=["finance"], source_id="doc-1")
    second = a_chunk("c2", tenant="tenant-B", principals=["finance"], source_id="doc-2")
    ids = [adapter_with_payloads(first), adapter_with_payloads(second)]

    records = {record.chunk_id: record for record in service.read_chunks(ids, config=StorageConfig())}

    assert records["c1"].access.tenant_id == "tenant-A"
    assert records["c2"].access.tenant_id == "tenant-B"
    assert records["c1"].access.acl_principals == ["finance"]


def test_missing_access_metadata_is_a_read_back_failure(adapter_with_payloads):
    chunk = a_chunk("c1", tenant="tenant-A", principals=["finance"], source_id="doc-1")
    point_id = adapter_with_payloads(chunk)
    payload = PayloadOnlyAdapter.payloads[point_id]
    payload.pop(PayloadField.TENANT_ID)

    with pytest.raises(service.ReadBackMismatchError) as excinfo:
        service.read_chunks([point_id], config=StorageConfig())

    assert excinfo.value.result.failed == 1


def test_unknown_point_id_reports_what_it_could_not_read(adapter_with_payloads):
    with pytest.raises(service.ReadBackMismatchError) as excinfo:
        service.read_chunks([uuid.uuid4()], config=StorageConfig())

    assert excinfo.value.result.failed == 1
    assert excinfo.value.result.failures[0].category.value == "read_back"
