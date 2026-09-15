import uuid

from sqlalchemy import exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_chunk import DocumentChunk


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_subject(self, subject_id: uuid.UUID) -> list[Document]:
        result = await self.session.scalars(
            select(Document)
            .where(Document.subject_id == subject_id)
            .order_by(Document.created_at, Document.id)
        )
        return list(result)

    async def get(self, document_id: uuid.UUID) -> Document | None:
        return await self.session.get(Document, document_id)

    async def get_by_checksum(
        self, subject_id: uuid.UUID, checksum_sha256: str
    ) -> Document | None:
        result = await self.session.scalars(
            select(Document).where(
                Document.subject_id == subject_id,
                Document.checksum_sha256 == checksum_sha256,
            )
        )
        return result.first()

    async def create(self, **values: object) -> Document:
        document = Document(**values)
        self.session.add(document)
        await self.session.flush()
        await self.session.refresh(document)
        return document

    async def claim_processing(self, document_id: uuid.UUID) -> Document | None:
        has_chunks = exists(
            select(DocumentChunk.id).where(DocumentChunk.document_id == Document.id)
        )
        result = await self.session.scalars(
            update(Document)
            .where(
                Document.id == document_id,
                (
                    Document.status.in_(("UPLOADED", "FAILED"))
                    | (
                        (Document.status == "READY")
                        & Document.embedding_provider.is_(None)
                        & Document.embedding_model.is_(None)
                        & Document.embedding_dimensions.is_(None)
                        & ~has_chunks
                    )
                ),
            )
            .values(
                status="PROCESSING",
                error_code=None,
                embedding_provider=None,
                embedding_model=None,
                embedding_dimensions=None,
            )
            .returning(Document)
        )
        return result.one_or_none()

    async def publish_ready(
        self,
        document_id: uuid.UUID,
        *,
        embedding_provider: str,
        embedding_model: str,
        embedding_dimensions: int,
    ) -> Document:
        result = await self.session.scalars(
            update(Document)
            .where(Document.id == document_id, Document.status == "PROCESSING")
            .values(
                status="READY",
                error_code=None,
                embedding_provider=embedding_provider,
                embedding_model=embedding_model,
                embedding_dimensions=embedding_dimensions,
            )
            .returning(Document)
        )
        return result.one()

    async def finish_processing(
        self, document_id: uuid.UUID, *, status: str, error_code: str | None
    ) -> Document:
        result = await self.session.scalars(
            update(Document)
            .where(Document.id == document_id, Document.status == "PROCESSING")
            .values(status=status, error_code=error_code)
            .returning(Document)
        )
        document = result.one()
        return document

    async def delete(self, document: Document) -> None:
        await self.session.delete(document)
        await self.session.flush()
