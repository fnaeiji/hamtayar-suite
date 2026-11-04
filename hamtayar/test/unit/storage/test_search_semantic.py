"""T012 (storage side): the semantic search entry point, against a fake adapter.

The fake replaces `QdrantAdapter` inside `packages.storage.service`, so these tests need no engine.
"""

import uuid
from typing import ClassVar

import pytest

from packages.storage import service
from packages.storage.qdrant import adapter as adapter_module
from packages.storage.qdrant.config import StorageConfig
from packages.storage.search import SearchFilter, SearchHit


class FakeSearchAdapter:
    """Duck-typed adapter exposing only `search`; records what the service passed down."""

    instances: ClassVar[list["FakeSearchAdapter"]] = []
    hits: tuple[SearchHit, ...] = ()
    error: Exception | None = None

    def __init__(self, config):
        self.config = config
        self.calls = []
        FakeSearchAdapter.instances.append(self)

    def search(self, query, search_filter):
        self.calls.append((query, search_filter))
        if FakeSearchAdapter.error is not None:
            raise FakeSearchAdapter.error
        return FakeSearchAdapter.hits


def a_hit(chunk_id: str, score: float) -> SearchHit:
    return SearchHit(
        point_id=uuid.uuid4(),
        chunk_id=chunk_id,
        text=f"text {chunk_id}",
        source_id="doc-1",
        version="v1",
        generation_id="gen-1",
        knowledge_space_id="ks-1",
        source_type="document",
        kind="document",
        location=None,
        score=score,
    )


@pytest.fixture
def fake_search_adapter(monkeypatch):
    FakeSearchAdapter.instances = []
    FakeSearchAdapter.hits = ()
    FakeSearchAdapter.error = None
    monkeypatch.setattr(service, "QdrantAdapter", FakeSearchAdapter)
    return FakeSearchAdapter


CONFIG = StorageConfig(sleep=lambda _s: None)
FILTER = SearchFilter(tenant_id="tenant-A", principals=("finance",))


def test_semantic_search_passes_vector_limit_and_filter(fake_search_adapter):
    fake_search_adapter.hits = (a_hit("c1", 0.9), a_hit("c2", 0.5))

    result = service.search_semantic(
        [0.1, 0.2, 0.3, 0.4], search_filter=FILTER, limit=7, config=CONFIG
    )

    assert [hit.chunk_id for hit in result] == ["c1", "c2"]
    query, passed_filter = fake_search_adapter.instances[0].calls[0]
    assert query.vector == [0.1, 0.2, 0.3, 0.4]
    assert query.limit == 7
    assert query.mode is None  # semantic path
    assert passed_filter == FILTER


def test_engine_order_is_preserved(fake_search_adapter):
    fake_search_adapter.hits = (a_hit("z", 0.99), a_hit("a", 0.11))

    result = service.search_semantic(
        [0.1, 0.2, 0.3, 0.4], search_filter=FILTER, limit=10, config=CONFIG
    )

    assert [hit.chunk_id for hit in result] == ["z", "a"]
    assert [hit.score for hit in result] == [0.99, 0.11]


def test_empty_engine_result_is_returned_as_an_empty_tuple(fake_search_adapter):
    fake_search_adapter.hits = ()

    assert (
        service.search_semantic(
            [0.1, 0.2, 0.3, 0.4], search_filter=FILTER, limit=5, config=CONFIG
        )
        == ()
    )


@pytest.mark.parametrize("limit", [0, -1])
def test_invalid_limit_is_rejected_before_the_engine(fake_search_adapter, limit):
    with pytest.raises(ValueError, match="limit"):
        service.search_semantic(
            [0.1, 0.2, 0.3, 0.4], search_filter=FILTER, limit=limit, config=CONFIG
        )
    assert fake_search_adapter.instances == []


def test_empty_vector_is_rejected(fake_search_adapter):
    with pytest.raises(ValueError, match="must not be empty"):
        service.search_semantic([], search_filter=FILTER, limit=5, config=CONFIG)
    assert fake_search_adapter.instances == []


def test_wrong_dimension_is_rejected(fake_search_adapter):
    with pytest.raises(ValueError, match="dimension"):
        service.search_semantic(
            [0.1, 0.2], search_filter=FILTER, limit=5, config=CONFIG
        )
    assert fake_search_adapter.instances == []


def test_engine_failure_propagates(fake_search_adapter):
    fake_search_adapter.error = adapter_module.AdapterUnavailableError(
        "connection refused"
    )

    with pytest.raises(adapter_module.AdapterUnavailableError):
        service.search_semantic(
            [0.1, 0.2, 0.3, 0.4], search_filter=FILTER, limit=5, config=CONFIG
        )
