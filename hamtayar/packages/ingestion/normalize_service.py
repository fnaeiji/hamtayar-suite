"""Compose existing DocumentCleaner and PersianNormalizer; no duplication."""

import asyncio
from typing import Protocol

from packages.contracts.artifacts import ArtifactRepository
from packages.contracts.common import ContentRef, SourceVersion
from packages.contracts.document import ParsedDocument
from packages.contracts.document_ingestion import ArtifactOutcome
from packages.contracts.errors import ErrorCode, ErrorDetail


class DocumentProcessor(Protocol):
    def __call__(self, document: ParsedDocument) -> ParsedDocument: ...


class DocumentNormalizationService:
    def __init__(
        self,
        *,
        artifacts: ArtifactRepository,
        profiles: dict[str, tuple[DocumentProcessor, DocumentProcessor]] | None = None,
    ) -> None:
        self.artifacts = artifacts
        # Profiles are explicit, reproducible pipeline settings. `default` is
        # the current TASK-08 Graph processing_profile.
        self.profiles = (
            dict(profiles) if profiles is not None else {"default": self._builtins()}
        )

    @staticmethod
    def _builtins() -> tuple[DocumentProcessor, DocumentProcessor]:
        def clean(document: ParsedDocument) -> ParsedDocument:
            from packages.documents.cleaning.service import DocumentCleaner

            return DocumentCleaner.clean_document(document)

        def normalize(document: ParsedDocument) -> ParsedDocument:
            from packages.documents.normalization.service import PersianNormalizer

            return PersianNormalizer.normalize_document(document)

        return clean, normalize

    async def normalize(
        self,
        *,
        source: SourceVersion,
        parsed: ContentRef,
        profile: str,
    ) -> ArtifactOutcome:
        if profile not in self.profiles:
            return ArtifactOutcome(
                error=ErrorDetail(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Unsupported processing profile",
                )
            )
        try:
            document = await self.artifacts.get_parsed(ref=parsed, source=source)
            clean, normalizer = self.profiles[profile]
            processed = await asyncio.to_thread(
                normalizer, await asyncio.to_thread(clean, document)
            )
            if not isinstance(processed, ParsedDocument) or processed.source != source:
                raise ValueError("Normalization returned invalid source")
            reference = await self.artifacts.put_parsed(
                source=source, document=processed, stage="normalized"
            )
        except ValueError:
            return ArtifactOutcome(
                error=ErrorDetail(
                    code=ErrorCode.VALIDATION_ERROR, message="Invalid parsed document"
                )
            )
        except FileNotFoundError:
            return ArtifactOutcome(
                error=ErrorDetail(
                    code=ErrorCode.SOURCE_NOT_FOUND,
                    message="Parsed document unavailable",
                )
            )
        return ArtifactOutcome(ref=reference)
