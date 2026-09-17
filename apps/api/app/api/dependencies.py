from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.adapters.fake import FakeAIProvider
from app.ai.adapters.openai import OpenAIProvider
from app.ai.gateway import AIGateway, AIGatewayResolver
from app.core.config import get_settings
from app.core.errors import ApplicationError
from app.db.session import async_session_factory
from app.embeddings.contracts import EmbeddingProvider
from app.embeddings.factory import create_embedding_provider
from app.embeddings.openai import OpenAIEmbeddingProvider
from app.embeddings.service import EmbeddingService
from app.ingestion.extraction import DocumentExtractor, PypdfDocumentExtractor
from app.retrieval.service import RetrievalService
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
    resolver = ConfiguredAIGatewayResolver()
    try:
        yield await resolver.resolve()
    finally:
        await resolver.aclose()


class ConfiguredAIGatewayResolver:
    def __init__(self) -> None:
        self.gateway: AIGateway | None = None
        self.provider: OpenAIProvider | None = None

    async def resolve(self) -> AIGateway:
        if self.gateway is not None:
            return self.gateway
        settings = get_settings()
        if settings.ai_provider == "fake":
            self.gateway = AIGateway(
                FakeAIProvider(model_name=settings.ai_model),
                timeout_seconds=settings.ai_timeout_seconds,
            )
            return self.gateway
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
        self.provider = OpenAIProvider.create(
            api_key=api_key,
            model=settings.ai_model,
            timeout_seconds=settings.ai_timeout_seconds,
        )
        self.gateway = AIGateway(
            self.provider, timeout_seconds=settings.ai_timeout_seconds
        )
        return self.gateway

    async def aclose(self) -> None:
        if self.provider is not None:
            await self.provider.aclose()


async def get_tutor_ai_gateway() -> AsyncIterator[AIGatewayResolver]:
    resolver = ConfiguredAIGatewayResolver()
    try:
        yield resolver
    finally:
        await resolver.aclose()


def get_document_storage() -> DocumentStorage:
    return LocalDocumentStorage(get_settings().document_storage_root)


def get_document_max_size_bytes() -> int:
    return get_settings().document_max_size_bytes


def get_document_extractor() -> DocumentExtractor:
    return PypdfDocumentExtractor()


async def get_embedding_provider() -> AsyncIterator[EmbeddingProvider]:
    provider = create_embedding_provider(get_settings())
    try:
        yield provider
    finally:
        if isinstance(provider, OpenAIEmbeddingProvider):
            await provider.aclose()


def get_retrieval_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    embedding_provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
) -> RetrievalService:
    settings = get_settings()
    return RetrievalService(
        session,
        EmbeddingService(
            embedding_provider,
            batch_size=settings.embedding_batch_size,
            dimensions=settings.embedding_dimensions,
        ),
        default_limit=settings.retrieval_top_k,
        max_limit=settings.retrieval_max_limit,
        min_relevance=settings.retrieval_min_relevance,
    )


DocumentStorageDependency = Annotated[DocumentStorage, Depends(get_document_storage)]
DocumentMaxSizeDependency = Annotated[int, Depends(get_document_max_size_bytes)]
DocumentExtractorDependency = Annotated[DocumentExtractor, Depends(get_document_extractor)]
EmbeddingProviderDependency = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]
RetrievalServiceDependency = Annotated[RetrievalService, Depends(get_retrieval_service)]
