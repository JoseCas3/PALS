from __future__ import annotations

import uuid
from collections.abc import Sequence

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_embedding_provider
from app.core.errors import ApplicationError
from app.embeddings.contracts import ProviderEmbedding
from app.embeddings.fake import FakeEmbeddingProvider
from app.embeddings.service import EmbeddingService
from app.ingestion.chunking import DocumentChunker
from app.ingestion.normalization import TextNormalizer
from app.ingestion.service import IngestionService
from app.main import app as fastapi_app
from app.models.attempt import Attempt
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.mastery import Mastery
from app.repositories.document_chunks import DocumentChunkRepository
from app.repositories.documents import DocumentRepository
from app.storage.documents import LocalDocumentStorage
from tests.pdf_factory import make_pdf
from tests.test_documents import upload_document
from tests.test_ingestion import StaticExtractor, page, process_document
from tests.test_subjects import create_subject


def publication_service(
    session: AsyncSession,
    storage: LocalDocumentStorage,
    provider: FakeEmbeddingProvider,
) -> IngestionService:
    text = " ".join(f"token{index}" for index in range(35))
    return IngestionService(
        session,
        storage,
        StaticExtractor((page(1, text),)),
        TextNormalizer(),
        DocumentChunker(10, 1),
        EmbeddingService(provider, batch_size=1, dimensions=1536),
    )


