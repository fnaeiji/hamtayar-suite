"""S-02 storage error types: ownership, attached detail and error codes.

Structural shape tests for `StoreResult` / `StoreFailure` / `PayloadField` live in
`test/contracts/test_storage.py` (the contract layer owns them); this file covers what the storage
layer adds on top: the five operational error types.
"""

import pytest
from uuid import UUID

from packages.contracts.errors import ErrorCode
from packages.contracts.storage import StoreFailure, StoreResult
from packages.storage.exceptions import (
    ChunkValidationError,
    CollectionMismatchError,
    ReadBackMismatchError,
    StoreTimeoutError,
    StoreWriteError,
)

PUBLIC_ERRORS = (
    ChunkValidationError,
    CollectionMismatchError,
    StoreWriteError,
    StoreTimeoutError,
    ReadBackMismatchError,
)


def a_failure(**overrides) -> StoreFailure:
    data = {"chunk_id": "c1", "category": "write", "reason": "boom"}
    data.update(overrides)
    return StoreFailure(**data)


@pytest.mark.parametrize("error_type", PUBLIC_ERRORS)
def test_every_storage_error_carries_result_and_error_code(error_type):
    result = StoreResult(requested=1, stored=0, failed=1, failures=(a_failure(),))
    error = error_type("something failed", result=result)

    assert isinstance(error, Exception)
    assert str(error) == "something failed"
    assert error.result is result
    assert isinstance(error.error_code, ErrorCode)


def test_validation_error_uses_the_validation_code_and_others_use_storage_code():
    result = StoreResult(requested=1, stored=0, failed=1, failures=(a_failure(),))

    assert ChunkValidationError("x", result=result).error_code is ErrorCode.VALIDATION_ERROR
    for error_type in (
        CollectionMismatchError,
        StoreWriteError,
        StoreTimeoutError,
        ReadBackMismatchError,
    ):
        assert error_type("x", result=result).error_code is ErrorCode.STORAGE_ERROR


def test_operational_errors_are_not_defined_in_contracts():
    import packages.contracts.storage as contracts

    for name in (
        "ChunkValidationError",
        "CollectionMismatchError",
        "StoreWriteError",
        "StoreTimeoutError",
        "ReadBackMismatchError",
        "StorageError",
    ):
        assert not hasattr(contracts, name), f"{name} must live in packages/storage, not contracts"


def test_service_reexports_the_public_error_types():
    from packages.storage import service

    for error_type in PUBLIC_ERRORS:
        assert getattr(service, error_type.__name__) is error_type


# ---- operation-level retryability (Task 2)


def _result(*failures) -> StoreResult:
    return StoreResult(requested=len(failures), stored=0, failed=len(failures), failures=failures)


def test_validation_and_mismatch_are_never_retryable():
    validation = _result(
        StoreFailure(chunk_id="c1", category="validation", reason="dup", retryable=False)
    )
    mismatch = _result(
        StoreFailure(chunk_id="c1", category="mismatch", reason="size", retryable=False)
    )

    assert ChunkValidationError("x", result=validation).retryable is False
    assert CollectionMismatchError("x", result=mismatch).retryable is False


def test_a_transient_write_is_retryable_and_a_permanent_write_is_not():
    transient = _result(StoreFailure(chunk_id="c1", category="write", reason="503", retryable=True))
    permanent = _result(StoreFailure(chunk_id="c1", category="write", reason="400", retryable=False))

    assert StoreWriteError("x", result=transient).retryable is True
    assert StoreWriteError("x", result=permanent).retryable is False


def test_unattempted_points_do_not_suppress_retryability():
    """Not `all(...)` over every failure: unattempted points are normal failures."""
    mixed = _result(
        StoreFailure(chunk_id="c1", category="write", reason="503", retryable=True),
        StoreFailure(chunk_id="c2", category="unattempted", reason="skipped", retryable=False),
    )

    assert StoreWriteError("x", result=mixed).retryable is True


def test_one_permanent_failure_in_a_batch_makes_the_operation_non_retryable():
    mixed = _result(
        StoreFailure(chunk_id="c1", category="write", reason="503", retryable=True),
        StoreFailure(chunk_id="c2", category="write", reason="400", retryable=False),
    )

    assert StoreWriteError("x", result=mixed).retryable is False


def test_read_back_mismatch_is_not_retryable_but_a_read_timeout_is():
    mismatch = _result(
        StoreFailure(point_id=UUID("12345678-1234-5678-1234-567812345678"),
                     category="read_back", reason="missing", retryable=False)
    )
    timeout = _result(
        StoreFailure(point_id=UUID("12345678-1234-5678-1234-567812345678"),
                     category="timeout", reason="unavailable", retryable=True)
    )

    assert ReadBackMismatchError("x", result=mismatch).retryable is False
    assert StoreTimeoutError("x", result=timeout).retryable is True


def test_failures_from_the_target_are_the_only_retryability_signal():
    """A result with no target-attributable failure is never retryable."""
    only_unattempted = _result(
        StoreFailure(chunk_id="c1", category="unattempted", reason="skipped", retryable=False)
    )

    assert StoreTimeoutError("x", result=only_unattempted).retryable is False
