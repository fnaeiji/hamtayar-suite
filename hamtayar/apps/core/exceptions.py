"""HTTP-safe errors and consistent public error responses."""

from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from packages.contracts.errors import ErrorCode


def request_id_for(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@dataclass
class ApplicationError(Exception):
    """Trusted domain error whose public message is safe for API consumers.

    Do not expose raw provider exception messages through this class.
    """

    code: ErrorCode
    message: str
    status_code: int = 400
    retryable: bool = False

    def __post_init__(self) -> None:
        if not 400 <= self.status_code <= 599:
            raise ValueError("ApplicationError requires an HTTP error status")


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str | ErrorCode,
    message: str,
    retryable: bool = False,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    rid = request_id_for(request)
    response_headers = dict(headers or {})
    if rid is not None:
        response_headers["X-Request-ID"] = rid
    return JSONResponse(
        status_code=status_code,
        headers=response_headers,
        content={
            "error": {
                "code": code.value if isinstance(code, ErrorCode) else code,
                "message": message,
                "retryable": retryable,
            },
            "request_id": rid,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register uniform JSON handlers without exposing secrets or tracebacks."""

    @app.exception_handler(ApplicationError)
    async def domain_error(request: Request, exc: ApplicationError) -> JSONResponse:
        return error_response(
            request, status_code=exc.status_code, code=exc.code,
            message=exc.message, retryable=exc.retryable,
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # No exc.body, exc.errors() or raw input: these may contain private data.
        return error_response(
            request, status_code=422, code=ErrorCode.VALIDATION_ERROR,
            message="Request validation failed",
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # HTTPException.detail is not guaranteed to be safe for disclosure.
        if exc.status_code == 404:
            public_message = "Not found"
        elif exc.status_code == 405:
            public_message = "Method not allowed"
        elif exc.status_code == 401:
            public_message = "Unauthorized"
        elif exc.status_code == 403:
            public_message = "Forbidden"
        elif exc.status_code == 429:
            public_message = "Too many requests"
        elif 400 <= exc.status_code < 500:
            public_message = "Invalid request"
        else:
            public_message = "Internal server error"

        # HTTP-level errors do not have a matching domain ErrorCode in the
        # current shared contract; http_error is explicitly transport-only.
        safe_headers = {
            key: value for key, value in (exc.headers or {}).items()
            if key.lower() in {"allow", "www-authenticate", "retry-after"}
        }
        return error_response(
            request, status_code=exc.status_code,
            code="http_error", message=public_message,
            headers=safe_headers,
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # The middleware logs this failure internally with the request ID.
        return error_response(
            request, status_code=500,
            code=ErrorCode.PROCESSING_FAILED,
            message="Internal server error",
        )
