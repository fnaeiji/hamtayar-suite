"""T017 (retrieval side): lexical filter and phrase search — normalization, mapping, access rules.

The engine is never involved: the storage seam is faked, and the normalizer is the real injected
`PersianNormalizer` (the approved composition approach).
"""

import pytest

from packages.contracts.access import AccessScope
from packages.contracts.errors import ErrorCode
from packages.contracts.retrieval import SearchResult
from packages.documents.normalization.service import PersianNormalizer
from packages.retrieval import search as search_module
from packages.retrieval.exceptions import (
    SearchEngineError,
    SearchMappingError,
    SearchScopeRequiredError,
    SearchValidationError,
)
from packages.storage.qdrant.config import StorageConfig
from packages.storage.service import AdapterUnavailableError, SearchFilter
from test.unit.retrieval.conftest import FakeStorageSearch, a_hit

CONFIG = StorageConfig(sleep=lambda _s: None)
SCOPE = AccessScope(tenant_id="tenant-A", principals=["finance"])
NORMALIZER = PersianNormalizer()


@pytest.fixture
def seam(install_search_seam):
    fake = FakeStorageSearch(hits=(a_hit("a", score=None), a_hit("b", score=None)))
    install_search_seam(search_module, fake)
    return fake


# ---- unranked lexical filter


def test_lexical_filter_maps_to_keyword_method_with_no_score(seam):
    response = search_module.search_lexical_filter(
        "search", scope=SCOPE, limit=5, config=CONFIG, normalizer=NORMALIZER
    )

    assert [result.evidence_id for result in response.results] == ["a", "b"]
    first = response.results[0]
    assert isinstance(first, SearchResult)
    assert first.retrieval_method == "keyword"
    assert first.score is None
    assert first.source.source.source_id == "doc-1"
    assert response.partial is False


def test_lexical_filter_query_is_normalized_before_storage(seam):
    search_module.search_lexical_filter(
        "جستجوي", scope=SCOPE, limit=5, config=CONFIG, normalizer=NORMALIZER
    )

    assert seam.calls[0]["query_text"] == "جستجوی"


def test_lexical_filter_passes_tenant_acl_source_and_generation(install_search_seam):
    fake = FakeStorageSearch(hits=())
    install_search_seam(search_module, fake)
    scope = AccessScope(
        tenant_id="tenant-A", principals=["finance"], source_ids=["doc-1", "doc-2"]
    )

    search_module.search_lexical_filter(
        "search",
        scope=scope,
        limit=5,
        config=CONFIG,
        normalizer=NORMALIZER,
        requested_source_ids=["doc-2"],
        generation_ids=["gen-7"],
    )

    passed = fake.calls[0]["search_filter"]
    assert isinstance(passed, SearchFilter)
    assert passed.tenant_id == "tenant-A"
    assert passed.principals == ("finance",)
    assert passed.source_ids == ("doc-2",)
    assert passed.generation_ids == ("gen-7",)


# ---- phrase search


def test_phrase_maps_to_keyword_method_and_keeps_the_engine_score(install_search_seam):
    fake = FakeStorageSearch(hits=(a_hit("only", score=2.49),))
    install_search_seam(search_module, fake)

    response = search_module.search_lexical_phrase(
        "semantic search", scope=SCOPE, limit=5, config=CONFIG, normalizer=NORMALIZER
    )

    assert [result.evidence_id for result in response.results] == ["only"]
    assert response.results[0].retrieval_method == "keyword"
    assert response.results[0].score == 2.49


def test_phrase_is_normalized_before_storage(install_search_seam):
    fake = FakeStorageSearch(hits=())
    install_search_seam(search_module, fake)

    search_module.search_lexical_phrase(
        "  می توان  ", scope=SCOPE, limit=5, config=CONFIG, normalizer=NORMALIZER
    )

    assert (
        fake.calls[0]["phrase"] == "می‌توان"
    )  # ZWNJ form, from the existing normalizer


# ---- validation


@pytest.mark.parametrize("query", ["", "   ", "\u200c"])
def test_empty_query_is_a_validation_error(seam, query):
    with pytest.raises(SearchValidationError) as excinfo:
        search_module.search_lexical_filter(
            query, scope=SCOPE, limit=5, config=CONFIG, normalizer=NORMALIZER
        )

    assert excinfo.value.error_code is ErrorCode.VALIDATION_ERROR
    assert seam.calls == []


def test_oversized_query_is_a_validation_error(seam):
    with pytest.raises(SearchValidationError, match="at most"):
        search_module.search_lexical_filter(
            "x" * 600, scope=SCOPE, limit=5, config=CONFIG, normalizer=NORMALIZER
        )
    assert seam.calls == []


@pytest.mark.parametrize("limit", [0, -1, 101])
def test_invalid_limit_is_a_validation_error(seam, limit):
    with pytest.raises(SearchValidationError):
        search_module.search_lexical_filter(
            "search", scope=SCOPE, limit=limit, config=CONFIG, normalizer=NORMALIZER
        )
    assert seam.calls == []


def test_missing_scope_fails_closed_for_lexical(seam):
    with pytest.raises(SearchScopeRequiredError):
        search_module.search_lexical_filter(
            "search", scope=None, limit=5, config=CONFIG, normalizer=NORMALIZER
        )
    assert seam.calls == []


def test_missing_scope_fails_closed_for_phrase(seam):
    with pytest.raises(SearchScopeRequiredError):
        search_module.search_lexical_phrase(
            "semantic search", scope=None, limit=5, config=CONFIG, normalizer=NORMALIZER
        )
    assert seam.calls == []


# ---- access shortcuts and failures


def test_empty_source_intersection_returns_empty_without_a_call(install_search_seam):
    fake = FakeStorageSearch(hits=(a_hit("a"),))
    install_search_seam(search_module, fake)
    scope = AccessScope(
        tenant_id="tenant-A", principals=["finance"], source_ids=["doc-1"]
    )

    response = search_module.search_lexical_filter(
        "search",
        scope=scope,
        limit=5,
        config=CONFIG,
        normalizer=NORMALIZER,
        requested_source_ids=["doc-9"],
    )

    assert response.results == []
    assert fake.calls == []


def test_no_match_returns_empty_response(seam):
    seam.hits = ()

    response = search_module.search_lexical_filter(
        "absent", scope=SCOPE, limit=5, config=CONFIG, normalizer=NORMALIZER
    )

    assert response.results == []
    assert response.partial is False


def test_engine_failure_is_translated(seam):
    seam.error = AdapterUnavailableError("connection refused")

    with pytest.raises(SearchEngineError) as excinfo:
        search_module.search_lexical_phrase(
            "semantic search",
            scope=SCOPE,
            limit=5,
            config=CONFIG,
            normalizer=NORMALIZER,
        )

    assert excinfo.value.error_code is ErrorCode.STORAGE_ERROR


def test_malformed_payload_is_a_mapping_error(install_search_seam):
    fake = FakeStorageSearch(hits=(a_hit("a", version=None),))
    install_search_seam(search_module, fake)

    with pytest.raises(SearchMappingError) as excinfo:
        search_module.search_lexical_filter(
            "search", scope=SCOPE, limit=5, config=CONFIG, normalizer=NORMALIZER
        )

    assert excinfo.value.error_code is ErrorCode.PROCESSING_FAILED
