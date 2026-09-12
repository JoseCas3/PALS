from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.common import ErrorBody, ErrorResponse


class ApplicationError(Exception):
    def __init__(
        self, status_code: int, code: str, message: str, details: Any = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


async def application_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, ApplicationError):
        raise exc
    body = ErrorResponse(
        error=ErrorBody(code=exc.code, message=exc.message, details=exc.details)
    )
    return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))


async def validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    body = ErrorResponse(
        error=ErrorBody(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            details=jsonable_encoder(exc.errors()),
        )
    )
    return JSONResponse(status_code=422, content=body.model_dump(mode="json"))
