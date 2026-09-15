from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.embeddings.contracts import EmbeddingVector
from app.ingestion.chunking import ProcessedChunk
from app.models.document_chunk import DocumentChunk


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
