
import pytest
from pydantic import ValidationError

from packages.contracts.access import AccessMetadata
from packages.contracts.common import ContentRef, SourceRef, SourceVersion
from packages.contracts.errors import ErrorCode, ErrorDetail
from packages.contracts.ingestion import (
    IngestionRequest,
    IngestionResponse,
    JobState,
    JobStatus,
)


@pytest.fixture
def valid_request():
    """Create a valid ingestion request."""

    return IngestionRequest(
        source=SourceVersion(
            source=SourceRef(
                source_id="doc-101",
                knowledge_space_id="engineering",
                source_type="document",
            ),
            version="v1",
        ),
        content=ContentRef(
            uri="padeen://documents/doc-101/v1",
        ),
        access=AccessMetadata(
            tenant_id="company-1",
            acl_principals=["team-hamtayar"],
        ),
        idempotency_key="request-101",
    )


def test_ingestion_request_valid(valid_request):
    assert valid_request.source.version == "v1"
    assert valid_request.idempotency_key == "request-101"


def test_ingestion_request_default_profile(valid_request):
    assert valid_request.processing_profile == "default"


def test_ingestion_request_default_metadata(valid_request):
    assert valid_request.metadata == {}


def test_ingestion_request_rejects_empty_idempotency_key(valid_request):
    data = valid_request.model_dump()
    data["idempotency_key"] = ""

    with pytest.raises(ValidationError):
        IngestionRequest.model_validate(data)


def test_ingestion_request_requires_access(valid_request):
    data = valid_request.model_dump()
    del data["access"]

    with pytest.raises(ValidationError):
        IngestionRequest.model_validate(data)


def test_ingestion_request_rejects_invalid_source(valid_request):
    data = valid_request.model_dump()
    data["source"]["version"] = ""

    with pytest.raises(ValidationError):
        IngestionRequest.model_validate(data)


def test_ingestion_response_default_status():
    response = IngestionResponse(job_id="job-101")

    assert response.status == JobState.PENDING


@pytest.mark.parametrize("state", list(JobState))
def test_job_status_accepts_all_states(state):
    job = JobStatus(
        job_id="job-101",
        status=state,
    )

    assert job.status == state


def test_job_status_rejects_invalid_state():
    with pytest.raises(ValidationError):
        JobStatus(
            job_id="job-101",
            status="unknown",
        )


def test_job_status_with_error():
    job = JobStatus(
        job_id="job-101",
        status=JobState.FAILED,
        error=ErrorDetail(
            code=ErrorCode.PROCESSING_FAILED,
            message="Document parsing failed",
            retryable=True,
        ),
    )

    assert job.status == JobState.FAILED
    assert job.error.code == ErrorCode.PROCESSING_FAILED
    assert job.error.retryable is True


def test_ingestion_request_json_round_trip(valid_request):
    json_data = valid_request.model_dump_json()
    restored = IngestionRequest.model_validate_json(json_data)

    assert restored == valid_request


def test_ingestion_response_rejects_extra_fields():
    with pytest.raises(ValidationError):
        IngestionResponse(
            job_id="job-101",
            unknown_field="test",
        )
