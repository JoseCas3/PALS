from __future__ import annotations

import asyncio
import hashlib
import uuid
from collections.abc import Sequence

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.embeddings.contracts import ProviderEmbedding
from app.embeddings.fake import FakeEmbeddingProvider
from app.embeddings.service import EmbeddingService
from app.ingestion.chunking import DocumentChunker
from app.ingestion.normalization import TextNormalizer
from app.ingestion.service import IngestionService
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.subject import Subject
from app.services.documents import DocumentService
from app.storage.documents import LocalDocumentStorage
from tests.conftest import test_engine
from tests.test_ingestion import StaticExtractor, page


class GatedEmbeddingProvider(FakeEmbeddingProvider):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def embed(self, texts: Sequence[str]) -> Sequence[ProviderEmbedding]:
        self.started.set()
        await self.release.wait()
        return await super().embed(texts)


def ingestion_service(
    session: AsyncSession,
    storage: LocalDocumentStorage,
    provider: FakeEmbeddingProvider,
) -> IngestionService:
    return IngestionService(
        session,
        storage,
        StaticExtractor((page(1, "Deterministic integration evidence for retrieval hardening."),)),
        TextNormalizer(),
        DocumentChunker(20, 2),
        EmbeddingService(provider, batch_size=8, dimensions=1536),
    )


async def committed_document(storage: LocalDocumentStorage) -> tuple[uuid.UUID, uuid.UUID]:
    subject_id = uuid.uuid4()
    document_id = uuid.uuid4()
    content = b"%PDF-1.4 integration race fixture"
    storage_key = f"{str(document_id)[:2]}/{document_id}.pdf"
    storage.save(storage_key, content)
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        session.add(Subject(id=subject_id, name=f"R7 {subject_id}"))
        await session.flush()
        session.add(
            Document(
                id=document_id,
                subject_id=subject_id,
                original_filename="r7.pdf",
                storage_key=storage_key,
                mime_type="application/pdf",
                size_bytes=len(content),
                checksum_sha256=hashlib.sha256(content).hexdigest(),
                status="UPLOADED",
                processing_version=1,
            )
        )
        await session.commit()
    return subject_id, document_id


async def cleanup_subject(subject_id: uuid.UUID) -> None:
    async with AsyncSession(test_engine) as session:
        await session.execute(delete(Subject).where(Subject.id == subject_id))
        await session.commit()


@pytest.mark.asyncio
async def test_exactly_one_concurrent_processing_claim_publishes_one_chunk_set(
    document_storage: LocalDocumentStorage,
) -> None:
    subject_id, document_id = await committed_document(document_storage)
    provider = GatedEmbeddingProvider()
    try:
        async with (
            AsyncSession(test_engine, expire_on_commit=False) as first_session,
            AsyncSession(test_engine, expire_on_commit=False) as second_session,
        ):
            first = asyncio.create_task(
                ingestion_service(first_session, document_storage, provider).process(document_id)
            )
            await asyncio.wait_for(provider.started.wait(), timeout=5)

            with pytest.raises(ApplicationError) as raised:
                await ingestion_service(
                    second_session, document_storage, FakeEmbeddingProvider()
                ).process(document_id)

            assert raised.value.code == "DOCUMENT_ALREADY_PROCESSING"
            provider.release.set()
            published = await asyncio.wait_for(first, timeout=5)
            assert published.status == "READY"

        async with AsyncSession(test_engine) as verification:
            document = await verification.get(Document, document_id)
            chunk_count = await verification.scalar(
                select(func.count()).select_from(DocumentChunk).where(
                    DocumentChunk.document_id == document_id
                )
            )
            assert document is not None
            assert document.embedding_provider == "fake"
            assert document.embedding_model == "fake-deterministic-v1"
            assert document.embedding_dimensions == 1536
            assert chunk_count == 1
            assert provider.call_count == 1
            await DocumentService(verification, document_storage).delete(document_id)
    finally:
        provider.release.set()
        await cleanup_subject(subject_id)


@pytest.mark.asyncio
async def test_delete_during_processing_fails_safely_without_corrupted_ready_state(
    document_storage: LocalDocumentStorage,
) -> None:
    subject_id, document_id = await committed_document(document_storage)
    provider = GatedEmbeddingProvider()
    try:
        async with (
            AsyncSession(test_engine, expire_on_commit=False) as processing_session,
            AsyncSession(test_engine, expire_on_commit=False) as deleting_session,
        ):
            processing = asyncio.create_task(
                ingestion_service(processing_session, document_storage, provider).process(
                    document_id
                )
            )
            await asyncio.wait_for(provider.started.wait(), timeout=5)
            await DocumentService(deleting_session, document_storage).delete(document_id)
            provider.release.set()

            with pytest.raises(ApplicationError) as raised:
                await asyncio.wait_for(processing, timeout=5)

            assert raised.value.code == "PROCESSING_FAILED"

        async with AsyncSession(test_engine) as verification:
            assert await verification.get(Document, document_id) is None
            assert (
                await verification.scalar(
                    select(func.count()).select_from(DocumentChunk).where(
                        DocumentChunk.document_id == document_id
                    )
                )
                == 0
            )
    finally:
        provider.release.set()
        await cleanup_subject(subject_id)
