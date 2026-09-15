from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import BinaryIO, NoReturn

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.embeddings.contracts import (
    EmbeddingDimensionMismatchError,
    EmbeddingError,
    EmbeddingUnavailableError,
)
from app.embeddings.service import EmbeddingService
from app.ingestion.chunking import ChunkingError, DocumentChunker, ProcessedChunk
from app.ingestion.extraction import DocumentExtractor, ExtractedPage, TextExtractionError
from app.ingestion.normalization import TextNormalizer
from app.models.document import Document, DocumentStatus
from app.repositories.document_chunks import DocumentChunkRepository
from app.repositories.documents import DocumentRepository
from app.storage.documents import DocumentStorage, DocumentStorageError

logger = logging.getLogger(__name__)
MIN_EXTRACTED_TEXT_CHARACTERS = 32


class InsufficientTextError(Exception):
    pass


@dataclass(frozen=True)
class ProcessedDocument:
    pages: tuple[ExtractedPage, ...]
    chunks: tuple[ProcessedChunk, ...]


class IngestionService:
    def __init__(
        self,
        session: AsyncSession,
        storage: DocumentStorage,
        extractor: DocumentExtractor,
        normalizer: TextNormalizer,
        chunker: DocumentChunker,
        embeddings: EmbeddingService,
    ) -> None:
        self.session = session
        self.storage = storage
        self.extractor = extractor
        self.normalizer = normalizer
        self.chunker = chunker
        self.embeddings = embeddings
        self.documents = DocumentRepository(session)
        self.document_chunks = DocumentChunkRepository(session)

    def ingest(self, source: BinaryIO) -> ProcessedDocument:
        extracted = self.extractor.extract(source)
        pages = self.normalizer.normalize_pages(extracted.pages)
        character_count = sum(
            1 for page in pages for character in page.text if not character.isspace()
        )
        if character_count < MIN_EXTRACTED_TEXT_CHARACTERS:
            raise InsufficientTextError("PDF has insufficient extractable text")
        return ProcessedDocument(pages=pages, chunks=self.chunker.chunk(pages))

    async def process(self, document_id: uuid.UUID) -> Document:
        document = await self.documents.claim_processing(document_id)
        if document is None:
            await self._raise_claim_error(document_id)
        await self.session.commit()

        try:
            result = await asyncio.to_thread(self._ingest_storage_document, document.storage_key)
        except TextExtractionError as exc:
            await self._fail(document_id, "TEXT_EXTRACTION_FAILED")
            raise ApplicationError(
                422, "TEXT_EXTRACTION_FAILED", "PDF text extraction failed"
            ) from exc
        except InsufficientTextError as exc:
            await self._fail(document_id, "TEXT_EXTRACTION_INSUFFICIENT")
            raise ApplicationError(
                422,
                "TEXT_EXTRACTION_INSUFFICIENT",
                "PDF does not contain enough extractable text",
            ) from exc
        except ChunkingError as exc:
            await self._fail(document_id, "CHUNKING_FAILED")
            raise ApplicationError(500, "CHUNKING_FAILED", "Document chunking failed") from exc
        except DocumentStorageError as exc:
            await self._fail(document_id, "PROCESSING_FAILED")
            raise ApplicationError(500, "PROCESSING_FAILED", "Document processing failed") from exc
        except Exception as exc:
            logger.error(
                "Document processing failed document_id=%s exception_class=%s",
                document_id,
                type(exc).__name__,
            )
            await self._fail(document_id, "PROCESSING_FAILED")
            raise ApplicationError(500, "PROCESSING_FAILED", "Document processing failed") from exc

        try:
            vectors = await self.embeddings.embed([chunk.text for chunk in result.chunks])
        except EmbeddingUnavailableError as exc:
            await self._fail(document_id, exc.code)
            raise ApplicationError(
                503, exc.code, "Embedding service is temporarily unavailable"
            ) from exc
        except EmbeddingDimensionMismatchError as exc:
            await self._fail(document_id, exc.code)
            raise ApplicationError(500, exc.code, "Embedding dimensions are invalid") from exc
        except EmbeddingError as exc:
            await self._fail(document_id, exc.code)
            raise ApplicationError(502, exc.code, "Embedding generation failed") from exc
        except Exception as exc:
            logger.error(
                "Embedding generation failed document_id=%s exception_class=%s",
                document_id,
                type(exc).__name__,
            )
            await self._fail(document_id, "EMBEDDING_FAILED")
            raise ApplicationError(
                502, "EMBEDDING_FAILED", "Embedding generation failed"
            ) from exc

        try:
            await self.document_chunks.replace(document_id, result.chunks, vectors)
            document = await self.documents.publish_ready(
                document_id,
                embedding_provider=self.embeddings.provider.provider_name,
                embedding_model=self.embeddings.provider.model_name,
                embedding_dimensions=self.embeddings.dimensions,
            )
            await self.session.commit()
        except Exception as exc:
            await self.session.rollback()
            logger.error(
                "Document publication failed document_id=%s exception_class=%s",
                document_id,
                type(exc).__name__,
            )
            await self._fail(document_id, "PROCESSING_FAILED")
            raise ApplicationError(500, "PROCESSING_FAILED", "Document processing failed") from exc
        logger.info(
            "Document processing completed document_id=%s page_count=%s chunk_count=%s",
            document_id,
            len(result.pages),
            len(result.chunks),
        )
        return document

    def _ingest_storage_document(self, storage_key: str) -> ProcessedDocument:
        with self.storage.open(storage_key) as source:
            return self.ingest(source)

    async def _fail(self, document_id: uuid.UUID, error_code: str) -> None:
        await self.session.rollback()
        await self.document_chunks.delete_for_document(document_id)
        await self.documents.finish_processing(
            document_id, status=DocumentStatus.FAILED.value, error_code=error_code
        )
        await self.session.commit()

    async def _raise_claim_error(self, document_id: uuid.UUID) -> NoReturn:
        document = await self.documents.get(document_id)
        if document is None:
            raise ApplicationError(404, "DOCUMENT_NOT_FOUND", "Document not found")
        if document.status == DocumentStatus.PROCESSING.value:
            raise ApplicationError(
                status.HTTP_409_CONFLICT,
                "DOCUMENT_ALREADY_PROCESSING",
                "Document is already processing",
            )
        if document.status == DocumentStatus.READY.value:
            raise ApplicationError(
                status.HTTP_409_CONFLICT,
                "DOCUMENT_ALREADY_PROCESSED",
                "Document has already been processed",
            )
        raise ApplicationError(
            status.HTTP_409_CONFLICT,
            "DOCUMENT_NOT_PROCESSABLE",
            "Document cannot be processed from its current state",
        )
