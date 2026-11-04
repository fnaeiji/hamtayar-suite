"""T026: access-scope/request restriction truth table and authorization invariants."""

from __future__ import annotations

import pytest

from packages.contracts.access import AccessScope
from packages.retrieval.filters import build_search_filter, resolve_source_ids


@pytest.mark.parametrize(
    ("scope_sources", "request_sources", "expected"),
    [
        (None, None, None),
        (None, [], ()),
        (None, ["a"], ("a",)),
        ([], None, ()),
        ([], [], ()),
        ([], ["a"], ()),
        (["a", "b"], None, ("a", "b")),
        (["a", "b"], [], ()),
        (["a", "b"], ["b", "c"], ("b",)),
    ],
)
def test_source_restriction_truth_table(scope_sources, request_sources, expected):
    scope = AccessScope(
        tenant_id="tenant-A", principals=["reader"], source_ids=scope_sources
    )
    assert resolve_source_ids(scope, request_sources) == expected


def test_filter_always_contains_tenant_and_acl_and_never_expands_scope():
    scope = AccessScope(
        tenant_id="tenant-A", principals=["reader", "team"], source_ids=["a", "b"]
    )
    result = build_search_filter(scope, requested_source_ids=["b", "unauthorized"])

    assert result is not None
    assert result.tenant_id == "tenant-A"
    assert result.principals == ("reader", "team")
    assert result.source_ids == ("b",)


def test_absent_generation_ids_means_no_generation_clause():
    scope = AccessScope(tenant_id="tenant-A", principals=["reader"])
    result = build_search_filter(scope, generation_ids=None)

    assert result is not None
    assert result.generation_ids is None


def test_present_generation_ids_are_passed_as_an_engine_filter():
    scope = AccessScope(tenant_id="tenant-A", principals=["reader"])
    result = build_search_filter(scope, generation_ids=["published"])

    assert result is not None
    assert result.generation_ids == ("published",)
