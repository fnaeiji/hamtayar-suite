
import pytest
from pydantic import ValidationError

from packages.contracts.access import (
    AccessMetadata,
    AccessScope,
    TrustedAccessContext,
)


@pytest.fixture
def valid_access_metadata():
    """Create valid access metadata for indexed content."""
    return AccessMetadata(
        tenant_id="company-1",
        acl_principals=["team-hamtayar", "user-101"],
    )


@pytest.fixture
def valid_trusted_context():
    """Create a valid trusted access context."""
    return TrustedAccessContext(
        subject_id="user-101",
        tenant_id="company-1",
        principals=["user-101", "team-hamtayar"],
    )


@pytest.fixture
def valid_access_scope():
    """Create a valid authorized retrieval scope."""
    return AccessScope(
        tenant_id="company-1",
        principals=["user-101", "team-hamtayar"],
        source_ids=["doc-101", "doc-102"],
    )


# AccessMetadata tests

def test_access_metadata_valid(valid_access_metadata):
    assert valid_access_metadata.tenant_id == "company-1"
    assert valid_access_metadata.acl_principals == [
        "team-hamtayar",
        "user-101",
    ]


def test_access_metadata_rejects_empty_tenant():
    with pytest.raises(ValidationError):
        AccessMetadata(
            tenant_id="",
            acl_principals=["team-hamtayar"],
        )


def test_access_metadata_rejects_empty_principals():
    with pytest.raises(ValidationError):
        AccessMetadata(
            tenant_id="company-1",
            acl_principals=[],
        )


def test_access_metadata_requires_principals():
    with pytest.raises(ValidationError):
        AccessMetadata(tenant_id="company-1")


def test_access_metadata_rejects_extra_fields():
    with pytest.raises(ValidationError):
        AccessMetadata(
            tenant_id="company-1",
            acl_principals=["team-hamtayar"],
            unknown_field="test",
        )


def test_access_metadata_json_round_trip(valid_access_metadata):
    json_data = valid_access_metadata.model_dump_json()
    restored = AccessMetadata.model_validate_json(json_data)

    assert restored == valid_access_metadata


# TrustedAccessContext tests

def test_trusted_context_valid(valid_trusted_context):
    assert valid_trusted_context.subject_id == "user-101"
    assert valid_trusted_context.tenant_id == "company-1"
    assert "team-hamtayar" in valid_trusted_context.principals


def test_trusted_context_rejects_empty_subject():
    with pytest.raises(ValidationError):
        TrustedAccessContext(
            subject_id="",
            tenant_id="company-1",
            principals=["team-hamtayar"],
        )


def test_trusted_context_rejects_empty_tenant():
    with pytest.raises(ValidationError):
        TrustedAccessContext(
            subject_id="user-101",
            tenant_id="",
            principals=["team-hamtayar"],
        )


def test_trusted_context_rejects_empty_principals():
    with pytest.raises(ValidationError):
        TrustedAccessContext(
            subject_id="user-101",
            tenant_id="company-1",
            principals=[],
        )


def test_trusted_context_requires_subject():
    with pytest.raises(ValidationError):
        TrustedAccessContext(
            tenant_id="company-1",
            principals=["team-hamtayar"],
        )


def test_trusted_context_rejects_extra_fields():
    with pytest.raises(ValidationError):
        TrustedAccessContext(
            subject_id="user-101",
            tenant_id="company-1",
            principals=["team-hamtayar"],
            unknown_field="test",
        )


def test_trusted_context_json_round_trip(valid_trusted_context):
    json_data = valid_trusted_context.model_dump_json()
    restored = TrustedAccessContext.model_validate_json(json_data)

    assert restored == valid_trusted_context


# AccessScope tests

def test_access_scope_valid(valid_access_scope):
    assert valid_access_scope.tenant_id == "company-1"
    assert valid_access_scope.principals == [
        "user-101",
        "team-hamtayar",
    ]
    assert len(valid_access_scope.source_ids) == 2


def test_access_scope_defaults_to_no_source_filter():
    scope = AccessScope(
        tenant_id="company-1",
        principals=["user-101"],
    )

    assert scope.source_ids is None


def test_access_scope_preserves_source_ids(valid_access_scope):
    assert valid_access_scope.source_ids == [
        "doc-101",
        "doc-102",
    ]


def test_access_scope_rejects_empty_tenant():
    with pytest.raises(ValidationError):
        AccessScope(
            tenant_id="",
            principals=["user-101"],
        )


def test_access_scope_rejects_empty_principals():
    with pytest.raises(ValidationError):
        AccessScope(
            tenant_id="company-1",
            principals=[],
        )


def test_access_scope_requires_principals():
    with pytest.raises(ValidationError):
        AccessScope(tenant_id="company-1")


def test_access_scope_rejects_invalid_source_ids():
    with pytest.raises(ValidationError):
        AccessScope(
            tenant_id="company-1",
            principals=["user-101"],
            source_ids="doc-101",
        )


def test_access_scope_rejects_extra_fields():
    with pytest.raises(ValidationError):
        AccessScope(
            tenant_id="company-1",
            principals=["user-101"],
            unknown_field="test",
        )


def test_access_scope_json_round_trip(valid_access_scope):
    json_data = valid_access_scope.model_dump_json()
    restored = AccessScope.model_validate_json(json_data)

    assert restored == valid_access_scope
