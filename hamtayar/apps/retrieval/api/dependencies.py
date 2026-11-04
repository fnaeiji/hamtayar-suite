"""Fail-closed auth and injectable Answer Graph execution port.

Production auth will be supplied by a future Padin adapter. Tests replace
`get_auth_context` through FastAPI's `app.dependency_overrides` only.
"""
from typing import Annotated, Protocol

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from apps.bootstrap import AppContainer, get_container
from apps.core.exceptions import ApplicationError
from apps.retrieval.api.schemas.answers import AnswerExecutionRequest, GraphResult
from packages.contracts.access import TrustedAccessContext
from packages.contracts.errors import ErrorCode


class AnswerGraphExecutor(Protocol):
    """Runs the authorized Answer Graph and awaits its final result."""

    async def execute(self, request: AnswerExecutionRequest) -> GraphResult: ...


bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> TrustedAccessContext:
    """No auth implementation yet: NEVER trust headers or user-supplied claims.

    When Padin integration is ready, replace this dependency with a trusted
    token verifier that returns `TrustedAccessContext`. For unit tests, use
    `app.dependency_overrides[get_auth_context]` with a controlled fake.
    """
    # The token, even if supplied, is never trusted without a real verifier.
    _ = credentials
    raise HTTPException(
        status_code=401,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_answer_executor(
    container: Annotated[AppContainer, Depends(get_container)],
) -> AnswerGraphExecutor:
    executor = container.services.get("answer_executor")
    if executor is None or not callable(getattr(executor, "execute", None)):
        raise ApplicationError(
            code=ErrorCode.PROVIDER_ERROR,
            message="Answer executor is not configured",
            status_code=503,
            retryable=True,
        )
    return executor
