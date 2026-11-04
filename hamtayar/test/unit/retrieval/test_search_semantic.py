"""T013 (retrieval side): semantic search semantics, validation and contract mapping.

Storage is replaced by the fake seam from `test/unit/retrieval/conftest.py`, so no engine is needed.
"""

import pytest

from packages.contracts.access import AccessScope
from packages.contracts.errors import ErrorCode
from packages.contracts.retrieval import RetrievalResponse, SearchResult
from packages.retrieval import search as search_module
from packages.retrieval.exceptions import (
    SearchEngineError,
    SearchMappingError,
    SearchScopeRequiredError,
    SearchValidationError,
)
from packages.storage.qdrant.config import StorageConfig
from packages.storage.service import SearchFilter
from test.unit.retrieval.conftest import FakeStorageSearch, a_hit

CONFIG = StorageConfig(sleep=lambda _s: None)
SCOPE = AccessScope(tenant_id="tenant-A", principals=["finance"])
VECTOR = [0.1, 0.2, 0.3, 0.4]


@pytest.fixture
def seam(install_search_seam):
    fake = FakeStorageSearch(hits=(a_hit("c1", score=0.9), a_hit("c2", score=0.4)))
    install_search_seam(search_module, fake)
    return fake


# ---- happy path and mapping


def test_semantic_search_maps_hits_to_retrieval_contracts(seam):
    response = search_module.search_semantic(
        VECTOR, scope=SCOPE, limit=5, config=CONFIG
    )

    assert isinstance(response, RetrievalResponse)
    assert [result.evidence_id for result in response.results] == ["c1", "c2"]
    first = response.results[0]
    assert isinstance(first, SearchResult)
    assert first.retrieval_method == "semantic"
    assert first.score == 0.9
    assert first.source.source.source_id == "doc-1"
    assert first.source.version == "v1"
    assert first.generation_id == "gen-1"
    assert response.partial is False


def test_result_order_and_scores_follow_the_engine(seam):
    seam.hits = (
        a_hit("top", score=0.99),
        a_hit("middle", score=0.5),
        a_hit("last", score=0.01),
    )

    response = search_module.search_semantic(
        VECTOR, scope=SCOPE, limit=10, config=CONFIG
    )

    assert [result.evidence_id for result in response.results] == [
        "top",
        "middle",
        "last",
    ]
    assert [result.score for result in response.results] == [0.99, 0.5, 0.01]


def test_tenant_and_principal_restrictions_reach_storage(seam):
    search_module.search_semantic(VECTOR, scope=SCOPE, limit=5, config=CONFIG)

    passed = seam.calls[0]["search_filter"]
    assert isinstance(passed, SearchFilter)
    assert passed.tenant_id == "tenant-A"
    assert passed.principals == ("finance",)
    assert passed.source_ids is None
    assert passed.generation_ids is None


def test_generation_restriction_is_passed_through(seam):
    search_module.search_semantic(
        VECTOR, scope=SCOPE, limit=5, config=CONFIG, generation_ids=["gen-9"]
    )

    assert seam.calls[0]["search_filter"].generation_ids == ("gen-9",)


# ---- source intersection (decision D)


def test_scope_only_source_restriction_is_used(install_search_seam):
    fake = FakeStorageSearch(hits=())
    install_search_seam(search_module, fake)
    scope = AccessScope(
        tenant_id="tenant-A", principals=["finance"], source_ids=["doc-1", "doc-2"]
    )

    search_module.search_semantic(VECTOR, scope=scope, limit=5, config=CONFIG)

    assert fake.calls[0]["search_filter"].source_ids == ("doc-1", "doc-2")


def test_request_narrows_scope_sources(install_search_seam):
    fake = FakeStorageSearch(hits=())
    install_search_seam(search_module, fake)
    scope = AccessScope(
        tenant_id="tenant-A", principals=["finance"], source_ids=["doc-1", "doc-2"]
    )

    search_module.search_semantic(
        VECTOR, scope=scope, limit=5, config=CONFIG, requested_source_ids=["doc-2"]
    )

    assert fake.calls[0]["search_filter"].source_ids == ("doc-2",)


def test_request_source_restriction_is_the_intersection_with_the_scope(
    install_search_seam,
):
    """The request can only narrow: a source outside the scope is dropped, not added."""
    fake = FakeStorageSearch(hits=())
    install_search_seam(search_module, fake)
    scope = AccessScope(
        tenant_id="tenant-A", principals=["finance"], source_ids=["doc-1", "doc-2"]
    )

    search_module.search_semantic(
        VECTOR,
        scope=scope,
        limit=5,
        config=CONFIG,
        requested_source_ids=["doc-1", "doc-9"],
    )

    assert fake.calls[0]["search_filter"].source_ids == ("doc-1",)


