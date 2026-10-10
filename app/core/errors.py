import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import request_id_ctx
from app.schemas.common import ErrorBody, ErrorDetail, ErrorResponse

logger = logging.getLogger("app.errors")


class AppError(Exception):
    """Base class for errors that are safe to return to API clients.

    Messages must never contain secrets, SQL, stack traces or user-supplied input.
    """

    status_code: int = 500
    code: str = "internal_error"
    default_message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    default_message = "The requested resource was not found."


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"
    default_message = "A required service is unavailable. Try again later."


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[ErrorDetail] | None = None,
) -> JSONResponse:
    request_id: str | None = getattr(request.state, "request_id", None)
    body = ErrorResponse(
        error=ErrorBody(code=code, message=message, request_id=request_id, details=details),
    )
    response = JSONResponse(status_code=status_code, content=body.model_dump(exclude_none=True))
    if request_id is not None:
        response.headers["X-Request-ID"] = request_id
    return response


def register_exception_handlers(app: FastAPI) -> None:
    """Maps exceptions to the safe, consistent error envelope."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return _error_response(request, exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        # Report field locations and messages only. Input values are never echoed back.
        details: list[ErrorDetail] = []
        for error in exc.errors():
            loc: tuple[Any, ...] = tuple(error.get("loc", ()))
            field = ".".join(str(part) for part in loc)
            details.append(ErrorDetail(field=field, message=str(error["msg"])))
        return _error_response(
            request, 422, "validation_error", "The request is invalid.", details
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Log the traceback server-side; the client receives only a generic message.
        request_id: str | None = getattr(request.state, "request_id", None)
        logger.error("unhandled exception", exc_info=exc, extra={"request_id": request_id})
        return _error_response(
            request, 500, "internal_error", "An unexpected error occurred."
        )
