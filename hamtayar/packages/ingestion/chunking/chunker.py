"""Structure-aware chunking with deterministic IDs and exact token limits."""

import hashlib
import json
from collections.abc import Callable

from packages.contracts.chunks import (
    Chunk,
    ChunkingItem,
    ChunkingRequest,
    ChunkingResult,
)
from packages.contracts.common import SourceLocation
from packages.knowledge.configuration import KnowledgeConfiguration

TokenCounter = Callable[[str], int]

_ATOMIC_BLOCKS = {"table", "code", "list", "quote"}
_RESERVED_CHUNK_METADATA_KEYS = frozenset(
    {
        "processing_profile",
        "token_count",
        "block_ids",
        "block_types",
        "code_language",
    }
)


def _token_count(
    text: str,
    count_tokens: TokenCounter,
) -> int:
    count = count_tokens(text)

    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("count_tokens must return a non-negative integer")

    return count


def _compatible_locations(
    first: SourceLocation | None,
    last: SourceLocation | None,
) -> bool:
    if first is None or last is None:
        return first is None and last is None

    return all(
        getattr(first, field) == getattr(last, field)
        for field in (
            "file_path",
            "page",
            "section",
            "sheet",
            "cell_range",
        )
    )


def _merged_location(
    items: list[ChunkingItem],
) -> SourceLocation | None:
    first = items[0].location
    last = items[-1].location

    if first is None:
        return None

    return SourceLocation(
        page=first.page,
        section=first.section,
        sheet=first.sheet,
        cell_range=first.cell_range,
        file_path=first.file_path,
        start_line=first.start_line,
        end_line=(last.end_line if last is not None else first.end_line),
    )


def chunk(
    request: ChunkingRequest,
    *,
    configuration: KnowledgeConfiguration,
    count_tokens: TokenCounter,
) -> ChunkingResult:
    """
    Convert prepared content into structure-aware chunks.

    - Preserve document boundaries and source locations.
    - Keep protected blocks intact.
    - Respect the configured maximum token count.
    - Use zero overlap.
    - Generate deterministic chunk IDs.
    """

    if not isinstance(request, ChunkingRequest):
        raise TypeError("request must be ChunkingRequest")

    if not isinstance(
        configuration,
        KnowledgeConfiguration,
    ):
        raise TypeError("configuration must be KnowledgeConfiguration")

    if not callable(count_tokens):
        raise TypeError("count_tokens must be callable")

    settings = configuration.chunking

    if request.processing_profile != settings.profile:
        raise ValueError("Chunking request profile does not match configuration")

    if settings.strategy != "structure_aware" or settings.overlap_tokens != 0:
        raise ValueError("Unsupported chunking settings")

    conflicting_keys = _RESERVED_CHUNK_METADATA_KEYS.intersection(request.metadata)
    if conflicting_keys:
        raise ValueError(
            "Document metadata contains reserved chunk keys: "
            + ", ".join(sorted(conflicting_keys))
        )

    chunks: list[Chunk] = []
    pending: list[ChunkingItem] = []

    def emit() -> None:
        if not pending:
            return

        text = "\n\n".join(item.text for item in pending)

        token_count = _token_count(
            text,
            count_tokens,
        )

        if token_count > settings.max_tokens:
            raise ValueError("Internal error: chunk exceeds max_tokens")

        ordinal = len(chunks) + 1

        identity = [
            request.source.source.knowledge_space_id,
            request.source.source.source_id,
            request.source.version,
            request.kind,
            request.processing_profile,
            ordinal,
            [item.block_id for item in pending],
            text,
        ]

        digest = hashlib.sha256(
            json.dumps(
                identity,
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()[:24]

        metadata = {
            **request.metadata,
            "processing_profile": request.processing_profile,
            "token_count": str(token_count),
            "block_ids": json.dumps([item.block_id for item in pending]),
            "block_types": ",".join(item.block_type or "unknown" for item in pending),
        }

        if len(pending) == 1 and pending[0].code_language:
            metadata["code_language"] = pending[0].code_language

        chunks.append(
            Chunk(
                chunk_id=f"chunk-{digest}",
                source=request.source.model_copy(deep=True),
                kind=request.kind,
                text=text,
                access=request.access.model_copy(deep=True),
                location=_merged_location(pending),
                symbol_id=(pending[0].symbol_id if len(pending) == 1 else None),
                metadata=metadata,
            )
        )

        pending.clear()

    for item in request.items:
        if not item.text.strip():
            continue

        item_tokens = _token_count(
            item.text,
            count_tokens,
        )

        if item_tokens > settings.max_tokens:
            raise ValueError(
                f"Block "
                f"{item.block_id or item.symbol_id or '<unknown>'} "
                f"has {item_tokens} tokens; "
                f"maximum is {settings.max_tokens}"
            )

        is_atomic = request.kind == "code" or item.block_type in _ATOMIC_BLOCKS

        if item.block_type == "heading" or is_atomic:
            emit()

        if pending:
            combined = "\n\n".join(
                [
                    *(part.text for part in pending),
                    item.text,
                ]
            )

            if (
                not _compatible_locations(
                    pending[0].location,
                    item.location,
                )
                or _token_count(
                    combined,
                    count_tokens,
                )
                > settings.max_tokens
            ):
                emit()

        pending.append(item)

        if is_atomic:
            emit()

    emit()

    return ChunkingResult(chunks=chunks)
