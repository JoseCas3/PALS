from typing import Any

from pydantic import BaseModel


def reject_nul(value: str | None) -> str | None:
    if value is not None and "\x00" in value:
        raise ValueError("Text must not contain NUL characters")
    return value


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any = None


class ErrorResponse(BaseModel):
    error: ErrorBody
