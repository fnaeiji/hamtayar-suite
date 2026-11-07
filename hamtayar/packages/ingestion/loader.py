"""Load a source through the injected artifact repository; no LangGraph logic."""

from packages.contracts.access import AccessMetadata
from packages.contracts.artifacts import ArtifactRepository
from packages.contracts.document import DocumentInput
from packages.contracts.document_ingestion import ArtifactOutcome
from packages.contracts.errors import ErrorCode, ErrorDetail


class DocumentLoader:
    def __init__(self, *, artifacts: ArtifactRepository) -> None:
        self.artifacts = artifacts

    async def load_document(
        self,
        *,
        document: DocumentInput,
        access: AccessMetadata,
    ) -> ArtifactOutcome:
        try:
            ref = await self.artifacts.stage_raw(
                source=document.source,
                original=document.content,
                access=access,
            )
        except PermissionError:
            return ArtifactOutcome(
                error=ErrorDetail(
                    code=ErrorCode.ACCESS_DENIED, message="Source not permitted"
                )
            )
        except FileNotFoundError:
            return ArtifactOutcome(
                error=ErrorDetail(
                    code=ErrorCode.SOURCE_NOT_FOUND, message="Source not found"
                )
            )
        except ValueError:
            return ArtifactOutcome(
                error=ErrorDetail(
                    code=ErrorCode.VALIDATION_ERROR, message="Invalid document input"
                )
            )
        return ArtifactOutcome(ref=ref)
