
import pytest

from packages.access.scope import build_access_scope
from packages.contracts.access import TrustedAccessContext


@pytest.fixture
def context():
    return TrustedAccessContext(
        subject_id="user-101",
        tenant_id="company-1",
        principals=["user-101", "team-hamtayar"],
    )


def test_scope_preserves_identity_permissions(context):
    scope = build_access_scope(context)

    assert scope.tenant_id == "company-1"
    assert scope.principals == [
        "user-101",
        "team-hamtayar",
    ]


def test_scope_defaults_to_no_source_filter(context):
    scope = build_access_scope(context)

    assert scope.source_ids is None


def test_scope_preserves_source_filter(context):
    scope = build_access_scope(
        context,
        source_ids=["doc-101", "doc-102"],
    )

    assert scope.source_ids == ["doc-101", "doc-102"]


def test_scope_preserves_empty_source_filter(context):
    scope = build_access_scope(context, source_ids=[])

    assert scope.source_ids == []


def test_scope_rejects_blank_source_id(context):
    with pytest.raises(ValueError):
        build_access_scope(
            context,
            source_ids=["doc-101", " "],
        )


def test_scope_rejects_blank_tenant():
    context = TrustedAccessContext.model_construct(
        subject_id="user-101",
        tenant_id=" ",
        principals=["user-101"],
    )

    with pytest.raises(ValueError):
        build_access_scope(context)


def test_scope_rejects_blank_principal():
    context = TrustedAccessContext.model_construct(
        subject_id="user-101",
        tenant_id="company-1",
        principals=[" "],
    )

    with pytest.raises(ValueError):
        build_access_scope(context)


def test_scope_rejects_empty_principals():
    context = TrustedAccessContext.model_construct(
        subject_id="user-101",
        tenant_id="company-1",
        principals=[],
    )

    with pytest.raises(ValueError):
        build_access_scope(context)


def test_scope_does_not_modify_context(context):
    scope = build_access_scope(context)

    scope.principals.append("new-principal")

    assert "new-principal" not in context.principals


def test_scope_copies_source_ids(context):
    source_ids = ["doc-101"]

    scope = build_access_scope(context, source_ids)
    source_ids.append("doc-102")

    assert scope.source_ids == ["doc-101"]
