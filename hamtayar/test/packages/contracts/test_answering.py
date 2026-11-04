
import pytest
from pydantic import ValidationError

from packages.contracts.answering import (
    AnswerRequest,
    AnswerResponse,
    Citation,
)
from packages.contracts.common import (
    SourceLocation,
    SourceRef,
    SourceVersion,
)
from packages.contracts.retrieval import SearchResult


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
def valid_evidence(source_version):
    """Create valid evidence returned by retrieval."""

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
        score=0.95,
    )


@pytest.fixture
def valid_citation(source_version):
    """Create a valid citation."""

    return Citation(
        evidence_id="chunk-101",
        source=source_version,
        location=SourceLocation(page=2),
    )


@pytest.fixture
def valid_answer_request(valid_evidence):
    """Create a valid answer generation request."""

    return AnswerRequest(
        question="What is Hamtayar?",
        evidence=[valid_evidence],
    )


@pytest.fixture
def valid_answer_response(valid_citation):
    """Create a valid completed answer."""

    return AnswerResponse(
        answer="Hamtayar is an enterprise RAG system.",
        citations=[valid_citation],
        status="completed",
    )


# AnswerRequest tests

def test_answer_request_valid(valid_answer_request):
    assert valid_answer_request.question == "What is Hamtayar?"
    assert len(valid_answer_request.evidence) == 1


def test_answer_request_defaults_to_empty_evidence():
    request = AnswerRequest(
        question="What is Hamtayar?",
    )

    assert request.evidence == []


def test_answer_request_rejects_empty_question():
    with pytest.raises(ValidationError):
        AnswerRequest(question="")


def test_answer_request_requires_question():
    with pytest.raises(ValidationError):
        AnswerRequest()


def test_answer_request_rejects_invalid_evidence(
    valid_answer_request,
):
    data = valid_answer_request.model_dump()
    data["evidence"][0]["retrieval_method"] = "invalid"

    with pytest.raises(ValidationError):
        AnswerRequest.model_validate(data)


def test_answer_request_rejects_extra_fields():
    with pytest.raises(ValidationError):
        AnswerRequest(
            question="What is Hamtayar?",
            unknown_field="test",
        )


def test_answer_request_json_round_trip(
    valid_answer_request,
):
    json_data = valid_answer_request.model_dump_json()
    restored = AnswerRequest.model_validate_json(json_data)

    assert restored == valid_answer_request


# Citation tests

def test_citation_valid(valid_citation):
    assert valid_citation.evidence_id == "chunk-101"
    assert valid_citation.source.version == "v1"
    assert valid_citation.location.page == 2


def test_citation_optional_location(source_version):
    citation = Citation(
        evidence_id="chunk-101",
        source=source_version,
    )

    assert citation.location is None


def test_citation_rejects_empty_evidence_id(source_version):
    with pytest.raises(ValidationError):
        Citation(
            evidence_id="",
            source=source_version,
        )


def test_citation_requires_source():
    with pytest.raises(ValidationError):
        Citation(evidence_id="chunk-101")


def test_citation_rejects_invalid_location(source_version):
    with pytest.raises(ValidationError):
        Citation(
            evidence_id="chunk-101",
            source=source_version,
            location={"page": 0},
        )


def test_citation_rejects_extra_fields(source_version):
    with pytest.raises(ValidationError):
        Citation(
            evidence_id="chunk-101",
            source=source_version,
            unknown_field="test",
        )


def test_citation_json_round_trip(valid_citation):
    json_data = valid_citation.model_dump_json()
    restored = Citation.model_validate_json(json_data)

    assert restored == valid_citation


# AnswerResponse tests

def test_answer_response_valid(valid_answer_response):
    assert valid_answer_response.status == "completed"
    assert len(valid_answer_response.citations) == 1
    assert valid_answer_response.citations[0].evidence_id == (
        "chunk-101"
    )


def test_answer_response_defaults_to_empty_citations():
    response = AnswerResponse(
        answer="No relevant information was found.",
        status="no_evidence",
    )

    assert response.citations == []


@pytest.mark.parametrize(
    "status",
    ["completed", "no_evidence", "failed"],
)
def test_answer_response_accepts_supported_statuses(status):
    response = AnswerResponse(
        answer="Sample answer",
        status=status,
    )

    assert response.status == status


def test_answer_response_rejects_invalid_status():
    with pytest.raises(ValidationError):
        AnswerResponse(
            answer="Sample answer",
            status="unknown",
        )


def test_answer_response_requires_status():
    with pytest.raises(ValidationError):
        AnswerResponse(answer="Sample answer")


def test_answer_response_requires_answer():
    with pytest.raises(ValidationError):
        AnswerResponse(status="completed")


def test_answer_response_rejects_invalid_citation(
    valid_answer_response,
):
    data = valid_answer_response.model_dump()
    data["citations"][0]["evidence_id"] = ""

    with pytest.raises(ValidationError):
        AnswerResponse.model_validate(data)


def test_answer_response_rejects_extra_fields():
    with pytest.raises(ValidationError):
        AnswerResponse(
            answer="Sample answer",
            status="completed",
            unknown_field="test",
        )


def test_answer_response_json_round_trip(
    valid_answer_response,
):
    json_data = valid_answer_response.model_dump_json()
    restored = AnswerResponse.model_validate_json(json_data)

    assert restored == valid_answer_response


def test_answer_response_allows_empty_answer_for_no_evidence():
    response = AnswerResponse(
        answer="",
        status="no_evidence",
    )

    assert response.answer == ""
