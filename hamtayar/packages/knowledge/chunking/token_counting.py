"""Ordered per-item diagnostics for prepared chunking requests."""

from dataclasses import dataclass

from packages.contracts.chunks import ChunkingRequest
from packages.knowledge.configuration import KnowledgeConfiguration
from packages.knowledge.tokenizer import (
    HuggingFaceTokenizer,
    TokenCounter,
    TokenizerConfigurationError,
    TokenizerIdentity,
)


@dataclass(frozen=True)
class ItemTokenCount:
    """Token diagnostic for one item; this item is not a final chunk."""

    order: int
    block_id: str | None
    block_type: str | None
    token_count: int
    exceeds_chunk_budget: bool


@dataclass(frozen=True)
class ChunkingTokenCountReport:
    """Per-item counts with their tokenizer and configured chunk budget."""

    tokenizer: TokenizerIdentity
    include_special_tokens: bool
    chunk_budget: int
    items: tuple[ItemTokenCount, ...]


def count_chunking_request_items(
    request: ChunkingRequest,
    *,
    configuration: KnowledgeConfiguration,
    tokenizer: TokenCounter | None = None,
) -> ChunkingTokenCountReport:
    """Count prepared item strings in order without changing the request.

    Counts are diagnostics for source blocks. They are not additive estimates
    for concatenated text and do not split or modify oversized items.
    """
    if not isinstance(request, ChunkingRequest):
        raise TypeError("request must be a ChunkingRequest")
    if not isinstance(configuration, KnowledgeConfiguration):
        raise TypeError("configuration must be a validated KnowledgeConfiguration")

    counter = (
        tokenizer
        if tokenizer is not None
        else HuggingFaceTokenizer(configuration.embedding)
    )
    include_special_tokens = configuration.embedding.include_special_tokens
    counts = tuple(
        ItemTokenCount(
            order=order,
            block_id=item.block_id,
            block_type=item.block_type,
            token_count=counter.count_tokens(
                item.text,
                include_special_tokens=include_special_tokens,
            ),
            exceeds_chunk_budget=False,
        )
        for order, item in enumerate(request.items, start=1)
    )
    identity = counter.identity
    capacity = identity.model_input_capacity
    if capacity is not None and configuration.chunking.max_tokens > capacity:
        raise TokenizerConfigurationError(
            f"Configured max_tokens ({configuration.chunking.max_tokens}) exceeds "
            f"the tokenizer-reported model input capacity ({capacity})."
        )
    return ChunkingTokenCountReport(
        tokenizer=identity,
        include_special_tokens=include_special_tokens,
        chunk_budget=configuration.chunking.max_tokens,
        items=tuple(
            ItemTokenCount(
                order=count.order,
                block_id=count.block_id,
                block_type=count.block_type,
                token_count=count.token_count,
                exceeds_chunk_budget=count.token_count
                > configuration.chunking.max_tokens,
            )
            for count in counts
        ),
    )
