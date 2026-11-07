"""Contract for externally verified ingest/publish permissions.

No default-allow implementation: integration with Padeen must be supplied by
the owning Access team; AccessMetadata by itself is not authentication.
"""

from typing import Literal, Protocol

from packages.contracts.access import AccessMetadata, TrustedAccessContext
from packages.contracts.common import SourceVersion


class IngestionAuthorizationPort(Protocol):
    async def authorize_action(
        self, *, context: TrustedAccessContext, source: SourceVersion,
        action: Literal['ingest', 'publish'],
    ) -> AccessMetadata: ...
