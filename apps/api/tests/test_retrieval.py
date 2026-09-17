from __future__ import annotations

import asyncio
import uuid
from collections.abc import Sequence

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.embeddings.contracts import EmbeddingError, ProviderEmbedding
from app.embeddings.service import EmbeddingService
from app.models.ai_interaction import AIInteraction
from app.models.attempt import Attempt
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.mastery import Mastery
from app.retrieval.service import RetrievalService
from tests.test_documents import OTHER_PDF, upload_document
from tests.test_subjects import create_subject


def vector(axis: int = 0, value: float = 1.0) -> tuple[float, ...]:
    result = [0.0] * 1536
    result[axis] = value
    return tuple(result)


class QueryProvider:
    provider_name = "fake"
    model_name = "fake-deterministic-v1"
    dimensions = 1536

    def __init__(self, query_vector: tuple[float, ...] | None = None) -> None:
        self.query_vector = query_vector or vector()
        self.calls: list[tuple[str, ...]] = []

    async def embed(self, texts: Sequence[str]) -> Sequence[ProviderEmbedding]:
        self.calls.append(tuple(texts))
        return [
            ProviderEmbedding(index=index, vector=self.query_vector)
            for index, _ in enumerate(texts)
        ]


def retrieval_service(
    session: AsyncSession,
    provider: QueryProvider | None = None,
    *,
    threshold: float = 0.0,
    default_limit: int = 8,
) -> RetrievalService:
    provider = provider or QueryProvider()
    return RetrievalService(
        session,
        EmbeddingService(provider, batch_size=64, dimensions=1536),
        default_limit=default_limit,
        max_limit=50,
        min_relevance=threshold,
    )


async def ready_document(
    client: AsyncClient,
    session: AsyncSession,
    subject_id: object,
    *,
    filename: str,
    content: bytes,
    provider: str | None = "fake",
    model: str | None = "fake-deterministic-v1",
    dimensions: int | None = 1536,
    status: str = "READY",
) -> Document:
    uploaded = await upload_document(client, subject_id, filename=filename, content=content)
    document = await session.get(Document, uuid.UUID(str(uploaded["id"])))
    assert document is not None
    document.status = status
    document.embedding_provider = provider
    document.embedding_model = model
    document.embedding_dimensions = dimensions
    await session.flush()
    return document


def add_chunk(
    session: AsyncSession,
    document: Document,
    *,
    index: int,
    text: str,
    embedding: tuple[float, ...],
    page_start: int = 1,
    page_end: int | None = None,
) -> DocumentChunk:
    chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=index,
        text=text,
        page_start=page_start,
        page_end=page_start if page_end is None else page_end,
        token_count=max(1, len(text.split())),
        embedding=list(embedding),
    )
    session.add(chunk)
    return chunk


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["", "  \t\r\n  "])
async def test_empty_query_is_rejected_before_embedding(
    db_session: AsyncSession, query: str
) -> None:
    provider = QueryProvider()
    with pytest.raises(ApplicationError) as raised:
        await retrieval_service(db_session, provider).retrieve(uuid.uuid4(), query)
    assert raised.value.code == "VALIDATION_ERROR"
    assert provider.calls == []


