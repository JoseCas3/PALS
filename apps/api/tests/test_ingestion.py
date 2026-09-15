from __future__ import annotations

import uuid
from io import BytesIO
from typing import BinaryIO

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_document_extractor, get_document_storage
from app.core.config import Settings
from app.core.errors import ApplicationError
from app.ingestion.chunking import (
    ChunkingError,
    DocumentChunker,
    LexicalTokenCounter,
    ProcessedChunk,
)
from app.ingestion.extraction import (
    DocumentExtractor,
    ExtractedDocument,
    ExtractedPage,
    PypdfDocumentExtractor,
    TextExtractionError,
)
from app.ingestion.normalization import TextNormalizer
from app.ingestion.service import IngestionService
from app.main import app as fastapi_app
from app.models.attempt import Attempt
from app.models.document import Document
from app.models.mastery import Mastery
from app.models.question import Question
from app.storage.documents import DocumentStorage, DocumentStorageError, LocalDocumentStorage
from tests.pdf_factory import make_pdf
from tests.test_attempts import ATTEMPT
from tests.test_documents import upload_document
from tests.test_exam_topics import create_topic
from tests.test_questions import create_question
from tests.test_subjects import create_subject


def page(number: int, text: str) -> ExtractedPage:
    return ExtractedPage(page_number=number, text=text)


def test_pypdf_extractor_preserves_pages_and_one_based_numbering() -> None:
    extracted = PypdfDocumentExtractor().extract(
        BytesIO(
            make_pdf(
                ["First page has deterministic text.", "", "Third page remains distinct."]
            )
        )
    )

    assert extracted == ExtractedDocument(
        pages=(
            page(1, "First page has deterministic text."),
            page(2, ""),
            page(3, "Third page remains distinct."),
        )
    )
    assert all(type(item) is ExtractedPage for item in extracted.pages)


def test_pypdf_extractor_maps_malformed_input_safely() -> None:
    with pytest.raises(TextExtractionError, match="PDF text extraction failed"):
        PypdfDocumentExtractor().extract(BytesIO(b"%PDF-malformed"))


def test_normalization_rules_are_idempotent_and_preserve_meaning() -> None:
    normalizer = TextNormalizer()
    source = "Cafe\u0301\x00\r\n  x\u00b2 + y = z   \r\n\r\n\r\nNext\t line  "
    normalized = normalizer.normalize(source)

    assert normalized == "Caf\u00e9\n x\u00b2 + y = z\n\nNext line"
    assert normalizer.normalize(normalized) == normalized
    assert "x\u00b2 + y = z" in normalized


def test_small_document_is_one_deterministic_chunk_with_consistent_count() -> None:
    pages = (page(1, "Alpha beta gamma.\n\nDelta epsilon."),)
    chunker = DocumentChunker(target_tokens=20, overlap_tokens=3)

    first = chunker.chunk(pages)
    second = chunker.chunk(pages)

    assert first == second
    assert len(first) == 1
    assert first[0].chunk_index == 0
    assert first[0].page_start == first[0].page_end == 1
    assert first[0].token_count == LexicalTokenCounter().count(first[0].text) == 5


def test_chunking_prefers_paragraph_then_sentence_boundaries() -> None:
    paragraph_pages = (page(1, "one two three four\n\nfive six seven eight nine ten"),)
    sentence_pages = (page(1, "one two three. four five six. seven eight nine ten"),)

    paragraph_chunks = DocumentChunker(7, 1).chunk(paragraph_pages)
    sentence_chunks = DocumentChunker(7, 1).chunk(sentence_pages)

    assert paragraph_chunks[0].text == "one two three four"
    assert sentence_chunks[0].text == "one two three. four five six."


def test_chunking_overlap_is_bounded_and_page_provenance_is_correct() -> None:
    pages = (
        page(1, "one two three"),
        page(2, "four five six seven eight nine ten eleven twelve"),
    )
    chunks = DocumentChunker(target_tokens=8, overlap_tokens=2).chunk(pages)

    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 2
    assert chunks[1].page_start == 2
    assert chunks[0].text.split()[-2:] == chunks[1].text.split()[:2]
    assert all(0 < chunk.token_count <= 8 for chunk in chunks)
    assert len({chunk.text for chunk in chunks}) == len(chunks)