async def chunk_count(session: AsyncSession, document_id: uuid.UUID) -> int:
    return int(
        await session.scalar(
            select(func.count()).select_from(DocumentChunk).where(
                DocumentChunk.document_id == document_id
            )
        )
        or 0
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_call", [1, 2, 4])
async def test_embedding_failure_in_any_batch_publishes_zero_chunks(
    async_client: AsyncClient,
    db_session: AsyncSession,
    document_storage: LocalDocumentStorage,
    failure_call: int,
) -> None:
    subject = await create_subject(async_client)
    uploaded = await upload_document(
        async_client,
        subject["id"],
        content=make_pdf(["Legacy PDF has enough deterministic text for an R3 upgrade."]),
    )
    document_id = uuid.UUID(str(uploaded["id"]))
    service = publication_service(
        db_session,
        document_storage,
        FakeEmbeddingProvider(failure="unavailable", failure_call=failure_call),
    )

    with pytest.raises(ApplicationError, match="temporarily unavailable") as raised:
        await service.process(document_id)

    document = await db_session.get(Document, document_id)
    assert raised.value.code == "EMBEDDING_UNAVAILABLE"
    assert document is not None and document.status == "FAILED"
    assert document.error_code == "EMBEDDING_UNAVAILABLE"
    assert await chunk_count(db_session, document_id) == 0
    assert await db_session.scalar(select(func.count()).select_from(Attempt)) == 0
    assert await db_session.scalar(select(func.count()).select_from(Mastery)) == 0


@pytest.mark.asyncio
async def test_wrong_dimensions_fail_safely_without_partial_chunks(
    async_client: AsyncClient,
    db_session: AsyncSession,
    document_storage: LocalDocumentStorage,
) -> None:
    subject = await create_subject(async_client)
    uploaded = await upload_document(
        async_client,
        subject["id"],
        content=make_pdf(["Legacy PDF has enough deterministic text for an R3 upgrade."]),
    )
    document_id = uuid.UUID(str(uploaded["id"]))
    service = publication_service(
        db_session, document_storage, FakeEmbeddingProvider(failure="wrong_dimensions")
    )

    with pytest.raises(ApplicationError) as raised:
        await service.process(document_id)

    assert raised.value.code == "EMBEDDING_DIMENSION_MISMATCH"
    assert await chunk_count(db_session, document_id) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_point", ["chunks", "ready"])
async def test_publication_insert_or_ready_failure_rolls_back_every_chunk(
    async_client: AsyncClient,
    db_session: AsyncSession,
    document_storage: LocalDocumentStorage,
    monkeypatch: pytest.MonkeyPatch,
    failure_point: str,
) -> None:
    subject = await create_subject(async_client)
    uploaded = await upload_document(async_client, subject["id"])
    document_id = uuid.UUID(str(uploaded["id"]))

    async def fail(*args: object, **kwargs: object) -> object:
        raise RuntimeError("private publication failure")

    target = DocumentChunkRepository if failure_point == "chunks" else DocumentRepository
    method = "replace" if failure_point == "chunks" else "publish_ready"
    monkeypatch.setattr(target, method, fail)

    with pytest.raises(ApplicationError) as raised:
        await publication_service(
            db_session, document_storage, FakeEmbeddingProvider()
        ).process(document_id)

    document = await db_session.get(Document, document_id)
    assert raised.value.code == "PROCESSING_FAILED"
    assert document is not None and document.status == "FAILED"
    assert await chunk_count(db_session, document_id) == 0


@pytest.mark.asyncio
async def test_publication_commit_failure_rolls_back_and_marks_failed(
    async_client: AsyncClient,
    db_session: AsyncSession,
    document_storage: LocalDocumentStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subject = await create_subject(async_client)
    uploaded = await upload_document(async_client, subject["id"])
    document_id = uuid.UUID(str(uploaded["id"]))
    real_commit = db_session.commit
    calls = 0

    async def fail_second_commit() -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("private commit failure")
        await real_commit()

    monkeypatch.setattr(db_session, "commit", fail_second_commit)
    with pytest.raises(ApplicationError) as raised:
        await publication_service(
            db_session, document_storage, FakeEmbeddingProvider()
        ).process(document_id)

    document = await db_session.get(Document, document_id)
    assert raised.value.code == "PROCESSING_FAILED"
    assert document is not None and document.status == "FAILED"
    assert await chunk_count(db_session, document_id) == 0


@pytest.mark.asyncio
async def test_failed_retry_publishes_exactly_one_ordered_chunk_set(
    async_client: AsyncClient,
    db_session: AsyncSession,
    document_storage: LocalDocumentStorage,
) -> None:
    subject = await create_subject(async_client)
    uploaded = await upload_document(async_client, subject["id"])
    document_id = uuid.UUID(str(uploaded["id"]))
    with pytest.raises(ApplicationError):
        await publication_service(
            db_session,
            document_storage,
            FakeEmbeddingProvider(failure="unavailable"),
        ).process(document_id)

    document = await publication_service(
        db_session, document_storage, FakeEmbeddingProvider()
    ).process(document_id)
    chunks = list(
        await db_session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
    )

    expected = DocumentChunker(10, 1).chunk(
        (page(1, " ".join(f"token{index}" for index in range(35))),)
    )
    assert document.status == "READY" and document.error_code is None
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert len(chunks) == len({chunk.chunk_index for chunk in chunks}) == len(expected) == 4
    assert [chunk.text for chunk in chunks] == [chunk.text for chunk in expected]
    assert [chunk.page_start for chunk in chunks] == [chunk.page_start for chunk in expected]
    assert [chunk.page_end for chunk in chunks] == [chunk.page_end for chunk in expected]
    assert [chunk.token_count for chunk in chunks] == [chunk.token_count for chunk in expected]
    assert all(len(chunk.embedding) == 1536 for chunk in chunks)


@pytest.mark.asyncio
async def test_legacy_r2_ready_document_can_be_upgraded(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    subject = await create_subject(async_client)
    uploaded = await upload_document(
        async_client,
        subject["id"],
        content=make_pdf(["Legacy PDF has enough deterministic text for an R3 upgrade."]),
    )
    document_id = uuid.UUID(str(uploaded["id"]))
    document = await db_session.get(Document, document_id)
    assert document is not None
    document.status = "READY"
    await db_session.flush()

    response = await process_document(async_client, document_id)

    await db_session.refresh(document)
    assert response.status_code == 200
    assert document.status == "READY"
    assert document.embedding_provider == "fake"
    assert document.embedding_model == "fake-deterministic-v1"
    assert document.embedding_dimensions == 1536
    assert await chunk_count(db_session, document_id) > 0


@pytest.mark.asyncio
async def test_legacy_upgrade_embedding_failure_becomes_failed_without_chunks(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    subject = await create_subject(async_client)
    uploaded = await upload_document(
        async_client,
        subject["id"],
        content=make_pdf(["Legacy PDF has enough deterministic text for an R3 upgrade."]),
    )
    document_id = uuid.UUID(str(uploaded["id"]))
    document = await db_session.get(Document, document_id)
    assert document is not None
    document.status = "READY"
    await db_session.flush()
    fastapi_app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider(
        failure="unavailable"
    )

    response = await process_document(async_client, document_id)

    await db_session.refresh(document)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "EMBEDDING_UNAVAILABLE"
    assert document.status == "FAILED"
    assert await chunk_count(db_session, document_id) == 0


@pytest.mark.asyncio
async def test_no_database_transaction_spans_provider_invocation(
    async_client: AsyncClient,
    db_session: AsyncSession,
    document_storage: LocalDocumentStorage,
) -> None:
    subject = await create_subject(async_client)
    uploaded = await upload_document(async_client, subject["id"])

    class TransactionCheckingProvider(FakeEmbeddingProvider):
        async def embed(self, texts: Sequence[str]) -> Sequence[ProviderEmbedding]:
            assert not db_session.in_transaction()
            return await super().embed(texts)

    document = await publication_service(
        db_session, document_storage, TransactionCheckingProvider()
    ).process(uuid.UUID(str(uploaded["id"])))
    assert document.status == "READY"


@pytest.mark.asyncio
async def test_document_delete_cascades_chunks_and_removes_pdf(
    async_client: AsyncClient,
    db_session: AsyncSession,
    document_storage: LocalDocumentStorage,
) -> None:
    subject = await create_subject(async_client)
    uploaded = await upload_document(
        async_client,
        subject["id"],
        content=make_pdf(["Delete cascade PDF has enough deterministic text for processing."]),
    )
    document_id = uuid.UUID(str(uploaded["id"]))
    response = await process_document(async_client, document_id)
    assert response.status_code == 200
    document = await db_session.get(Document, document_id)
    assert document is not None
    storage_key = document.storage_key
    assert document_storage.exists(storage_key)
    assert await chunk_count(db_session, document_id) > 0

    deleted = await async_client.delete(f"/api/v1/documents/{document_id}")

    assert deleted.status_code == 204
    assert await db_session.get(Document, document_id) is None
    assert await chunk_count(db_session, document_id) == 0
    assert not document_storage.exists(storage_key)
