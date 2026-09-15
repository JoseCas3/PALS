from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

EmbeddingVector = tuple[float, ...]


@dataclass(frozen=True)
class ProviderEmbedding:
    index: int
    vector: EmbeddingVector


class EmbeddingError(Exception):
    code = "EMBEDDING_FAILED"


class EmbeddingUnavailableError(EmbeddingError):
    code = "EMBEDDING_UNAVAILABLE"


class EmbeddingDimensionMismatchError(EmbeddingError):
    code = "EMBEDDING_DIMENSION_MISMATCH"


class EmbeddingProvider(Protocol):
    provider_name: str
    model_name: str
    dimensions: int

    async def embed(self, texts: Sequence[str]) -> Sequence[ProviderEmbedding]: ...
