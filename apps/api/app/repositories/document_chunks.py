from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.embeddings.contracts import EmbeddingVector
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.subject import Subject

if TYPE_CHECKING:
    from app.ingestion.chunking import ProcessedChunk


@dataclass(frozen=True)
class RetrievalCandidate:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_filename: str
    page_start: int
    page_end: int
    text: str
    cosine_distance: float


@dataclass(frozen=True)
class DocumentEvidence:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_filename: str
    page_start: int
    page_end: int
    text: str


class DocumentChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def replace(
        self,
        document_id: uuid.UUID,
        chunks: Sequence[ProcessedChunk],
        vectors: Sequence[EmbeddingVector],
    ) -> list[DocumentChunk]:
        await self.delete_for_document(document_id)
        rows = [
            DocumentChunk(
                document_id=document_id,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                token_count=chunk.token_count,
                embedding=list(vector),
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        self.session.add_all(rows)
        await self.session.flush()
        return rows

    async def delete_for_document(self, document_id: uuid.UUID) -> None:
        await self.session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )

    async def list_for_document(self, document_id: uuid.UUID) -> list[DocumentChunk]:
        result = await self.session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return list(result)

    async def count_for_document(self, document_id: uuid.UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count()).select_from(DocumentChunk).where(
                    DocumentChunk.document_id == document_id
                )
            )
            or 0
        )

    async def get_ready_evidence(
        self, document_id: uuid.UUID, chunk_id: uuid.UUID
    ) -> DocumentEvidence | None:
        row = (
            await self.session.execute(
                select(
                    DocumentChunk.id,
                    DocumentChunk.document_id,
                    Document.original_filename,
                    DocumentChunk.page_start,
                    DocumentChunk.page_end,
                    DocumentChunk.text,
                )
                .join(Document, Document.id == DocumentChunk.document_id)
                .join(Subject, Subject.id == Document.subject_id)
                .where(
                    Document.id == document_id,
                    Document.status == "READY",
                    DocumentChunk.id == chunk_id,
                    DocumentChunk.document_id == document_id,
                )
            )
        ).one_or_none()
        if row is None:
            return None
        return DocumentEvidence(
            chunk_id=row.id,
            document_id=row.document_id,
            document_filename=row.original_filename,
            page_start=row.page_start,
            page_end=row.page_end,
            text=row.text,
        )

    async def retrieve_candidates(
        self,
        *,
        subject_id: uuid.UUID,
        query_vector: EmbeddingVector,
        embedding_provider: str,
        embedding_model: str,
        embedding_dimensions: int,
        limit: int,
    ) -> list[RetrievalCandidate]:
        distance = DocumentChunk.embedding.cosine_distance(list(query_vector))
        rows = (
            await self.session.execute(
                select(
                    DocumentChunk.id,
                    DocumentChunk.document_id,
                    Document.original_filename,
                    DocumentChunk.page_start,
                    DocumentChunk.page_end,
                    DocumentChunk.text,
                    distance.label("cosine_distance"),
                )
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(
                    Document.subject_id == subject_id,
                    Document.status == "READY",
                    Document.embedding_provider == embedding_provider,
                    Document.embedding_model == embedding_model,
                    Document.embedding_dimensions == embedding_dimensions,
                )
                .order_by(
                    distance.asc(),
                    Document.id.asc(),
                    DocumentChunk.chunk_index.asc(),
                    DocumentChunk.id.asc(),
                )
                .limit(limit)
            )
        ).all()
        return [
            RetrievalCandidate(
                chunk_id=row.id,
                document_id=row.document_id,
                document_filename=row.original_filename,
                page_start=row.page_start,
                page_end=row.page_end,
                text=row.text,
                cosine_distance=(
                    float(row.cosine_distance)
                    if row.cosine_distance is not None
                    else float("inf")
                ),
            )
            for row in rows
        ]
