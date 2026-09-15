from __future__ import annotations

import math
import unicodedata
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.embeddings.contracts import (
    EmbeddingDimensionMismatchError,
    EmbeddingError,
    EmbeddingUnavailableError,
)
from app.embeddings.service import EmbeddingService
from app.repositories.document_chunks import DocumentChunkRepository
from app.repositories.subjects import SubjectRepository
from app.retrieval.contracts import RetrievalResult, RetrievedChunk

_CANDIDATE_MULTIPLIER = 4


class RetrievalService:
    def __init__(
        self,
        session: AsyncSession,
        embeddings: EmbeddingService,
        *,
        default_limit: int,
        max_limit: int,
        min_relevance: float,
    ) -> None:
        if default_limit <= 0 or max_limit <= 0 or default_limit > max_limit:
            raise ValueError("Retrieval limits are invalid")
        if not -1.0 <= min_relevance <= 1.0:
            raise ValueError("Retrieval minimum relevance must be between -1 and 1")
        self.subjects = SubjectRepository(session)
        self.chunks = DocumentChunkRepository(session)
        self.embeddings = embeddings
        self.default_limit = default_limit
        self.max_limit = max_limit
        self.min_relevance = min_relevance

    async def retrieve(
        self, subject_id: uuid.UUID, query: str, limit: int | None = None
    ) -> RetrievalResult:
        prepared_query = self._prepare_query(query)
        final_limit = self.default_limit if limit is None else limit
        if final_limit <= 0 or final_limit > self.max_limit:
            raise ApplicationError(
                422,
                "VALIDATION_ERROR",
                f"Retrieval limit must be between 1 and {self.max_limit}",
            )
        if await self.subjects.get(subject_id) is None:
            raise ApplicationError(404, "RESOURCE_NOT_FOUND", "Subject not found")

        try:
            (query_vector,) = await self.embeddings.embed([prepared_query])
        except EmbeddingUnavailableError as exc:
            raise EmbeddingUnavailableError("Embedding provider is unavailable") from exc
        except EmbeddingDimensionMismatchError as exc:
            raise EmbeddingDimensionMismatchError("Embedding dimension mismatch") from exc
        except EmbeddingError as exc:
            raise EmbeddingError("Embedding generation failed") from exc
        except Exception as exc:
            raise EmbeddingError("Embedding generation failed") from exc
        candidate_limit = min(self.max_limit, final_limit * _CANDIDATE_MULTIPLIER)
        candidates = await self.chunks.retrieve_candidates(
            subject_id=subject_id,
            query_vector=query_vector,
            embedding_provider=self.embeddings.provider.provider_name,
            embedding_model=self.embeddings.provider.model_name,
            embedding_dimensions=self.embeddings.dimensions,
            limit=candidate_limit,
        )

        returned: list[RetrievedChunk] = []
        seen_text: set[str] = set()
        for candidate in candidates:
            relevance = 1.0 - candidate.cosine_distance
            if not math.isfinite(relevance) or relevance < self.min_relevance:
                continue
            identity = self._deduplication_identity(candidate.text)
            if identity in seen_text:
                continue
            seen_text.add(identity)
            returned.append(
                RetrievedChunk(
                    chunk_id=candidate.chunk_id,
                    document_id=candidate.document_id,
                    document_filename=candidate.document_filename,
                    page_start=candidate.page_start,
                    page_end=candidate.page_end,
                    text=candidate.text,
                    relevance_score=relevance,
                )
            )
            if len(returned) == final_limit:
                break
        return RetrievalResult(chunks=returned, sufficient=bool(returned))

    @staticmethod
    def _prepare_query(query: str) -> str:
        prepared = " ".join(unicodedata.normalize("NFC", query).split())
        if not prepared:
            raise ApplicationError(422, "VALIDATION_ERROR", "Retrieval query must not be empty")
        return prepared

    @staticmethod
    def _deduplication_identity(text: str) -> str:
        return " ".join(unicodedata.normalize("NFC", text).split()).casefold()
