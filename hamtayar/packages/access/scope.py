
from packages.contracts.access import (
    AccessScope,
    TrustedAccessContext,
)


def build_access_scope(
    context: TrustedAccessContext,
    source_ids: list[str] | None = None,
) -> AccessScope:
    """Build a retrieval scope from trusted identity data."""

    if (
        not context.subject_id.strip()
        or not context.tenant_id.strip()
        or any(not p.strip() for p in context.principals)
    ):
        raise ValueError("Invalid trusted access context")

    if source_ids is not None:
        if any(not source_id.strip() for source_id in source_ids):
            raise ValueError("Invalid source filter")

    return AccessScope(
        tenant_id=context.tenant_id,
        principals=context.principals.copy(),
        source_ids=(
            source_ids.copy()
            if source_ids is not None
            else None
        ),
    )