@pytest.mark.asyncio
async def test_unknown_subject_follows_subject_not_found_convention(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(ApplicationError) as raised:
        await retrieval_service(db_session).retrieve(uuid.uuid4(), "query")
    assert raised.value.code == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_empty_compatible_corpus_is_normal_and_query_is_prepared(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    subject = await create_subject(async_client)
    provider = QueryProvider()
    result = await retrieval_service(db_session, provider).retrieve(
        uuid.UUID(str(subject["id"])), "  vector\n query  "
    )
    assert result.chunks == [] and result.sufficient is False
    assert provider.calls == [("vector query",)]


@pytest.mark.asyncio
async def test_query_embedding_wait_holds_no_prerequisite_database_transaction(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    subject = await create_subject(async_client)

    class GatedQueryProvider(QueryProvider):
        def __init__(self) -> None:
            super().__init__()
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def embed(self, texts: Sequence[str]) -> Sequence[ProviderEmbedding]:
            self.started.set()
            await self.release.wait()
            return await super().embed(texts)

    provider = GatedQueryProvider()
    retrieval = asyncio.create_task(
        retrieval_service(db_session, provider).retrieve(
            uuid.UUID(str(subject["id"])), "transaction boundary"
        )
    )
    try:
        await asyncio.wait_for(provider.started.wait(), timeout=5)
        assert not db_session.in_transaction()
    finally:
        provider.release.set()

    result = await asyncio.wait_for(retrieval, timeout=5)
    assert result.chunks == [] and result.sufficient is False


@pytest.mark.asyncio
async def test_query_embedding_failure_is_sanitized(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    subject = await create_subject(async_client)

    class FailingQueryProvider(QueryProvider):
        async def embed(self, texts: Sequence[str]) -> Sequence[ProviderEmbedding]:
            raise RuntimeError(f"provider payload for {texts[0]}")

    with pytest.raises(EmbeddingError) as raised:
        await retrieval_service(db_session, FailingQueryProvider()).retrieve(
            uuid.UUID(str(subject["id"])), "private query text"
        )
    assert str(raised.value) == "Embedding generation failed"
    assert "private query text" not in str(raised.value)


@pytest.mark.asyncio
async def test_subject_ready_profile_filters_and_exact_cosine_ordering(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    subject_a = await create_subject(async_client, "A")
    subject_b = await create_subject(async_client, "B")
    eligible_one = await ready_document(
        async_client, db_session, subject_a["id"], filename="one.pdf", content=b"%PDF-one"
    )
    eligible_two = await ready_document(
        async_client, db_session, subject_a["id"], filename="two.pdf", content=b"%PDF-two"
    )
    other_subject = await ready_document(
        async_client, db_session, subject_b["id"], filename="other.pdf", content=b"%PDF-other"
    )
    add_chunk(
        db_session,
        eligible_one,
        index=0,
        text="best",
        embedding=vector(0, 1.0),
        page_start=2,
        page_end=3,
    )
    two_axis = tuple(a + b for a, b in zip(vector(0), vector(1), strict=True))
    add_chunk(
        db_session, eligible_two, index=0, text="second", embedding=two_axis, page_start=4
    )
    add_chunk(
        db_session,
        other_subject,
        index=0,
        text="global best excluded",
        embedding=vector(0, 1.0),
    )
    eligible_one_id = eligible_one.id
    await db_session.commit()

    result = await retrieval_service(db_session, threshold=-1.0).retrieve(
        uuid.UUID(str(subject_a["id"])), "query"
    )

    assert [chunk.text for chunk in result.chunks] == ["best", "second"]
    assert result.sufficient is True
    assert result.chunks[0].document_id == eligible_one_id
    assert result.chunks[0].document_filename == "one.pdf"
    assert (result.chunks[0].page_start, result.chunks[0].page_end) == (2, 3)
    assert result.chunks[0].relevance_score == pytest.approx(1.0)
    assert not hasattr(result.chunks[0], "embedding")


@pytest.mark.asyncio
async def test_lifecycle_and_full_embedding_profile_are_enforced(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    subject = await create_subject(async_client)
    cases = [
        ("UPLOADED", "fake", "fake-deterministic-v1", 1536),
        ("PROCESSING", "fake", "fake-deterministic-v1", 1536),
        ("FAILED", "fake", "fake-deterministic-v1", 1536),
        ("READY", "other", "fake-deterministic-v1", 1536),
        ("READY", "fake", "other-model", 1536),
        ("READY", "fake", "fake-deterministic-v1", 768),
        ("READY", None, None, None),
    ]
    for index, (status, provider, model, dimensions) in enumerate(cases):
        document = await ready_document(
            async_client,
            db_session,
            subject["id"],
            filename=f"excluded-{index}.pdf",
            content=f"%PDF-excluded-{index}".encode(),
            status=status,
            provider=provider,
            model=model,
            dimensions=dimensions,
        )
        add_chunk(db_session, document, index=0, text=f"excluded {index}", embedding=vector())
    included = await ready_document(
        async_client,
        db_session,
        subject["id"],
        filename="included.pdf",
        content=b"%PDF-included",
    )
    add_chunk(db_session, included, index=0, text="included", embedding=vector())
    await ready_document(
        async_client,
        db_session,
        subject["id"],
        filename="legacy-no-chunks.pdf",
        content=b"%PDF-legacy",
        provider=None,
        model=None,
        dimensions=None,
    )
    await db_session.flush()

    result = await retrieval_service(db_session).retrieve(
        uuid.UUID(str(subject["id"])), "query"
    )
    assert [chunk.text for chunk in result.chunks] == ["included"]


@pytest.mark.asyncio
async def test_threshold_boundary_limit_deduplication_and_stable_ties(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    subject = await create_subject(async_client)
    document = await ready_document(
        async_client, db_session, subject["id"], filename="ranked.pdf", content=b"%PDF-ranked"
    )
    first = add_chunk(db_session, document, index=0, text="Repeated text", embedding=vector())
    add_chunk(db_session, document, index=1, text=" repeated   TEXT ", embedding=vector())
    second = add_chunk(db_session, document, index=2, text="stable second", embedding=vector())
    add_chunk(db_session, document, index=3, text="below", embedding=vector(0, -1.0))
    await db_session.flush()
    first_id = first.id
    second_id = second.id
    await db_session.commit()

    result = await retrieval_service(db_session, threshold=1.0, default_limit=2).retrieve(
        uuid.UUID(str(subject["id"])), "query", limit=2
    )
    assert [chunk.chunk_id for chunk in result.chunks] == [first_id, second_id]
    assert all(chunk.relevance_score == pytest.approx(1.0) for chunk in result.chunks)

    filtered = await retrieval_service(db_session, threshold=0.0).retrieve(
        uuid.UUID(str(subject["id"])), "query", limit=1
    )
    assert len(filtered.chunks) == 1
    all_filtered = await retrieval_service(db_session, threshold=0.1).retrieve(
        uuid.UUID(str(subject["id"])), "query", limit=4
    )
    assert "below" not in [chunk.text for chunk in all_filtered.chunks]


@pytest.mark.asyncio
async def test_all_candidates_below_threshold_is_insufficient_and_evidence_neutral(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    subject = await create_subject(async_client)
    document = await ready_document(
        async_client, db_session, subject["id"], filename="low.pdf", content=OTHER_PDF
    )
    add_chunk(db_session, document, index=0, text="low", embedding=vector(0, -1.0))
    await db_session.commit()
    before = (
        await db_session.scalar(select(func.count()).select_from(Attempt)),
        await db_session.scalar(select(func.count()).select_from(Mastery)),
        await db_session.scalar(select(func.count()).select_from(AIInteraction)),
    )

    result = await retrieval_service(db_session, threshold=0.0).retrieve(
        uuid.UUID(str(subject["id"])), "private query"
    )
    after = (
        await db_session.scalar(select(func.count()).select_from(Attempt)),
        await db_session.scalar(select(func.count()).select_from(Mastery)),
        await db_session.scalar(select(func.count()).select_from(AIInteraction)),
    )
    assert result.chunks == [] and result.sufficient is False
    assert after == before


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [0, 51])
async def test_limit_is_bounded(
    async_client: AsyncClient, db_session: AsyncSession, limit: int
) -> None:
    subject = await create_subject(async_client)
    with pytest.raises(ApplicationError) as raised:
        await retrieval_service(db_session).retrieve(
            uuid.UUID(str(subject["id"])), "query", limit=limit
        )
    assert raised.value.code == "VALIDATION_ERROR"
