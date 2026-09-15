from __future__ import annotations

from app.core.config import Settings
from app.embeddings.contracts import EmbeddingProvider
from app.embeddings.fake import FakeEmbeddingProvider
from app.embeddings.openai import OpenAIEmbeddingProvider


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "fake":
        return FakeEmbeddingProvider(
            model_name=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
        )
    api_key = (
        settings.ai_api_key.get_secret_value().strip()
        if settings.ai_api_key is not None
        else ""
    )
    return OpenAIEmbeddingProvider(
        api_key=api_key,
        model_name=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
        timeout_seconds=settings.ai_timeout_seconds,
    )
