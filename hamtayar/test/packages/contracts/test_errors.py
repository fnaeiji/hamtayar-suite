
import pytest
from pydantic import ValidationError

from packages.contracts.errors import (
    ErrorCode,
    ErrorDetail,
)


@pytest.fixture
def valid_error():
    """Create a valid error detail."""

    return ErrorDetail(
        code=ErrorCode.STORAGE_ERROR,
        message="Qdrant connection failed",
        retryable=True,
    )


# ErrorCode tests

@pytest.mark.parametrize(
    ("error_code", "expected_value"),
    [
        (ErrorCode.VALIDATION_ERROR, "validation_error"),
        (ErrorCode.ACCESS_DENIED, "access_denied"),
        (ErrorCode.SOURCE_NOT_FOUND, "source_not_found"),
        (ErrorCode.UNSUPPORTED_FORMAT, "unsupported_format"),
        (ErrorCode.PROVIDER_ERROR, "provider_error"),
        (ErrorCode.STORAGE_ERROR, "storage_error"),
        (ErrorCode.PROCESSING_FAILED, "processing_failed"),
    ],
)
def test_error_code_values(error_code, expected_value):
    assert error_code.value == expected_value


# ErrorDetail tests

def test_error_detail_valid(valid_error):
    assert valid_error.code == ErrorCode.STORAGE_ERROR
    assert valid_error.message == "Qdrant connection failed"
    assert valid_error.retryable is True


def test_error_detail_default_retryable():
    error = ErrorDetail(
        code=ErrorCode.VALIDATION_ERROR,
        message="Invalid input data",
    )

    assert error.retryable is False


@pytest.mark.parametrize("retryable", [True, False])
def test_error_detail_accepts_retryable_values(retryable):
    error = ErrorDetail(
        code=ErrorCode.PROVIDER_ERROR,
        message="Provider failed",
        retryable=retryable,
    )

    assert error.retryable is retryable


def test_error_detail_rejects_empty_message():
    with pytest.raises(ValidationError):
        ErrorDetail(
            code=ErrorCode.STORAGE_ERROR,
            message="",
        )


def test_error_detail_requires_message():
    with pytest.raises(ValidationError):
        ErrorDetail(
            code=ErrorCode.STORAGE_ERROR,
        )


def test_error_detail_requires_code():
    with pytest.raises(ValidationError):
        ErrorDetail(
            message="Something went wrong",
        )


def test_error_detail_rejects_unknown_code():
    with pytest.raises(ValidationError):
        ErrorDetail(
            code="unknown_error",
            message="Unknown error",
        )


def test_error_detail_accepts_string_code():
    error = ErrorDetail(
        code="access_denied",
        message="Access is denied",
    )

    assert error.code == ErrorCode.ACCESS_DENIED


def test_error_detail_rejects_invalid_retryable():
    with pytest.raises(ValidationError):
        ErrorDetail(
            code=ErrorCode.STORAGE_ERROR,
            message="Storage failed",
            retryable="sometimes",
        )


def test_error_detail_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ErrorDetail(
            code=ErrorCode.PROCESSING_FAILED,
            message="Processing failed",
            unknown_field="test",
        )


def test_error_detail_json_round_trip(valid_error):
    json_data = valid_error.model_dump_json()
    restored = ErrorDetail.model_validate_json(json_data)

    assert restored == valid_error


def test_error_detail_serializes_code_as_string(valid_error):
    data = valid_error.model_dump(mode="json")

    assert data["code"] == "storage_error"
    assert data["message"] == "Qdrant connection failed"
    assert data["retryable"] is True
