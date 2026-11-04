"""T021 (storage side): the native BM25 entry point, against a fake adapter."""

import uuid
from typing import ClassVar

import pytest

from packages.storage import service
from packages.storage.qdrant import adapter as adapter_module
from packages.storage.qdrant.config import StorageConfig
from packages.storage.search import SearchFilter, SearchHit, SearchMode


class FakeAdapter:
    instances: ClassVar[list["FakeAdapter"]] = []
    hits: tuple[SearchHit, ...] = ()
    error: Exception | None = None

    def __init__(self, config):
        self.config = config
        self.calls = []
        FakeAdapter.instances.append(self)

    def search(self, query, search_filter):
        self.calls.append((query, search_filter))
        if FakeAdapter.error is not None:
            raise FakeAdapter.error
        return FakeAdapter.hits


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
def fake_adapter(monkeypatch):
    FakeAdapter.instances = []
    FakeAdapter.hits = ()
    FakeAdapter.error = None
    monkeypatch.setattr(service, "QdrantAdapter", FakeAdapter)
    return FakeAdapter


CONFIG = StorageConfig(sleep=lambda _s: None)
FILTER = SearchFilter(tenant_id="tenant-A", principals=("finance",))


def test_bm25_uses_bm25_mode_and_keeps_engine_scores(fake_adapter):
    fake_adapter.hits = (
        a_hit("top", 1.039265),
        a_hit("mid", 0.836971),
        a_hit("low", 0.219774),
    )

    result = service.search_lexical_bm25(
        "search", search_filter=FILTER, limit=10, config=CONFIG
    )

    assert [hit.chunk_id for hit in result] == ["top", "mid", "low"]
    assert [hit.score for hit in result] == [1.039265, 0.836971, 0.219774]
    query, passed_filter = fake_adapter.instances[0].calls[0]
    assert query.mode is SearchMode.BM25
    assert query.text == "search"
    assert query.limit == 10
    assert passed_filter == FILTER


def test_engine_order_is_not_recalculated(fake_adapter):
    """Retrieval must not re-rank: the engine's descending order is preserved verbatim."""
    fake_adapter.hits = (a_hit("a", 0.9), a_hit("b", 0.1))

    assert [
        h.chunk_id
        for h in service.search_lexical_bm25(
            "search", search_filter=FILTER, limit=5, config=CONFIG
        )
    ] == ["a", "b"]


def test_no_match_returns_empty_tuple(fake_adapter):
    fake_adapter.hits = ()

    assert (
        service.search_lexical_bm25(
            "absent", search_filter=FILTER, limit=5, config=CONFIG
        )
        == ()
    )


@pytest.mark.parametrize("text", ["", "   "])
def test_blank_query_is_rejected(fake_adapter, text):
    with pytest.raises(ValueError, match="must not be empty"):
        service.search_lexical_bm25(text, search_filter=FILTER, limit=5, config=CONFIG)
    assert fake_adapter.instances == []


@pytest.mark.parametrize("limit", [0, -2])
def test_invalid_limit_is_rejected(fake_adapter, limit):
    with pytest.raises(ValueError, match="limit"):
        service.search_lexical_bm25(
            "search", search_filter=FILTER, limit=limit, config=CONFIG
        )
    assert fake_adapter.instances == []


@pytest.mark.parametrize(
    "error",
    [
        adapter_module.AdapterTransientError("503 after retries"),
        adapter_module.AdapterPermanentError("index not found"),
        adapter_module.AdapterUnavailableError("connection refused"),
    ],
)
def test_engine_failures_propagate_from_the_storage_boundary(fake_adapter, error):
    fake_adapter.error = error

    with pytest.raises(type(error)):
        service.search_lexical_bm25(
            "search", search_filter=FILTER, limit=5, config=CONFIG
        )
