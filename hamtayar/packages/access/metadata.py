
from packages.contracts.access import AccessMetadata
from packages.contracts.common import SourceVersion

from .provider import AuthorizationProvider


async def resolve_access_metadata(
    source: SourceVersion,
    provider: AuthorizationProvider,
) -> AccessMetadata:
    """Get trusted access metadata for an indexed source."""

    metadata = await provider.get_source_metadata(source)
    metadata = AccessMetadata.model_validate(metadata)

    if (
        not metadata.tenant_id.strip()
        or any(not p.strip() for p in metadata.acl_principals)
    ):
        raise ValueError("Invalid source access metadata")

    return metadata
