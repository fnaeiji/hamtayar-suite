
import pytest
from pydantic import ValidationError

from packages.contracts.access import AccessScope
from packages.contracts.common import (
    SourceLocation,
    SourceRef,
    SourceVersion,
)
from packages.contracts.retrieval import (
    RetrievalQuery,
    RetrievalResponse,
    SearchRequest,
    SearchResult,
)


@pytest.fixture
def source_version():
    """Create a valid document source version."""
    return SourceVersion(
        source=SourceRef(
            source_id="doc-101",
            knowledge_space_id="engineering",
            source_type="document",
        ),
        version="v1",
    )


@pytest.fixture
def valid_scope():
    """Create a valid authorized search scope."""
    return AccessScope(
        tenant_id="company-1",
        principals=["user-101", "team-hamtayar"],
        source_ids=["doc-101"],
    )


@pytest.fixture
def valid_query(valid_scope):
    """Create a valid internal retrieval query."""
    return RetrievalQuery(
        request=SearchRequest(
            query="What is Hamtayar?",
            top_k=5,
        ),
        scope=valid_scope,
        generation_ids=["gen-001"],
    )


@pytest.fixture
def valid_result(source_version):
    """Create a valid search result."""
    return SearchResult(
        evidence_id="chunk-101",
        source=source_version,
        generation_id="gen-001",
        retrieval_method="hybrid",
        text="Hamtayar is an enterprise RAG system.",
        location=SourceLocation(
            page=2,
            section="Architecture",
        ),
        score=0.91,
    )


# SearchRequest tests

def test_search_request_valid():
    request = SearchRequest(
        query="What is Hamtayar?",
        mode="semantic",
        top_k=5,
    )

    assert request.query == "What is Hamtayar?"
    assert request.mode == "semantic"
    assert request.top_k == 5


def test_search_request_defaults():
    request = SearchRequest(query="Sample query")

    assert request.mode == "hybrid"
    assert request.top_k == 10
    assert request.source_ids is None


@pytest.mark.parametrize(
    "mode",
    ["keyword", "semantic", "hybrid", "code"],
)
def test_search_request_accepts_supported_modes(mode):
    request = SearchRequest(
        query="Sample query",
        mode=mode,
    )

    assert request.mode == mode


def test_search_request_rejects_empty_query():
    with pytest.raises(ValidationError):
        SearchRequest(query="")


@pytest.mark.parametrize("top_k", [0, -1, 101, 1000])
def test_search_request_rejects_invalid_top_k(top_k):
    with pytest.raises(ValidationError):
        SearchRequest(
            query="Sample query",
            top_k=top_k,
        )


@pytest.mark.parametrize("top_k", [1, 100])
def test_search_request_accepts_top_k_boundaries(top_k):
    request = SearchRequest(
        query="Sample query",
        top_k=top_k,
    )

    assert request.top_k == top_k


def test_search_request_rejects_invalid_mode():
    with pytest.raises(ValidationError):
        SearchRequest(
            query="Sample query",
            mode="unknown",
        )


def test_search_request_preserves_source_filter():
    request = SearchRequest(
        query="Sample query",
        source_ids=["doc-101", "doc-102"],
    )

    assert request.source_ids == ["doc-101", "doc-102"]


def test_search_request_rejects_extra_fields():
    with pytest.raises(ValidationError):
        SearchRequest(
            query="Sample query",
            unknown_field="test",
        )


def test_search_request_json_round_trip():
    original = SearchRequest(
        query="Sample query",
        mode="hybrid",
        top_k=20,
        source_ids=["doc-101"],
    )

    restored = SearchRequest.model_validate_json(
        original.model_dump_json()
    )

    assert restored == original


# RetrievalQuery tests

def test_retrieval_query_valid(valid_query):
    assert valid_query.request.top_k == 5
    assert valid_query.scope.tenant_id == "company-1"
    assert valid_query.generation_ids == ["gen-001"]


def test_retrieval_query_rejects_empty_generations(valid_scope):
    with pytest.raises(ValidationError):
        RetrievalQuery(
            request=SearchRequest(query="Sample query"),
            scope=valid_scope,
            generation_ids=[],
        )


def test_retrieval_query_requires_scope():
    with pytest.raises(ValidationError):
        RetrievalQuery(
            request=SearchRequest(query="Sample query"),
            generation_ids=["gen-001"],
        )


def test_retrieval_query_rejects_invalid_scope(valid_query):
    data = valid_query.model_dump()
    data["scope"]["principals"] = []

    with pytest.raises(ValidationError):
        RetrievalQuery.model_validate(data)


def test_retrieval_query_json_round_trip(valid_query):
    restored = RetrievalQuery.model_validate_json(
        valid_query.model_dump_json()
    )

    assert restored == valid_query


# SearchResult tests

def test_search_result_valid(valid_result):
    assert valid_result.evidence_id == "chunk-101"
    assert valid_result.retrieval_method == "hybrid"
    assert valid_result.score == 0.91


def test_search_result_optional_fields(source_version):
    result = SearchResult(
        evidence_id="chunk-102",
        source=source_version,
        generation_id="gen-001",
        retrieval_method="keyword",
    )

    assert result.text is None
    assert result.location is None
    assert result.score is None


def test_search_result_rejects_invalid_method(source_version):
    with pytest.raises(ValidationError):
        SearchResult(
            evidence_id="chunk-101",
            source=source_version,
            generation_id="gen-001",
            retrieval_method="unknown",
        )


def test_search_result_requires_source():
    with pytest.raises(ValidationError):
        SearchResult(
            evidence_id="chunk-101",
            generation_id="gen-001",
            retrieval_method="hybrid",
        )


def test_search_result_rejects_invalid_location(valid_result):
    data = valid_result.model_dump()
    data["location"] = {"page": 0}

    with pytest.raises(ValidationError):
        SearchResult.model_validate(data)


def test_search_result_json_round_trip(valid_result):
    restored = SearchResult.model_validate_json(
        valid_result.model_dump_json()
    )

    assert restored == valid_result


# RetrievalResponse tests

def test_retrieval_response_defaults():
    response = RetrievalResponse()

    assert response.results == []
    assert response.partial is False
    assert response.warnings == []


def test_retrieval_response_preserves_results(valid_result):
    response = RetrievalResponse(
        results=[valid_result],
    )

    assert len(response.results) == 1
    assert response.results[0].evidence_id == "chunk-101"


def test_retrieval_response_preserves_partial_and_warnings():
    response = RetrievalResponse(
        partial=True,
        warnings=["One retrieval provider failed"],
    )

    assert response.partial is True
    assert len(response.warnings) == 1


def test_retrieval_response_rejects_invalid_result(valid_result):
    data = valid_result.model_dump()
    data["retrieval_method"] = "invalid"

    with pytest.raises(ValidationError):
        RetrievalResponse(results=[data])


def test_retrieval_response_json_round_trip(valid_result):
    original = RetrievalResponse(
        results=[valid_result],
        partial=False,
        warnings=[],
    )

    restored = RetrievalResponse.model_validate_json(
        original.model_dump_json()
    )

    assert restored == original
