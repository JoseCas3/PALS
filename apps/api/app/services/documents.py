from __future__ import annotations

import asyncio
import hashlib
import uuid
from contextlib import suppress

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.models.document import Document, DocumentStatus
from app.repositories.documents import DocumentRepository
from app.repositories.subjects import SubjectRepository
from app.storage.documents import DocumentStorage, DocumentStorageError


class DocumentService:
    def __init__(self, session: AsyncSession, storage: DocumentStorage) -> None:
        self.session = session
        self.storage = storage
        self.documents = DocumentRepository(session)
        self.subjects = SubjectRepository(session)

    async def list_for_subject(self, subject_id: uuid.UUID) -> list[Document]:
        await self._require_subject(subject_id)
        return await self.documents.list_for_subject(subject_id)

    async def get(self, document_id: uuid.UUID) -> Document:
        document = await self.documents.get(document_id)
        if document is None:
            raise ApplicationError(404, "DOCUMENT_NOT_FOUND", "Document not found")
        return document

    async def upload(
        self,
        subject_id: uuid.UUID,
        *,
        original_filename: str | None,
        mime_type: str | None,
        content: bytes,
        max_size_bytes: int,
    ) -> Document:
        await self._require_subject(subject_id)
        filename = self._validate_upload(
            original_filename=original_filename,
            mime_type=mime_type,
            content=content,
            max_size_bytes=max_size_bytes,
        )
        checksum = hashlib.sha256(content).hexdigest()
        if await self.documents.get_by_checksum(subject_id, checksum) is not None:
            raise ApplicationError(
                status.HTTP_409_CONFLICT,
                "DOCUMENT_ALREADY_EXISTS",
                "This document already exists for the Subject",
            )

        document_id = uuid.uuid4()
        storage_key = f"{str(document_id)[:2]}/{document_id}.pdf"
        try:
            await asyncio.to_thread(self.storage.save, storage_key, content)
        except DocumentStorageError as exc:
            raise ApplicationError(
                500, "DOCUMENT_STORAGE_ERROR", "Document storage operation failed"
            ) from exc

        try:
            document = await self.documents.create(
                id=document_id,
                subject_id=subject_id,
                original_filename=filename,
                storage_key=storage_key,
                mime_type="application/pdf",
                size_bytes=len(content),
                checksum_sha256=checksum,
                status=DocumentStatus.UPLOADED.value,
                error_code=None,
                processing_version=1,
                embedding_provider=None,
                embedding_model=None,
                embedding_dimensions=None,
            )
            await self.session.commit()
            return document
        except IntegrityError as exc:
            await self.session.rollback()
            await self._best_effort_delete(storage_key)
            raise ApplicationError(
                status.HTTP_409_CONFLICT,
                "DOCUMENT_ALREADY_EXISTS",
                "This document already exists for the Subject",
            ) from exc
        except Exception:
            await self.session.rollback()
            await self._best_effort_delete(storage_key)
            raise

    async def delete(self, document_id: uuid.UUID) -> None:
        document = await self.get(document_id)
        try:
            await asyncio.to_thread(self.storage.delete, document.storage_key)
        except DocumentStorageError as exc:
            raise ApplicationError(
                500, "DOCUMENT_STORAGE_ERROR", "Document storage operation failed"
            ) from exc
        await self.documents.delete(document)
        await self.session.commit()

    async def _require_subject(self, subject_id: uuid.UUID) -> None:
        if await self.subjects.get(subject_id) is None:
            raise ApplicationError(404, "RESOURCE_NOT_FOUND", "Subject not found")

    @staticmethod
    def _validate_upload(
        *,
        original_filename: str | None,
        mime_type: str | None,
        content: bytes,
        max_size_bytes: int,
    ) -> str:
        if not original_filename or "\x00" in original_filename or len(original_filename) > 255:
            raise ApplicationError(422, "UNSUPPORTED_FILE_TYPE", "A valid PDF filename is required")
        if not original_filename.lower().endswith(".pdf"):
            raise ApplicationError(415, "UNSUPPORTED_FILE_TYPE", "Only PDF documents are supported")
        if mime_type and mime_type.lower() != "application/pdf":
            raise ApplicationError(415, "UNSUPPORTED_FILE_TYPE", "Only PDF documents are supported")
        if len(content) > max_size_bytes:
            raise ApplicationError(413, "FILE_TOO_LARGE", "Document exceeds the upload size limit")
        if not content or not content.startswith(b"%PDF-"):
            raise ApplicationError(422, "INVALID_PDF", "Document is not a valid PDF")
        return original_filename

    async def _best_effort_delete(self, storage_key: str) -> None:
        with suppress(DocumentStorageError):
            await asyncio.to_thread(self.storage.delete, storage_key)
