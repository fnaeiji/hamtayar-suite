"""Reuse the existing block preparation, adding optional chunk metadata."""

from packages.contracts.chunks import ChunkingRequest
from packages.knowledge.chunking.preparation import (
    prepare_chunking_request as prepare_existing,
)


def prepare_chunking_request(document, *, access, configuration, metadata=None):
    request = prepare_existing(document, access=access, configuration=configuration)
    return ChunkingRequest.model_validate(
        {**request.model_dump(), "metadata": dict(metadata or {})}
    )
