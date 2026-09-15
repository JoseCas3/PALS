from __future__ import annotations

import math
from collections.abc import Sequence

from app.embeddings.contracts import (
    EmbeddingDimensionMismatchError,
    EmbeddingError,
    EmbeddingProvider,
    EmbeddingVector,
)


class EmbeddingService:
    def __init__(self, provider: EmbeddingProvider, *, batch_size: int, dimensions: int) -> None:
        if batch_size <= 0:
            raise ValueError("Embedding batch size must be positive")
        if dimensions <= 0:
            raise ValueError("Embedding dimensions must be positive")
        self.provider = provider
        self.batch_size = batch_size
        self.dimensions = dimensions

    async def embed(self, texts: Sequence[str]) -> tuple[EmbeddingVector, ...]:
        vectors: list[EmbeddingVector] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            response = tuple(await self.provider.embed(batch))
            if len(response) != len(batch):
                raise EmbeddingError("Embedding response cardinality mismatch")
            if tuple(item.index for item in response) != tuple(range(len(batch))):
                raise EmbeddingError("Embedding response ordering mismatch")
            for item in response:
                vector = item.vector
                if len(vector) != self.dimensions:
                    raise EmbeddingDimensionMismatchError("Embedding dimension mismatch")
                if any(
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    for value in vector
                ):
                    raise EmbeddingError("Embedding contains a non-finite numeric value")
                vectors.append(tuple(float(value) for value in vector))
        return tuple(vectors)
