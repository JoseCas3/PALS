from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.adapters.openai import OpenAIProvider
from app.ai.gateway import AIGateway
from app.core.config import get_settings
from app.core.errors import ApplicationError
from app.db.session import async_session_factory
from app.ingestion.extraction import DocumentExtractor, PypdfDocumentExtractor
from app.storage.documents import DocumentStorage, LocalDocumentStorage


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


Session = Annotated[AsyncSession, Depends(get_session)]


async def get_ai_gateway() -> AsyncIterator[AIGateway]:
    settings = get_settings()
    api_key = (
        settings.ai_api_key.get_secret_value().strip()
        if settings.ai_api_key is not None
        else ""
    )
    if settings.ai_provider != "openai" or not api_key:
        raise ApplicationError(
            503,
            "AI_PROVIDER_UNAVAILABLE",
            "AI service is temporarily unavailable",
        )
    provider = OpenAIProvider.create(
        api_key=api_key,
        model=settings.ai_model,
        timeout_seconds=settings.ai_timeout_seconds,
    )
    try:
        yield AIGateway(provider, timeout_seconds=settings.ai_timeout_seconds)
    finally:
        await provider.aclose()


def get_document_storage() -> DocumentStorage:
    return LocalDocumentStorage(get_settings().document_storage_root)


def get_document_max_size_bytes() -> int:
    return get_settings().document_max_size_bytes


def get_document_extractor() -> DocumentExtractor:
    return PypdfDocumentExtractor()


DocumentStorageDependency = Annotated[DocumentStorage, Depends(get_document_storage)]
DocumentMaxSizeDependency = Annotated[int, Depends(get_document_max_size_bytes)]
DocumentExtractorDependency = Annotated[DocumentExtractor, Depends(get_document_extractor)]
