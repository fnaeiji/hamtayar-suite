"""Authorized search boundary: turn an `AccessScope` plus request restrictions into a search filter.

Approved decision D: `AccessScope.source_ids` is the security boundary, a request-supplied source list
is an optional narrowing, and the effective restriction is:

| scope | request | effective |
|---|---|---|
| present | present | intersection (empty ⇒ deny) |
| present | absent  | scope |
| absent  | present | request (tenant + ACL still enforced) |
| absent  | absent  | no source clause |

Tenant and principals are always present. A **deny** is not an error: `build_search_filter` returns
`None`, and the caller must return an empty result without executing any query.
"""

from __future__ import annotations

from packages.contracts.access import AccessScope
from packages.storage.service import SearchFilter

from .exceptions import SearchScopeRequiredError

__all__ = ["build_search_filter", "resolve_source_ids"]


def resolve_source_ids(
    scope: AccessScope,
    requested_source_ids: list[str] | None,
) -> tuple[str, ...] | None:
    """Effective source restriction: `None` means "no source clause", `()` means "deny"."""
    scope_sources = scope.source_ids
    requested = requested_source_ids

    if scope_sources is not None:
        if not scope_sources:
            return ()  # an empty authorized list authorizes nothing
        if requested is None:
            return tuple(scope_sources)
        allowed = set(scope_sources)
        intersection = tuple(source for source in requested if source in allowed)
        return intersection  # may be empty → deny

    if requested is not None:
        return tuple(requested)  # may be empty → deny

    return None


def build_search_filter(
    scope: AccessScope | None,
    *,
    requested_source_ids: list[str] | None = None,
    generation_ids: list[str] | None = None,
) -> SearchFilter | None:
    """Build the engine-facing filter, or `None` when the effective restriction denies everything.

    Raises:
        SearchScopeRequiredError: the scope is missing or lacks a tenant/principals (fail closed).
    """
    if scope is None:
        raise SearchScopeRequiredError("an access scope is required to search")
    if not scope.tenant_id or not scope.principals:
        raise SearchScopeRequiredError(
            "access scope must carry a tenant and at least one principal"
        )

    source_ids = resolve_source_ids(scope, requested_source_ids)
    if source_ids is not None and not source_ids:
        return None  # deny: never widen, never query

    return SearchFilter(
        tenant_id=scope.tenant_id,
        principals=tuple(scope.principals),
        source_ids=source_ids,
        generation_ids=tuple(generation_ids) if generation_ids is not None else None,
    )