def test_non_intersecting_sources_return_empty_without_a_query(install_search_seam):
    fake = FakeStorageSearch(hits=(a_hit("c1"),))
    install_search_seam(search_module, fake)
    scope = AccessScope(
        tenant_id="tenant-A", principals=["finance"], source_ids=["doc-1"]
    )

    response = search_module.search_semantic(
        VECTOR, scope=scope, limit=5, config=CONFIG, requested_source_ids=["doc-2"]
    )

    assert response.results == []
    assert fake.calls == [], "deny-all must short-circuit before any engine call"


def test_request_only_sources_are_used_while_tenant_and_acl_stay(install_search_seam):
    fake = FakeStorageSearch(hits=())
    install_search_seam(search_module, fake)

    search_module.search_semantic(
        VECTOR, scope=SCOPE, limit=5, config=CONFIG, requested_source_ids=["doc-7"]
    )

    passed = fake.calls[0]["search_filter"]
    assert passed.source_ids == ("doc-7",)
    assert passed.tenant_id == "tenant-A"
    assert passed.principals == ("finance",)


# ---- validation and fail-closed


def test_missing_scope_fails_closed(seam):
    with pytest.raises(SearchScopeRequiredError) as excinfo:
        search_module.search_semantic(VECTOR, scope=None, limit=5, config=CONFIG)

    assert excinfo.value.error_code is ErrorCode.ACCESS_DENIED
    assert seam.calls == []


def test_the_scope_contract_forbids_empty_tenant_or_principals():
    """Fail-closed starts at the contract: an unusable scope cannot even be constructed."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AccessScope(tenant_id="t", principals=[])
    with pytest.raises(ValidationError):
        AccessScope(tenant_id="", principals=["finance"])


@pytest.mark.parametrize("limit", [0, -3, 101])
def test_invalid_limit_is_a_validation_error(seam, limit):
    with pytest.raises(SearchValidationError) as excinfo:
        search_module.search_semantic(VECTOR, scope=SCOPE, limit=limit, config=CONFIG)

    assert excinfo.value.error_code is ErrorCode.VALIDATION_ERROR
    assert seam.calls == []


def test_empty_vector_is_a_validation_error(seam):
    with pytest.raises(SearchValidationError):
        search_module.search_semantic([], scope=SCOPE, limit=5, config=CONFIG)
    assert seam.calls == []


def test_wrong_dimension_is_a_validation_error(seam):
    with pytest.raises(SearchValidationError, match="dimension"):
        search_module.search_semantic([0.1, 0.2], scope=SCOPE, limit=5, config=CONFIG)
    assert seam.calls == []


# ---- empty results, operational failures, mapping failures


def test_no_matches_returns_an_empty_valid_response(seam):
    seam.hits = ()

    response = search_module.search_semantic(
        VECTOR, scope=SCOPE, limit=5, config=CONFIG
    )

    assert response.results == []
    assert response.partial is False


def test_engine_failure_is_translated(seam):
    from packages.storage.service import AdapterUnavailableError

    seam.error = AdapterUnavailableError("connection refused")

    with pytest.raises(SearchEngineError) as excinfo:
        search_module.search_semantic(VECTOR, scope=SCOPE, limit=5, config=CONFIG)

    assert excinfo.value.error_code is ErrorCode.STORAGE_ERROR
    assert isinstance(excinfo.value.__cause__, AdapterUnavailableError)


def test_public_storage_failures_propagate_unchanged(seam):
    from packages.storage.exceptions import StoreTimeoutError

    seam.error = StoreTimeoutError("target unavailable", result=_store_result())

    with pytest.raises(StoreTimeoutError):
        search_module.search_semantic(VECTOR, scope=SCOPE, limit=5, config=CONFIG)


def test_malformed_payload_is_a_mapping_error(install_search_seam):
    broken = a_hit("c1", source_id=None)
    fake = FakeStorageSearch(hits=(broken,))
    install_search_seam(search_module, fake)

    with pytest.raises(SearchMappingError) as excinfo:
        search_module.search_semantic(VECTOR, scope=SCOPE, limit=5, config=CONFIG)

    assert excinfo.value.error_code is ErrorCode.PROCESSING_FAILED


def _store_result():
    from packages.contracts.storage import StoreFailure, StoreResult

    failure = StoreFailure(
        chunk_id="c1", category="timeout", reason="unavailable", retryable=True
    )
    return StoreResult(requested=1, stored=0, failed=1, failures=(failure,))
