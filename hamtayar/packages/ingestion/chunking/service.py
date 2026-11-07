"""Artifact adapter around the single structure-aware chunking algorithm."""

import asyncio

from packages.contracts.document_ingestion import ChunkArtifactOutcome
from packages.contracts.errors import ErrorCode, ErrorDetail
from packages.ingestion.chunking.chunker import chunk
from packages.ingestion.chunking.preparation import prepare_chunking_request


class DocumentChunkingService:
    def __init__(self, *, artifacts, count_tokens, configuration):
        self.artifacts, self.count_tokens, self.configuration = (
            artifacts,
            count_tokens,
            configuration,
        )

    async def chunk(self, *, source, normalized, access, profile):
        if profile not in ("default", self.configuration.chunking.profile):
            return ChunkArtifactOutcome(
                error=ErrorDetail(
                    code=ErrorCode.VALIDATION_ERROR, message="Unsupported profile"
                )
            )
        try:
            document = await self.artifacts.get_parsed(ref=normalized, source=source)
            request = prepare_chunking_request(
                document, access=access, configuration=self.configuration
            )
            result = await asyncio.to_thread(
                chunk,
                request,
                configuration=self.configuration,
                count_tokens=self.count_tokens,
            )
            if not result.chunks:
                raise ValueError("No chunks")
            ref = await self.artifacts.put_chunks(source=source, result=result)
            return ChunkArtifactOutcome(ref=ref, count=len(result.chunks))
        except FileNotFoundError:
            return ChunkArtifactOutcome(
                error=ErrorDetail(
                    code=ErrorCode.SOURCE_NOT_FOUND, message="Document unavailable"
                )
            )
        except ValueError:
            return ChunkArtifactOutcome(
                error=ErrorDetail(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Invalid chunking input or token limit",
                )
            )
