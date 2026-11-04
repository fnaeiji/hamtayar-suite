"""Public Knowledge package service operations."""

from collections.abc import Mapping
from pathlib import Path

from packages.contracts.chunks import ChunkingRequest
from packages.knowledge.chunking import (
    ChunkingTokenCountReport,
    count_chunking_request_items,
    prepare_chunking_request,
)
from packages.knowledge.configuration import (
    DEFAULT_KNOWLEDGE_CONFIG_PATH,
    KnowledgeConfiguration,
    load_knowledge_configuration,
)
from packages.knowledge.tokenizer import HuggingFaceTokenizer, TokenCounter


def load_configuration(
    path: str | Path = DEFAULT_KNOWLEDGE_CONFIG_PATH,
    *,
    overrides: Mapping[str, Mapping[str, object]] | None = None,
) -> KnowledgeConfiguration:
    """Load validated Knowledge configuration from an explicit TOML path."""
    return load_knowledge_configuration(path, overrides=overrides)


def create_tokenizer(configuration: KnowledgeConfiguration) -> HuggingFaceTokenizer:
    """Create a lazy tokenizer instance for reuse across Knowledge operations."""
    if not isinstance(configuration, KnowledgeConfiguration):
        raise TypeError("configuration must be a validated KnowledgeConfiguration")
    return HuggingFaceTokenizer(configuration.embedding)


def count_tokens(
    text: str,
    *,
    configuration: KnowledgeConfiguration,
    tokenizer: TokenCounter | None = None,
) -> int:
    """Count an exact string with the configured tokenizer and special-token policy."""
    if not isinstance(text, str):
        raise TypeError("Tokenizer input must be a string")
    if not isinstance(configuration, KnowledgeConfiguration):
        raise TypeError("configuration must be a validated KnowledgeConfiguration")
    counter = tokenizer if tokenizer is not None else create_tokenizer(configuration)
    return counter.count_tokens(
        text,
        include_special_tokens=configuration.embedding.include_special_tokens,
    )


def count_prepared_request(
    request: ChunkingRequest,
    *,
    configuration: KnowledgeConfiguration,
    tokenizer: TokenCounter | None = None,
) -> ChunkingTokenCountReport:
    """Return ordered token diagnostics for a prepared request's items."""
    if not isinstance(configuration, KnowledgeConfiguration):
        raise TypeError("configuration must be a validated KnowledgeConfiguration")
    counter = tokenizer if tokenizer is not None else create_tokenizer(configuration)
    return count_chunking_request_items(
        request,
        configuration=configuration,
        tokenizer=counter,
    )


__all__ = [
    "ChunkingTokenCountReport",
    "count_prepared_request",
    "count_tokens",
    "create_tokenizer",
    "load_configuration",
    "prepare_chunking_request",
]
