from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import openai

from app.embeddings.contracts import (
    EmbeddingError,
    EmbeddingUnavailableError,
    ProviderEmbedding,
)


class OpenAIEmbeddingProvider:
    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        dimensions: int,
        timeout_seconds: float,
        client: Any | None = None,
    ) -> None:
        self.model_name = model_name
        self.dimensions = dimensions
        self._client = client or (
            openai.AsyncOpenAI(api_key=api_key, timeout=timeout_seconds) if api_key else None
        )

    async def embed(self, texts: Sequence[str]) -> Sequence[ProviderEmbedding]:
        if self._client is None:
            raise EmbeddingUnavailableError("Embedding provider is unavailable")
        try:
            response = await self._client.embeddings.create(
                input=list(texts),
                model=self.model_name,
                dimensions=self.dimensions,
            )
        except (
            openai.APITimeoutError,
            openai.APIConnectionError,
            openai.AuthenticationError,
            openai.PermissionDeniedError,
            openai.RateLimitError,
        ) as exc:
            raise EmbeddingUnavailableError("Embedding provider is unavailable") from exc
        except openai.APIStatusError as exc:
            if exc.status_code >= 500:
                raise EmbeddingUnavailableError("Embedding provider is unavailable") from exc
            raise EmbeddingError("Embedding provider rejected the request") from exc
        except openai.OpenAIError as exc:
            raise EmbeddingError("Embedding provider failed") from exc
        return [
            ProviderEmbedding(index=item.index, vector=tuple(item.embedding))
            for item in response.data
        ]

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.close()
