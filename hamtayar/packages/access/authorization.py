
from packages.contracts.access import TrustedAccessContext
from packages.contracts.common import SourceVersion
from packages.contracts.retrieval import SearchResult

from .provider import AuthorizationProvider


def _source_key(source: SourceVersion) -> tuple[str, str, str, str]:
    return (
        source.source.knowledge_space_id,
        source.source.source_type,
        source.source.source_id,
        source.version,
    )


async def reauthorize_results(
    results: list[SearchResult],
    context: TrustedAccessContext,
    provider: AuthorizationProvider,
) -> list[SearchResult]:
    """Return only evidence whose sources pass reauthorization."""

    if not results:
        return []

    sources = list({
        _source_key(result.source): result.source
        for result in results
    }.values())

    authorized = await provider.authorize_sources(
        context,
        sources,
    )

    requested_keys = {_source_key(source) for source in sources}
    allowed_keys = {_source_key(source) for source in authorized}

    if not allowed_keys.issubset(requested_keys):
        raise ValueError(
            "Authorization provider returned unexpected sources"
        )

    return [
        result
        for result in results
        if _source_key(result.source) in allowed_keys
    ]
