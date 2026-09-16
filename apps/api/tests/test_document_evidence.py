from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gateway import AIGateway
from app.embeddings.service import EmbeddingService
from app.models import AIInteraction, Attempt, Mastery
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.repositories.document_chunks import DocumentChunkRepository
from app.retrieval.service import RetrievalService
from tests.test_retrieval import add_chunk, ready_document, vector
from tests.test_subjects import create_subject


async def create_evidence(
    client: AsyncClient,
    session: AsyncSession,
    *,
    filename: str = "course-notes.pdf",
    text: str = "Exact cited evidence from the uploaded document.",
    page_start: int = 2,
    page_end: int = 4,
    status: str = "READY",
) -> tuple[Document, DocumentChunk]:
    subject = await create_subject(client)
    document = await ready_document(
        client,
        session,
        subject["id"],
        filename=filename,
        content=f"%PDF-{uuid.uuid4()}".encode(),
        status=status,
    )
    chunk = add_chunk(
        session,
        document,
        index=0,
        text=text,
        embedding=vector(),
        page_start=page_start,
        page_end=page_end,
    )
    await session.flush()
    return document, chunk


@pytest.mark.asyncio
async def test_exact_ready_evidence_is_safe_and_evidence_neutral(
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document, chunk = await create_evidence(
        async_client,
        db_session,
        filename="<b>untrusted</b>.pdf",
        text="Line one\n<script>alert('source')</script>",
        page_start=3,
        page_end=5,
    )

    async def forbidden(*_: object, **__: object) -> object:
        raise AssertionError("Evidence lookup must not invoke AI, embeddings, or retrieval")

    monkeypatch.setattr(RetrievalService, "retrieve", forbidden)
    monkeypatch.setattr(EmbeddingService, "embed", forbidden)
    monkeypatch.setattr(AIGateway, "generate", forbidden)
    before = (
        await db_session.scalar(select(func.count()).select_from(Attempt)),
        await db_session.scalar(select(func.count()).select_from(Mastery)),
        await db_session.scalar(select(func.count()).select_from(AIInteraction)),
    )

    response = await async_client.get(
        f"/api/v1/documents/{document.id}/chunks/{chunk.id}"
    )

    assert response.status_code == 200
    assert response.json() == {
        "chunk_id": str(chunk.id),
        "document_id": str(document.id),
        "document_filename": "<b>untrusted</b>.pdf",
        "page_start": 3,
        "page_end": 5,
        "text": "Line one\n<script>alert('source')</script>",
    }
    serialized = response.text
    assert "embedding" not in serialized
    assert "storage_key" not in serialized
    assert document.storage_key not in serialized
    after = (
        await db_session.scalar(select(func.count()).select_from(Attempt)),
        await db_session.scalar(select(func.count()).select_from(Mastery)),
        await db_session.scalar(select(func.count()).select_from(AIInteraction)),
    )
    assert after == before


@pytest.mark.asyncio
async def test_cross_document_chunk_is_not_found(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    first, _ = await create_evidence(async_client, db_session, filename="first.pdf")
    _, second_chunk = await create_evidence(
        async_client, db_session, filename="second.pdf"
    )

    response = await async_client.get(
        f"/api/v1/documents/{first.id}/chunks/{second_chunk.id}"
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DOCUMENT_EVIDENCE_NOT_FOUND"
    assert "second.pdf" not in response.text


@pytest.mark.asyncio
async def test_missing_document_and_missing_chunk_are_safe(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    document, _ = await create_evidence(async_client, db_session)

    missing_document = await async_client.get(
        f"/api/v1/documents/{uuid.uuid4()}/chunks/{uuid.uuid4()}"
    )
    missing_chunk = await async_client.get(
        f"/api/v1/documents/{document.id}/chunks/{uuid.uuid4()}"
    )

    assert missing_document.status_code == 404
    assert missing_document.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"
    assert missing_chunk.status_code == 404
    assert missing_chunk.json()["error"]["code"] == "DOCUMENT_EVIDENCE_NOT_FOUND"


@pytest.mark.asyncio
@pytest.mark.parametrize("document_status", ["FAILED", "PROCESSING"])
async def test_non_ready_document_evidence_is_unavailable(
    async_client: AsyncClient,
    db_session: AsyncSession,
    document_status: str,
) -> None:
    document, chunk = await create_evidence(
        async_client, db_session, status=document_status
    )

    response = await async_client.get(
        f"/api/v1/documents/{document.id}/chunks/{chunk.id}"
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DOCUMENT_EVIDENCE_NOT_FOUND"
    assert chunk.text not in response.text


@pytest.mark.asyncio
async def test_deleted_document_and_chunk_are_unavailable(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    document, chunk = await create_evidence(async_client, db_session)

    deleted = await async_client.delete(f"/api/v1/documents/{document.id}")
    response = await async_client.get(
        f"/api/v1/documents/{document.id}/chunks/{chunk.id}"
    )

    assert deleted.status_code == 204
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.id == chunk.id)
        )
        == 0
    )


@pytest.mark.asyncio
async def test_evidence_database_failure_is_sanitized(
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document, chunk = await create_evidence(async_client, db_session)

    async def fail_lookup(*_: object, **__: object) -> None:
        raise DBAPIError(
            "SELECT secret FROM document_chunks",
            ("private chunk text",),
            RuntimeError("private database detail"),
            False,
        )

    monkeypatch.setattr(DocumentChunkRepository, "get_ready_evidence", fail_lookup)
    response = await async_client.get(
        f"/api/v1/documents/{document.id}/chunks/{chunk.id}"
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "DATABASE_ERROR"
    assert "private" not in response.text