def test_chunking_whitespace_fallback_and_pathological_text_terminate() -> None:
    text = " ".join(f"unit{index}" for index in range(1000))
    chunks = DocumentChunker(target_tokens=40, overlap_tokens=5).chunk((page(1, text),))

    assert len(chunks) > 1
    assert chunks[-1].text.endswith("unit999")
    assert all(chunk.text and chunk.token_count <= 40 for chunk in chunks)


@pytest.mark.parametrize(
    ("target", "overlap"),
    [(0, 0), (-1, 0), (10, -1), (10, 10), (10, 11)],
)
def test_invalid_chunk_configuration_is_rejected(target: int, overlap: int) -> None:
    with pytest.raises(ValueError):
        DocumentChunker(target, overlap)


def test_settings_reject_overlap_not_smaller_than_target() -> None:
    with pytest.raises(ValueError, match="overlap"):
        Settings(rag_chunk_target_tokens=10, rag_chunk_overlap_tokens=10)


class StaticExtractor(DocumentExtractor):
    def __init__(self, pages: tuple[ExtractedPage, ...] | None = None) -> None:
        self.pages = pages or (page(1, "Enough deterministic text for successful processing."),)

    def extract(self, source: BinaryIO) -> ExtractedDocument:
        return ExtractedDocument(self.pages)


class FailingExtractor(DocumentExtractor):
    def extract(self, source: BinaryIO) -> ExtractedDocument:
        raise TextExtractionError("private parser detail")


class UnexpectedExtractor(DocumentExtractor):
    def extract(self, source: BinaryIO) -> ExtractedDocument:
        raise RuntimeError("private unexpected detail")


class FailingChunker(DocumentChunker):
    def chunk(self, pages: tuple[ExtractedPage, ...]) -> tuple[ProcessedChunk, ...]:
        raise ChunkingError("private chunk detail")


async def process_document(client: AsyncClient, document_id: object) -> Response:
    return await client.post(f"/api/v1/documents/{document_id}/process")


