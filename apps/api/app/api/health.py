from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import engine

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    status: Literal["ready"]
    database: Literal["connected"]


class NotReadyResponse(BaseModel):
    status: Literal["not_ready"]
    database: Literal["unavailable"]


async def database_is_ready() -> bool:
    try:
        async with asyncio.timeout(get_settings().database_connect_timeout_seconds):
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
    except (OSError, SQLAlchemyError, TimeoutError):
        logger.warning("PostgreSQL readiness check failed", exc_info=True)
        return False
    return True


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": NotReadyResponse}},
)
async def ready(
    is_database_ready: Annotated[bool, Depends(database_is_ready)],
) -> ReadinessResponse | JSONResponse:
    if not is_database_ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=NotReadyResponse(
                status="not_ready", database="unavailable"
            ).model_dump(),
        )
    return ReadinessResponse(status="ready", database="connected")

