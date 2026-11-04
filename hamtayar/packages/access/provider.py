
from typing import Protocol

from packages.contracts.access import (
    AccessMetadata,
    TrustedAccessContext,
)
from packages.contracts.common import SourceVersion


class AuthorizationProvider(Protocol):
    """Interface implemented by a trusted authorization integration."""

    async def get_trusted_context(
        self,
        access_token: str,
    ) -> TrustedAccessContext:
        """Return verified user identity and principals."""
        ...

    async def get_source_metadata(
        self,
        source: SourceVersion,
    ) -> AccessMetadata:
        """Return authoritative access metadata for a source."""
        ...

    async def authorize_sources(
        self,
        context: TrustedAccessContext,
        sources: list[SourceVersion],
    ) -> list[SourceVersion]:
        """Return only the sources the subject may currently access."""
        ...
