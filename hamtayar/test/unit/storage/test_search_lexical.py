"""T016 (storage side): unranked lexical filtering and phrase search, against a fake adapter."""

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


def a_hit(chunk_id: str, score: float | None = None) -> SearchHit:
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


def test_lexical_filter_uses_filter_mode_and_keeps_scores_none(fake_adapter):
    fake_adapter.hits = (a_hit("a"), a_hit("b"))

    result = service.search_lexical_filter(
        "search", search_filter=FILTER, limit=4, config=CONFIG
    )

    assert [hit.chunk_id for hit in result] == ["a", "b"]
    query, passed_filter = fake_adapter.instances[0].calls[0]
    assert query.mode is SearchMode.FILTER
    assert query.text == "search"
    assert query.limit == 4
    assert passed_filter == FILTER
    assert all(hit.score is None for hit in result)


def test_phrase_uses_phrase_mode_and_passes_the_phrase_verbatim(fake_adapter):
    fake_adapter.hits = (a_hit("a"),)

    service.search_lexical_phrase(
        "semantic search", search_filter=FILTER, limit=3, config=CONFIG
    )

    query, _ = fake_adapter.instances[0].calls[0]
    assert query.mode is SearchMode.PHRASE
    assert query.text == "semantic search"
    assert query.limit == 3


def test_phrase_service_preserves_adapter_score_semantics(fake_adapter):
    fake_adapter.hits = (a_hit("a", score=None),)

    result = service.search_lexical_phrase(
        "semantic search", search_filter=FILTER, limit=3, config=CONFIG
    )

    assert result[0].score is None


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_blank_lexical_query_is_rejected(fake_adapter, text):
    with pytest.raises(ValueError, match="must not be empty"):
        service.search_lexical_filter(
            text, search_filter=FILTER, limit=5, config=CONFIG
        )
    assert fake_adapter.instances == []


@pytest.mark.parametrize("text", ["", "  "])
def test_blank_phrase_is_rejected(fake_adapter, text):
    with pytest.raises(ValueError, match="must not be empty"):
        service.search_lexical_phrase(
            text, search_filter=FILTER, limit=5, config=CONFIG
        )
    assert fake_adapter.instances == []


def test_invalid_limit_is_rejected(fake_adapter):
    with pytest.raises(ValueError, match="limit"):
        service.search_lexical_filter(
            "search", search_filter=FILTER, limit=0, config=CONFIG
        )
    assert fake_adapter.instances == []


def test_engine_failures_propagate_from_the_storage_boundary(fake_adapter):
    fake_adapter.error = adapter_module.AdapterPermanentError(
        "404 collection not found"
    )

    with pytest.raises(adapter_module.AdapterPermanentError):
        service.search_lexical_phrase(
            "semantic search", search_filter=FILTER, limit=5, config=CONFIG
        )
