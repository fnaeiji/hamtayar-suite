"""T025: consolidated failure/empty-result matrix for all retrieval operations."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from packages.contracts.access import AccessScope
from packages.retrieval import search as retrieval
from packages.retrieval.exceptions import (
    SearchEngineError,
    SearchMappingError,
    SearchScopeRequiredError,
    SearchValidationError,
)
from packages.storage.qdrant.config import StorageConfig
from packages.storage.search import SearchHit


@dataclass
class IdentityNormalizer:
    def normalize_text(self, text: str) -> str:
        return text


CONFIG = StorageConfig(vector_size=4, max_retries=0)
SCOPE = AccessScope(tenant_id="tenant-A", principals=["reader"])
NORMALIZER = IdentityNormalizer()


def _call(operation: str, **overrides):
    common = {"scope": SCOPE, "config": CONFIG, "limit": 5}
    common.update(overrides)
    if operation == "semantic":
        return retrieval.search_semantic(
            common.pop("query_vector", [0.1] * 4), **common
        )
    function = {
        "filter": retrieval.search_lexical_filter,
        "phrase": retrieval.search_lexical_phrase,
        "bm25": retrieval.search_lexical_bm25,
    }[operation]
    return function(common.pop("query_text", "search"), normalizer=NORMALIZER, **common)


@pytest.mark.parametrize("operation", ["semantic", "filter", "phrase", "bm25"])
def test_empty_engine_results_are_successful(operation, monkeypatch):
    monkeypatch.setattr(retrieval, _storage_name(operation), lambda *args, **kwargs: ())
    assert _call(operation).results == []


@pytest.mark.parametrize("operation", ["filter", "phrase", "bm25"])
@pytest.mark.parametrize("query", ["", "   "])
def test_empty_lexical_queries_are_validation_failures(operation, query):
    with pytest.raises(SearchValidationError):
        _call(operation, query_text=query)


@pytest.mark.parametrize("vector", [[], [0.1, 0.2]])
def test_invalid_vectors_are_validation_failures(vector):
    with pytest.raises(SearchValidationError):
        _call("semantic", query_vector=vector)


@pytest.mark.parametrize("operation", ["semantic", "filter", "phrase", "bm25"])
@pytest.mark.parametrize("limit", [0, -1, 101, True, 1.5])
def test_invalid_limits_are_validation_failures(operation, limit):
    with pytest.raises(SearchValidationError):
        _call(operation, limit=limit)


@pytest.mark.parametrize("operation", ["semantic", "filter", "phrase", "bm25"])
def test_missing_scope_fails_closed(operation):
    with pytest.raises(SearchScopeRequiredError):
        _call(operation, scope=None)


@pytest.mark.parametrize("operation", ["semantic", "filter", "phrase", "bm25"])
def test_non_intersecting_sources_return_empty_without_engine_call(
    operation, monkeypatch
):
    def forbidden(*args, **kwargs):
        raise AssertionError("engine must not be called")

    monkeypatch.setattr(retrieval, _storage_name(operation), forbidden)
    restricted = AccessScope(
        tenant_id="tenant-A", principals=["reader"], source_ids=["authorized"]
    )
    assert (
        _call(operation, scope=restricted, requested_source_ids=["other"]).results == []
    )


@pytest.mark.parametrize("operation", ["semantic", "filter", "phrase", "bm25"])
@pytest.mark.parametrize(
    "failure",
    [
        retrieval.storage_service.AdapterUnavailableError("unreachable"),
        retrieval.storage_service.AdapterTransientError("timeout"),
        retrieval.storage_service.AdapterPermanentError("missing collection or index"),
    ],
)
def test_transport_timeout_and_engine_rejections_remain_failures(
    operation, failure, monkeypatch
):
    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(retrieval, _storage_name(operation), fail)
    with pytest.raises(SearchEngineError):
        _call(operation)


@pytest.mark.parametrize("operation", ["semantic", "filter", "phrase", "bm25"])
def test_malformed_engine_hits_are_mapping_failures(operation, monkeypatch):
    malformed = SearchHit(
        point_id=uuid4(),
        chunk_id=None,
        text=None,
        source_id=None,
        version=None,
        generation_id=None,
        knowledge_space_id=None,
        source_type=None,
        kind=None,
        location=None,
        score=None,
    )
    monkeypatch.setattr(
        retrieval, _storage_name(operation), lambda *args, **kwargs: (malformed,)
    )
    with pytest.raises(SearchMappingError):
        _call(operation)


def _storage_name(operation: str) -> str:
    return {
        "semantic": "search_storage_semantic",
        "filter": "search_storage_lexical_filter",
        "phrase": "search_storage_lexical_phrase",
        "bm25": "search_storage_lexical_bm25",
    }[operation]
