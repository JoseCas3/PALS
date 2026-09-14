import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document


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

    async def delete(self, document: Document) -> None:
        await self.session.delete(document)
        await self.session.flush()
