"""T022 (retrieval side): native BM25 orchestration — validation, mapping, access, failures.

BM25 must stay distinguishable from unranked lexical filtering: same `retrieval_method="keyword"`,
but a **real numeric engine score** instead of `None`.
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
    fake = FakeStorageSearch(
        hits=(a_hit("top", score=1.039265), a_hit("mid", score=0.219774))
    )
    install_search_seam(search_module, fake)
    return fake


def _bm25(text="search", *, scope=SCOPE, limit=10, config=CONFIG, **kwargs):
    return search_module.search_lexical_bm25(
        text, scope=scope, config=config, normalizer=NORMALIZER, limit=limit, **kwargs
    )


# ---- happy path


def test_bm25_keeps_real_scores_and_engine_order(seam):
    response = _bm25()

    assert [result.evidence_id for result in response.results] == ["top", "mid"]
    assert [result.score for result in response.results] == [1.039265, 0.219774]
    assert all(isinstance(result.score, float) for result in response.results)


def test_bm25_maps_to_keyword_method_with_a_score(seam):
    result = _bm25().results[0]

    assert isinstance(result, SearchResult)
    assert result.retrieval_method == "keyword"
    assert result.score is not None, "BM25 must carry the engine relevance score"
    assert result.source.source.source_id == "doc-1"
    assert result.generation_id == "gen-1"


def test_bm25_and_unranked_filtering_are_distinguishable(install_search_seam):
    """Same method label, different score semantics — the documented invariant for T030."""
    fake = FakeStorageSearch(hits=(a_hit("x", score=0.7),))
    install_search_seam(search_module, fake)
    bm25 = search_module.search_lexical_bm25(
        "search", scope=SCOPE, config=CONFIG, normalizer=NORMALIZER
    ).results[0]

    fake.hits = (a_hit("x", score=None),)
    filtered = search_module.search_lexical_filter(
        "search", scope=SCOPE, config=CONFIG, normalizer=NORMALIZER
    ).results[0]

    assert bm25.retrieval_method == filtered.retrieval_method == "keyword"
    assert bm25.score == 0.7 and filtered.score is None


def test_query_is_normalized_before_the_engine(seam):
    _bm25("جستجوي")

    assert seam.calls[0]["query_text"] == "جستجوی"


def test_access_filter_is_passed_with_all_restrictions(install_search_seam):
    fake = FakeStorageSearch(hits=())
    install_search_seam(search_module, fake)
    scope = AccessScope(
        tenant_id="tenant-A", principals=["finance"], source_ids=["doc-1", "doc-2"]
    )

    search_module.search_lexical_bm25(
        "search",
        scope=scope,
        config=CONFIG,
        normalizer=NORMALIZER,
        requested_source_ids=["doc-2"],
        generation_ids=["gen-7"],
    )

    passed = fake.calls[0]["search_filter"]
    assert isinstance(passed, SearchFilter)
    assert (passed.tenant_id, passed.principals) == ("tenant-A", ("finance",))
    assert passed.source_ids == ("doc-2",)
    assert passed.generation_ids == ("gen-7",)


# ---- validation and fail-closed


@pytest.mark.parametrize("query", ["", "   "])
def test_blank_query_is_a_validation_error(seam, query):
    with pytest.raises(SearchValidationError) as excinfo:
        _bm25(query)

    assert excinfo.value.error_code is ErrorCode.VALIDATION_ERROR
    assert seam.calls == []


@pytest.mark.parametrize("limit", [0, -1, 101])
def test_invalid_limit_is_a_validation_error(seam, limit):
    with pytest.raises(SearchValidationError):
        _bm25(limit=limit)
    assert seam.calls == []


def test_missing_scope_fails_closed(seam):
    with pytest.raises(SearchScopeRequiredError) as excinfo:
        _bm25(scope=None)

    assert excinfo.value.error_code is ErrorCode.ACCESS_DENIED
    assert seam.calls == []


def test_empty_source_intersection_denies_without_a_call(install_search_seam):
    fake = FakeStorageSearch(hits=(a_hit("x", score=1.0),))
    install_search_seam(search_module, fake)
    scope = AccessScope(
        tenant_id="tenant-A", principals=["finance"], source_ids=["doc-1"]
    )

    response = search_module.search_lexical_bm25(
        "search",
        scope=scope,
        config=CONFIG,
        normalizer=NORMALIZER,
        requested_source_ids=["doc-9"],
    )

    assert response.results == []
    assert fake.calls == []


# ---- results and failures


def test_no_match_is_a_valid_empty_result(seam):
    seam.hits = ()

    response = _bm25()

    assert response.results == []
    assert response.partial is False


def test_engine_failure_is_translated(seam):
    seam.error = AdapterUnavailableError("connection refused")

    with pytest.raises(SearchEngineError) as excinfo:
        _bm25()

    assert excinfo.value.error_code is ErrorCode.STORAGE_ERROR
    assert isinstance(excinfo.value.__cause__, AdapterUnavailableError)


def test_malformed_engine_record_is_a_mapping_error(install_search_seam):
    fake = FakeStorageSearch(hits=(a_hit("x", source_id=None),))
    install_search_seam(search_module, fake)

    with pytest.raises(SearchMappingError) as excinfo:
        search_module.search_lexical_bm25(
            "search", scope=SCOPE, config=CONFIG, normalizer=NORMALIZER
        )

    assert excinfo.value.error_code is ErrorCode.PROCESSING_FAILED
