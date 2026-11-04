"""Document Ingestion execution port and DI resolver, without Queue or Padeen."""
from typing import Annotated

from fastapi import Depends

from apps.bootstrap import AppContainer, get_container
from apps.core.exceptions import ApplicationError
from apps.document_ingestion.api.schemas.jobs import (
    DocumentExecutionRequest,
    DocumentExecutionResult,
)
from apps.orchestration.execution import (
    DocumentIngestionExecutor,
    ExecutorUnavailable,
    resolve_document_ingestion_executor,
)
from packages.contracts.errors import ErrorCode


def get_document_ingestion_executor(
    container: Annotated[AppContainer, Depends(get_container)],
) -> DocumentIngestionExecutor:
    try:
        return resolve_document_ingestion_executor(container)
    except ExecutorUnavailable as exc:
        raise ApplicationError(
            code=ErrorCode.PROVIDER_ERROR,
            message="Document ingestion executor is not configured",
            status_code=503,
            retryable=True,
        ) from exc
