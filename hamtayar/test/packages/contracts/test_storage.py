
from uuid import UUID

import pytest
from pydantic import ValidationError

from packages.contracts.storage import (
    FailureCategory,
    PayloadField,
    StoreFailure,
    StoreResult,
)


@pytest.fixture
def valid_failure():
    """Create a valid storage failure."""

    return StoreFailure(
        chunk_id="chunk-101",
        category=FailureCategory.TIMEOUT,
        reason="Write confirmation timed out",
        retryable=True,
    )


@pytest.fixture
def valid_result(valid_failure):
    """Create a valid partial storage result."""

    return StoreResult(
        requested=3,
        stored=2,
        failed=1,
        failures=(valid_failure,),
    )


# PayloadField tests

def test_payload_field_contains_expected_keys():
    expected = (
        "chunk_id",
        "generation_id",
        "model_id",
        "source_id",
        "version",
        "knowledge_space_id",
        "source_type",
        "kind",
        "text",
        "location",
        "tenant_id",
        "acl_principals",
        "symbol_id",
        "metadata",
    )

    assert PayloadField.ALL == expected


def test_payload_field_has_no_duplicates():
    assert len(PayloadField.ALL) == len(
        set(PayloadField.ALL)
    )


# FailureCategory tests

@pytest.mark.parametrize(
    "category",
    list(FailureCategory),
)
def test_failure_category_accepts_supported_values(category):
    assert FailureCategory(category.value) == category


def test_failure_category_rejects_unknown_value():
    with pytest.raises(ValueError):
        FailureCategory("unknown")


# StoreFailure tests

def test_store_failure_valid(valid_failure):
    assert valid_failure.chunk_id == "chunk-101"
    assert valid_failure.category == FailureCategory.TIMEOUT
    assert valid_failure.retryable is True


def test_store_failure_accepts_point_id():
    point_id = UUID("12345678-1234-5678-1234-567812345678")

    failure = StoreFailure(
        point_id=point_id,
        category=FailureCategory.WRITE,
        reason="Write failed",
    )

    assert failure.point_id == point_id
    assert failure.chunk_id is None


def test_store_failure_accepts_both_identifiers():
    failure = StoreFailure(
        point_id=UUID("12345678-1234-5678-1234-567812345678"),
        chunk_id="chunk-101",
        category=FailureCategory.READ_BACK,
        reason="Stored point does not match",
    )

    assert failure.point_id is not None
    assert failure.chunk_id == "chunk-101"


def test_store_failure_requires_identity():
    with pytest.raises(ValidationError):
        StoreFailure(
            category=FailureCategory.WRITE,
            reason="Write failed",
        )


def test_store_failure_rejects_empty_chunk_id():
    with pytest.raises(ValidationError):
        StoreFailure(
            chunk_id="",
            category=FailureCategory.WRITE,
            reason="Write failed",
        )


def test_store_failure_rejects_invalid_point_id():
    with pytest.raises(ValidationError):
        StoreFailure(
            point_id="invalid-uuid",
            category=FailureCategory.WRITE,
            reason="Write failed",
        )


def test_store_failure_requires_category():
    with pytest.raises(ValidationError):
        StoreFailure(
            chunk_id="chunk-101",
            reason="Write failed",
        )


def test_store_failure_rejects_invalid_category():
    with pytest.raises(ValidationError):
        StoreFailure(
            chunk_id="chunk-101",
            category="unknown",
            reason="Write failed",
        )


def test_store_failure_rejects_empty_reason():
    with pytest.raises(ValidationError):
        StoreFailure(
            chunk_id="chunk-101",
            category=FailureCategory.WRITE,
            reason="",
        )


def test_store_failure_requires_reason():
    with pytest.raises(ValidationError):
        StoreFailure(
            chunk_id="chunk-101",
            category=FailureCategory.WRITE,
        )


def test_store_failure_default_retryable():
    failure = StoreFailure(
        chunk_id="chunk-101",
        category=FailureCategory.VALIDATION,
        reason="Invalid chunk",
    )

    assert failure.retryable is False


def test_store_failure_rejects_extra_fields():
    with pytest.raises(ValidationError):
        StoreFailure(
            chunk_id="chunk-101",
            category=FailureCategory.WRITE,
            reason="Write failed",
            unknown_field="test",
        )


def test_store_failure_json_round_trip(valid_failure):
    serialized = valid_failure.model_dump_json()
    restored = StoreFailure.model_validate_json(serialized)

    assert restored == valid_failure


# StoreResult tests

def test_store_result_valid(valid_result):
    assert valid_result.requested == 3
    assert valid_result.stored == 2
    assert valid_result.failed == 1
    assert len(valid_result.failures) == 1


def test_store_result_accepts_full_success():
    result = StoreResult(
        requested=3,
        stored=3,
        failed=0,
    )

    assert result.failed == 0
    assert result.failures == ()


def test_store_result_accepts_zero_points():
    result = StoreResult(
        requested=0,
        stored=0,
        failed=0,
    )

    assert result.failures == ()


def test_store_result_accepts_complete_failure(valid_failure):
    result = StoreResult(
        requested=1,
        stored=0,
        failed=1,
        failures=(valid_failure,),
    )

    assert result.stored == 0
    assert result.failed == 1


def test_store_result_rejects_failure_count_mismatch(
    valid_failure,
):
    with pytest.raises(ValidationError):
        StoreResult(
            requested=3,
            stored=2,
            failed=1,
            failures=(valid_failure, valid_failure),
        )


def test_store_result_rejects_total_count_mismatch(
    valid_failure,
):
    with pytest.raises(ValidationError):
        StoreResult(
            requested=5,
            stored=2,
            failed=1,
            failures=(valid_failure,),
        )


@pytest.mark.parametrize(
    "field",
    ["requested", "stored", "failed"],
)
def test_store_result_rejects_negative_counts(field):
    data = {
        "requested": 0,
        "stored": 0,
        "failed": 0,
    }
    data[field] = -1

    with pytest.raises(ValidationError):
        StoreResult(**data)


def test_store_result_rejects_invalid_nested_failure():
    with pytest.raises(ValidationError):
        StoreResult(
            requested=1,
            stored=0,
            failed=1,
            failures=(
                {
                    "chunk_id": "",
                    "category": "write",
                    "reason": "Write failed",
                },
            ),
        )


def test_store_result_rejects_extra_fields():
    with pytest.raises(ValidationError):
        StoreResult(
            requested=1,
            stored=1,
            failed=0,
            unknown_field="test",
        )


def test_store_result_json_round_trip(valid_result):
    serialized = valid_result.model_dump_json()
    restored = StoreResult.model_validate_json(serialized)

    assert restored == valid_result


def test_store_result_preserves_failure_details(valid_result):
    failure = valid_result.failures[0]

    assert failure.chunk_id == "chunk-101"
    assert failure.category == FailureCategory.TIMEOUT
    assert failure.retryable is True