@pytest.mark.asyncio
async def test_process_uploaded_document_to_ready_without_persisting_derived_text(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    subject = await create_subject(async_client)
    uploaded = await upload_document(
        async_client,
        subject["id"],
        content=make_pdf(["This synthetic PDF has enough deterministic text for processing."]),
    )

    response = await process_document(async_client, uploaded["id"])

    assert response.status_code == 200
    assert response.json()["status"] == "READY"
    assert response.json()["error_code"] is None
    assert "text" not in response.json()
    assert "chunks" not in response.json()
    document = await db_session.get(Document, uuid.UUID(str(uploaded["id"])))
    assert document is not None and document.status == "READY"
    assert "document_chunks" not in document.metadata.tables
    assert not hasattr(document, "text")
    assert not hasattr(document, "chunks")


@pytest.mark.asyncio
async def test_failed_document_can_retry_and_clears_error(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    subject = await create_subject(async_client)
    uploaded = await upload_document(async_client, subject["id"])
    document = await db_session.get(Document, uuid.UUID(str(uploaded["id"])))
    assert document is not None
    document.status = "FAILED"
    document.error_code = "TEXT_EXTRACTION_FAILED"
    await db_session.flush()
    fastapi_app.dependency_overrides[get_document_extractor] = StaticExtractor

    response = await process_document(async_client, uploaded["id"])

    assert response.status_code == 200
    assert response.json()["status"] == "READY"
    assert response.json()["error_code"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("extractor", "expected_code"),
    [
        (FailingExtractor(), "TEXT_EXTRACTION_FAILED"),
        (StaticExtractor((page(1, ""),)), "TEXT_EXTRACTION_INSUFFICIENT"),
        (UnexpectedExtractor(), "PROCESSING_FAILED"),
    ],
)
async def test_processing_failures_persist_safe_error(
    async_client: AsyncClient,
    db_session: AsyncSession,
    extractor: DocumentExtractor,
    expected_code: str,
) -> None:
    subject = await create_subject(async_client)
    uploaded = await upload_document(async_client, subject["id"])
    fastapi_app.dependency_overrides[get_document_extractor] = lambda: extractor

    response = await process_document(async_client, uploaded["id"])

    assert response.status_code in (422, 500)
    assert response.json()["error"]["code"] == expected_code
    assert "private" not in response.text
    document = await db_session.get(Document, uuid.UUID(str(uploaded["id"])))
    assert document is not None
    await db_session.refresh(document)
    assert document.status == "FAILED"
    assert document.error_code == expected_code


@pytest.mark.asyncio
async def test_chunking_failure_persists_safe_error(
    async_client: AsyncClient,
    db_session: AsyncSession,
    document_storage: LocalDocumentStorage,
) -> None:
    subject = await create_subject(async_client)
    uploaded = await upload_document(async_client, subject["id"])
    service = IngestionService(
        db_session,
        document_storage,
        StaticExtractor(),
        TextNormalizer(),
        FailingChunker(10, 1),
    )

    with pytest.raises(ApplicationError) as raised:
        await service.process(uuid.UUID(str(uploaded["id"])))

    assert raised.value.code == "CHUNKING_FAILED"
    document = await db_session.get(Document, uuid.UUID(str(uploaded["id"])))
    assert document is not None and document.error_code == "CHUNKING_FAILED"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_status", "expected_code"),
    [("PROCESSING", "DOCUMENT_ALREADY_PROCESSING"), ("READY", "DOCUMENT_ALREADY_PROCESSED")],
)
async def test_unprocessable_lifecycle_states_are_rejected(
    async_client: AsyncClient,
    db_session: AsyncSession,
    source_status: str,
    expected_code: str,
) -> None:
    subject = await create_subject(async_client)
    uploaded = await upload_document(async_client, subject["id"])
    document = await db_session.get(Document, uuid.UUID(str(uploaded["id"])))
    assert document is not None
    document.status = source_status
    await db_session.flush()

    response = await process_document(async_client, uploaded["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == expected_code


class ReadFailingStorage(DocumentStorage):
    def save(self, storage_key: str, content: bytes) -> None:
        raise NotImplementedError

    def open(self, storage_key: str) -> BinaryIO:
        raise DocumentStorageError("private path")

    def delete(self, storage_key: str) -> None:
        raise NotImplementedError

    def exists(self, storage_key: str) -> bool:
        return True


@pytest.mark.asyncio
async def test_storage_read_failure_is_safe_and_failed(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    subject = await create_subject(async_client)
    uploaded = await upload_document(async_client, subject["id"])
    fastapi_app.dependency_overrides[get_document_storage] = ReadFailingStorage

    response = await process_document(async_client, uploaded["id"])

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "PROCESSING_FAILED"
    assert "private" not in response.text
    document = await db_session.get(Document, uuid.UUID(str(uploaded["id"])))
    assert document is not None
    await db_session.refresh(document)
    assert document.status == "FAILED"


@pytest.mark.asyncio
async def test_processing_does_not_touch_academic_evidence(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    subject = await create_subject(async_client)
    topic = await create_topic(async_client, subject["id"], "Limits")
    question = await create_question(async_client, topic["id"])
    attempt = await async_client.post(f"/api/v1/questions/{question['id']}/attempts", json=ATTEMPT)
    assert attempt.status_code == 201
    mastery_before = await db_session.get(Mastery, uuid.UUID(str(topic["id"])))
    assert mastery_before is not None
    score_before = mastery_before.score
    uploaded = await upload_document(async_client, subject["id"])
    fastapi_app.dependency_overrides[get_document_extractor] = StaticExtractor

    response = await process_document(async_client, uploaded["id"])

    assert response.status_code == 200
    assert await db_session.scalar(select(func.count()).select_from(Question)) == 1
    assert await db_session.scalar(select(func.count()).select_from(Attempt)) == 1
    await db_session.refresh(mastery_before)
    assert mastery_before.score == score_before


@pytest.mark.asyncio
async def test_no_transaction_is_open_during_extraction(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    subject = await create_subject(async_client)
    uploaded = await upload_document(async_client, subject["id"])

    class TransactionCheckingExtractor(StaticExtractor):
        def extract(self, source: BinaryIO) -> ExtractedDocument:
            assert not db_session.in_transaction()
            return super().extract(source)

    fastapi_app.dependency_overrides[get_document_extractor] = TransactionCheckingExtractor
    response = await process_document(async_client, uploaded["id"])
    assert response.status_code == 200
