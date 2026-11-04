"""Map processed document blocks to the shared chunking input contract."""

from packages.contracts.access import AccessMetadata
from packages.contracts.chunks import ChunkingItem, ChunkingRequest
from packages.contracts.document import ParsedDocument
from packages.knowledge.configuration import KnowledgeConfiguration


def prepare_chunking_request(
    document: ParsedDocument,
    *,
    access: AccessMetadata,
    configuration: KnowledgeConfiguration,
) -> ChunkingRequest:
    """Prepare one request item per document block without transforming text.

    ``access`` must be trusted metadata associated with this same source by the
    caller. Pydantic type validation here does not authenticate its origin.
    Structural source locations remain original-source coordinates, while
    protected span coordinates remain relative to each block's effective text.
    """
    if not isinstance(document, ParsedDocument):
        raise TypeError("document must be a ParsedDocument")
    if not isinstance(access, AccessMetadata):
        raise TypeError("access must be trusted AccessMetadata supplied by the caller")
    if not isinstance(configuration, KnowledgeConfiguration):
        raise TypeError("configuration must be a validated KnowledgeConfiguration")
    if document.source.source.source_type != "document":
        raise ValueError("Chunking input preparation requires a document source")

    items = [
        ChunkingItem(
            text=block.effective_text,
            location=block.location.model_copy(deep=True) if block.location else None,
            block_id=block.block_id,
            block_type=block.block_type,
            heading_level=block.heading_level,
            code_language=block.code_language,
            protected_spans=[
                span.model_copy(deep=True) for span in block.protected_spans
            ],
        )
        for block in document.blocks
    ]
    return ChunkingRequest(
        source=document.source.model_copy(deep=True),
        kind="document",
        items=items,
        access=access.model_copy(deep=True),
        processing_profile=configuration.chunking.profile,
    )
