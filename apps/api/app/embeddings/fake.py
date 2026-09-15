from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from typing import Literal

from app.embeddings.contracts import (
    EmbeddingUnavailableError,
    ProviderEmbedding,
)

FakeFailure = Literal[
    "unavailable",
    "timeout",
    "wrong_dimensions",
    "cardinality",
    "nonfinite",
    "infinity",
    "ordering",
]


class FakeEmbeddingProvider:
    provider_name = "fake"

    def __init__(
        self,
        *,
        model_name: str = "fake-deterministic-v1",
        dimensions: int = 1536,
        failure: FakeFailure | None = None,
        failure_call: int = 1,
    ) -> None:
        self.model_name = model_name
        self.dimensions = dimensions
        self.failure = failure
        self.failure_call = failure_call
        self.call_count = 0

    async def embed(self, texts: Sequence[str]) -> Sequence[ProviderEmbedding]:
        self.call_count += 1
        failing = self.failure is not None and self.call_count == self.failure_call
        if failing and self.failure in {"unavailable", "timeout"}:
            raise EmbeddingUnavailableError("Embedding provider is unavailable")

        result = [
            ProviderEmbedding(index=index, vector=self._vector(text))
            for index, text in enumerate(texts)
        ]
        if failing and self.failure == "wrong_dimensions" and result:
            result[0] = ProviderEmbedding(result[0].index, result[0].vector[:-1])
        elif failing and self.failure == "cardinality" and result:
            result.pop()
        elif failing and self.failure == "nonfinite" and result:
            vector = list(result[0].vector)
            vector[0] = math.nan
            result[0] = ProviderEmbedding(result[0].index, tuple(vector))
        elif failing and self.failure == "infinity" and result:
            vector = list(result[0].vector)
            vector[0] = math.inf
            result[0] = ProviderEmbedding(result[0].index, tuple(vector))
        elif failing and self.failure == "ordering" and len(result) > 1:
            result.reverse()
        return result

    def _vector(self, text: str) -> tuple[float, ...]:
        seed = hashlib.sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        counter = 0
        while len(values) < self.dimensions:
            block = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
            for offset in range(0, len(block), 4):
                integer = int.from_bytes(block[offset : offset + 4], "big")
                values.append((integer / 2**32) * 2.0 - 1.0)
                if len(values) == self.dimensions:
                    break
            counter += 1
        return tuple(values)
