from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.core.config import get_settings
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Accept", "Content-Type"],
)
app.include_router(health_router)

