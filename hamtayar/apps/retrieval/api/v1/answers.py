"""Synchronous-from-HTTP (async IO) authenticated Q&A entry point."""
import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from apps.bootstrap import AppContainer, get_container
from apps.core.exceptions import ApplicationError
from apps.retrieval.api.dependencies import AnswerGraphExecutor, get_answer_executor, get_auth_context
from apps.retrieval.api.schemas.answers import (
    AnswerExecutionRequest,
    AnswerRequest,
    AnswerResponse,
    CitationDTO,
    GraphResult,
)
from packages.contracts.access import AccessScope, TrustedAccessContext
from packages.contracts.errors import ErrorCode

router = APIRouter(prefix="/api/v1", tags=["answers"])


def _provider_error(message: str, status_code: int = 502, retryable: bool = True) -> ApplicationError:
    return ApplicationError(
        code=ErrorCode.PROVIDER_ERROR,
        message=message,
        status_code=status_code,
        retryable=retryable,
    )


@router.post(
    "/answers",
    response_model=AnswerResponse,
    status_code=200,
    responses={
        401: {"description": "Authentication required"},
        422: {"description": "Invalid request"},
        502: {"description": "Answer execution failed"},
        503: {"description": "Executor unavailable"},
        504: {"description": "Answer execution timed out"},
    },
)
async def create_answer(
    body: AnswerRequest,
    request: Request,
    auth: Annotated[TrustedAccessContext, Depends(get_auth_context)],
    executor: Annotated[AnswerGraphExecutor, Depends(get_answer_executor)],
    container: Annotated[AppContainer, Depends(get_container)],
) -> AnswerResponse:
    """Require a trusted identity before invoking the Answer Graph.

    The Graph must enforce tenant/ACL prefiltering and reauthorization during
    retrieval; no client-supplied permissions are accepted by this route.
    """
    # Dependency overrides are for tests; reject malformed/absent trusted auth.
    if not isinstance(auth, TrustedAccessContext):
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Bearer"})

    rid = getattr(request.state, "request_id", None)
    if not isinstance(rid, str) or not rid:
        raise _provider_error("Request context is unavailable", status_code=503)

    scope = AccessScope(tenant_id=auth.tenant_id, principals=list(auth.principals))
    task = AnswerExecutionRequest(
        question=body.question,
        auth_context=auth,
        access_scope=scope,
        request_id=rid,
    )

    try:
        result = await asyncio.wait_for(
            executor.execute(task),
            timeout=container.settings.request_timeout_seconds,
        )
    except TimeoutError as exc:
        raise _provider_error("Answer generation timed out", status_code=504) from exc
    except ApplicationError:
        raise
    except Exception as exc:
        raise _provider_error("Answer generation failed") from exc

    if not isinstance(result, GraphResult):
        raise _provider_error("Answer executor returned an invalid result", retryable=False)
    if result.status == "failed":
        raise _provider_error("Answer generation failed")
    if result.status == "completed" and (not result.answer.strip() or not result.citations):
        raise _provider_error("Answer executor returned an invalid result", retryable=False)
    if result.status == "no_evidence" and (result.answer.strip() or result.citations):
        raise _provider_error("Answer executor returned an invalid result", retryable=False)

    return AnswerResponse(
        status=result.status,
        answer=result.answer,
        citations=[CitationDTO.from_contract(citation) for citation in result.citations],
        request_id=rid,
    )
