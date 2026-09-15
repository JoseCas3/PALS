from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_chunk import DocumentChunk
from tests.test_documents import upload_document
from tests.test_subjects import create_subject


def vector(value: float = 0.0) -> list[float]:
    return [value] * 1536


@pytest.mark.asyncio
async def test_vector_extension_insert_read_type_and_cosine_operator(
    async_client: object, db_session: AsyncSession
) -> None:
    version = await db_session.scalar(
        text("SELECT extversion FROM pg_extension WHERE extname='vector'")
    )
    type_name = await db_session.scalar(
        text(
            "SELECT format_type(a.atttypid, a.atttypmod) "
            "FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid "
            "WHERE c.relname='document_chunks' AND a.attname='embedding'"
        )
    )
    distance = await db_session.scalar(
        text("SELECT ('[1,0]'::vector <=> '[0,1]'::vector)::float")
    )

    assert version == "0.8.6"
    assert type_name == "vector(1536)"
    assert distance == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_document_chunk_insert_read_and_cascade(
    async_client: object, db_session: AsyncSession
) -> None:
    subject = await create_subject(async_client)  # type: ignore[arg-type]
    document = await upload_document(async_client, subject["id"])  # type: ignore[arg-type]
    document_id = uuid.UUID(str(document["id"]))
    chunk = DocumentChunk(
        document_id=document_id,
        chunk_index=0,
        text="persisted text",
        page_start=1,
        page_end=1,
        token_count=2,
        embedding=vector(0.25),
    )
    db_session.add(chunk)
    await db_session.flush()
    await db_session.refresh(chunk)
    assert len(chunk.embedding) == 1536

    await db_session.execute(text("DELETE FROM documents WHERE id=:id"), {"id": document_id})
    assert await db_session.scalar(
        select(DocumentChunk.id).where(DocumentChunk.document_id == document_id)
    ) is None


@pytest.mark.asyncio
async def test_document_chunk_unique_document_index_is_enforced(
    async_client: object, db_session: AsyncSession
) -> None:
    subject = await create_subject(async_client)  # type: ignore[arg-type]
    document = await upload_document(async_client, subject["id"])  # type: ignore[arg-type]
    document_id = uuid.UUID(str(document["id"]))
    original = DocumentChunk(
        document_id=document_id,
        chunk_index=0,
        text="original",
        page_start=1,
        page_end=1,
        token_count=1,
        embedding=vector(),
    )
    duplicate = DocumentChunk(
        document_id=document_id,
        chunk_index=0,
        text="duplicate",
        page_start=1,
        page_end=1,
        token_count=1,
        embedding=vector(),
    )
    db_session.add_all([original, duplicate])
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_wrong_vector_dimension_is_rejected(
    async_client: object, db_session: AsyncSession
) -> None:
    subject = await create_subject(async_client)  # type: ignore[arg-type]
    document = await upload_document(async_client, subject["id"])  # type: ignore[arg-type]
    db_session.add(
        DocumentChunk(
            document_id=uuid.UUID(str(document["id"])),
            chunk_index=0,
            text="wrong vector",
            page_start=1,
            page_end=1,
            token_count=2,
            embedding=[0.0] * 3,
        )
    )
    with pytest.raises(DBAPIError):
        await db_session.flush()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "values",
    [
        {"chunk_index": -1},
        {"page_start": 0},
        {"page_start": 2, "page_end": 1},
        {"token_count": 0},
        {"text": "   "},
    ],
)
async def test_document_chunk_checks_are_enforced(
    async_client: object, db_session: AsyncSession, values: dict[str, object]
) -> None:
    subject = await create_subject(async_client)  # type: ignore[arg-type]
    document = await upload_document(async_client, subject["id"])  # type: ignore[arg-type]
    fields: dict[str, object] = {
        "document_id": uuid.UUID(str(document["id"])),
        "chunk_index": 0,
        "text": "valid",
        "page_start": 1,
        "page_end": 1,
        "token_count": 1,
        "embedding": vector(),
    }
    fields.update(values)
    db_session.add(DocumentChunk(**fields))
    with pytest.raises(IntegrityError):
        await db_session.flush()
