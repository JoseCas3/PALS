import uuid
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO, cast

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_document_max_size_bytes, get_document_storage
from app.main import app as fastapi_app
from app.models.attempt import Attempt
from app.models.document import Document
from app.models.mastery import Mastery
from app.repositories.documents import DocumentRepository
from app.storage.documents import DocumentStorage, DocumentStorageError, LocalDocumentStorage
from tests.test_attempts import ATTEMPT
from tests.test_exam_topics import create_topic
from tests.test_questions import create_question
from tests.test_subjects import create_subject

PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n"
OTHER_PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog /Version/1.7>>endobj\n%%EOF\n"


async def upload_document(
    client: AsyncClient,
    subject_id: object,
    *,
    filename: str = "notes.pdf",
    content: bytes = PDF,
    mime_type: str = "application/pdf",
) -> dict[str, object]:
    response = await client.post(
        f"/api/v1/subjects/{subject_id}/documents",
        files={"file": (filename, content, mime_type)},
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, object], response.json())


@pytest.mark.asyncio
async def test_valid_upload_persists_metadata_and_opaque_file(
    async_client: AsyncClient,
    db_session: AsyncSession,
    document_storage: LocalDocumentStorage,
) -> None:
    subject = await create_subject(async_client)
    response = await upload_document(async_client, subject["id"])

    assert response["status"] == "UPLOADED"
    assert response["original_filename"] == "notes.pdf"
    assert response["mime_type"] == "application/pdf"
    assert response["size_bytes"] == len(PDF)
    assert response["checksum_sha256"] == sha256(PDF).hexdigest()
    assert response["processing_version"] == 1
    assert response["error_code"] is None
    assert "storage_key" not in response
    assert str(document_storage.root) not in str(response)

    document = await db_session.get(Document, uuid.UUID(str(response["id"])))
    assert document is not None
    assert document.storage_key == f"{str(document.id)[:2]}/{document.id}.pdf"
    assert not Path(document.storage_key).is_absolute()
    assert document.embedding_provider is None
    assert document.embedding_model is None
    assert document.embedding_dimensions is None
    assert document_storage.exists(document.storage_key)


@pytest.mark.asyncio
async def test_missing_upload_returns_safe_validation_error(
    async_client: AsyncClient,
    document_storage: LocalDocumentStorage,
) -> None:
    subject = await create_subject(async_client)

    response = await async_client.post(
        f"/api/v1/subjects/{subject['id']}/documents"
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert list(document_storage.root.rglob("*.pdf")) == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "content", "mime_type", "status_code", "error_code"),
    [
        ("notes.txt", PDF, "application/pdf", 415, "UNSUPPORTED_FILE_TYPE"),
        ("notes.pdf", PDF, "text/plain", 415, "UNSUPPORTED_FILE_TYPE"),
        ("notes.pdf", b"not a PDF", "application/pdf", 422, "INVALID_PDF"),
        ("notes.pdf", b"", "application/pdf", 422, "INVALID_PDF"),
    ],
)
async def test_upload_validation_rejects_invalid_files_without_storage(
    async_client: AsyncClient,
    document_storage: LocalDocumentStorage,
    filename: str,
    content: bytes,
    mime_type: str,
    status_code: int,
    error_code: str,
) -> None:
    subject = await create_subject(async_client)
    response = await async_client.post(
        f"/api/v1/subjects/{subject['id']}/documents",
        files={"file": (filename, content, mime_type)},
    )

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == error_code
    assert list(document_storage.root.rglob("*.pdf")) == []


@pytest.mark.asyncio
async def test_oversized_upload_uses_configured_limit(
    async_client: AsyncClient, document_storage: LocalDocumentStorage
) -> None:
    subject = await create_subject(async_client)
    fastapi_app.dependency_overrides[get_document_max_size_bytes] = lambda: 8
    try:
        response = await async_client.post(
            f"/api/v1/subjects/{subject['id']}/documents",
            files={"file": ("large.pdf", PDF, "application/pdf")},
        )
    finally:
        fastapi_app.dependency_overrides.pop(get_document_max_size_bytes, None)

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
    assert list(document_storage.root.rglob("*.pdf")) == []


@pytest.mark.asyncio
async def test_duplicate_semantics_and_no_orphan_file(
    async_client: AsyncClient,
    db_session: AsyncSession,
    document_storage: LocalDocumentStorage,
) -> None:
    first_subject = await create_subject(async_client, "Calculus")
    second_subject = await create_subject(async_client, "Physics")
    first = await upload_document(async_client, first_subject["id"])

    duplicate = await async_client.post(
        f"/api/v1/subjects/{first_subject['id']}/documents",
        files={"file": ("renamed.pdf", PDF, "application/pdf")},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DOCUMENT_ALREADY_EXISTS"
    assert len(list(document_storage.root.rglob("*.pdf"))) == 1

    different_content = await upload_document(
        async_client, first_subject["id"], content=OTHER_PDF
    )
    same_content_other_subject = await upload_document(
        async_client, second_subject["id"], content=PDF
    )
    assert different_content["id"] != first["id"]
    assert same_content_other_subject["id"] != first["id"]
    assert await db_session.scalar(select(func.count()).select_from(Document)) == 3


@pytest.mark.asyncio
async def test_list_get_scope_and_not_found(async_client: AsyncClient) -> None:
    first_subject = await create_subject(async_client, "Calculus")
    second_subject = await create_subject(async_client, "Physics")
    first = await upload_document(async_client, first_subject["id"])
    await upload_document(async_client, first_subject["id"], content=OTHER_PDF)
    await upload_document(async_client, second_subject["id"], content=PDF)

    listed = await async_client.get(f"/api/v1/subjects/{first_subject['id']}/documents")
    assert listed.status_code == 200
    assert len(listed.json()) == 2
    assert {item["subject_id"] for item in listed.json()} == {first_subject["id"]}

    fetched = await async_client.get(f"/api/v1/documents/{first['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == first["id"]

    missing = await async_client.get(f"/api/v1/documents/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_delete_removes_row_and_file_without_affecting_evidence(
    async_client: AsyncClient,
    db_session: AsyncSession,
    document_storage: LocalDocumentStorage,
) -> None:
    subject = await create_subject(async_client)
    topic = await create_topic(async_client, subject["id"], "Limits")
    question = await create_question(async_client, topic["id"])
    attempt = await async_client.post(
        f"/api/v1/questions/{question['id']}/attempts", json=ATTEMPT
    )
    assert attempt.status_code == 201
    uploaded = await upload_document(async_client, subject["id"])
    document = await db_session.get(Document, uuid.UUID(str(uploaded["id"])))
    assert document is not None
    storage_key = document.storage_key

    deleted = await async_client.delete(f"/api/v1/documents/{uploaded['id']}")
    assert deleted.status_code == 204
    assert await db_session.get(Document, document.id) is None
    assert not document_storage.exists(storage_key)
    assert await db_session.scalar(select(func.count()).select_from(Attempt)) == 1
    mastery = await db_session.get(Mastery, uuid.UUID(str(topic["id"])))
    assert mastery is not None
    assert str(mastery.score) == "6.40"


@pytest.mark.asyncio
async def test_subject_delete_cascades_metadata_and_cleans_file(
    async_client: AsyncClient,
    db_session: AsyncSession,
    document_storage: LocalDocumentStorage,
) -> None:
    subject = await create_subject(async_client)
    uploaded = await upload_document(async_client, subject["id"])
    document = await db_session.get(Document, uuid.UUID(str(uploaded["id"])))
    assert document is not None
    storage_key = document.storage_key

    response = await async_client.delete(f"/api/v1/subjects/{subject['id']}")

    assert response.status_code == 204
    assert await db_session.scalar(
        select(func.count()).select_from(Document).where(Document.id == document.id)
    ) == 0
    assert not document_storage.exists(storage_key)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename",
    ["../../evil.pdf", "..\\..\\evil.pdf", "C:\\Windows\\evil.pdf", "/var/tmp/evil.pdf"],
)
async def test_hostile_filename_cannot_control_storage_path(
    async_client: AsyncClient,
    db_session: AsyncSession,
    document_storage: LocalDocumentStorage,
    filename: str,
) -> None:
    subject = await create_subject(async_client)
    uploaded = await upload_document(async_client, subject["id"], filename=filename)
    document = await db_session.get(Document, uuid.UUID(str(uploaded["id"])))
    assert document is not None
    assert document.original_filename.endswith("evil.pdf")
    assert document.storage_key == f"{str(document.id)[:2]}/{document.id}.pdf"
    assert (document_storage.root / document.storage_key).is_file()


@pytest.mark.asyncio
async def test_database_failure_after_storage_cleans_file_and_hides_details(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    document_storage: LocalDocumentStorage,
) -> None:
    subject = await create_subject(async_client)

    async def fail_create(*_: object, **__: object) -> Document:
        raise DBAPIError(
            "INSERT INTO documents (original_filename)",
            ("private.pdf",),
            RuntimeError("private storage detail"),
            False,
        )

    monkeypatch.setattr(DocumentRepository, "create", fail_create)
    response = await async_client.post(
        f"/api/v1/subjects/{subject['id']}/documents",
        files={"file": ("private.pdf", PDF, "application/pdf")},
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "DATABASE_ERROR"
    assert "private.pdf" not in response.text
    assert str(document_storage.root) not in response.text
    assert list(document_storage.root.rglob("*.pdf")) == []


class FailingStorage(DocumentStorage):
    def save(self, storage_key: str, content: bytes) -> None:
        raise DocumentStorageError("private absolute path")

    def open(self, storage_key: str) -> BinaryIO:
        raise NotImplementedError

    def delete(self, storage_key: str) -> None:
        raise NotImplementedError

    def exists(self, storage_key: str) -> bool:
        return False


@pytest.mark.asyncio
async def test_storage_failure_creates_no_row_and_returns_safe_error(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    subject = await create_subject(async_client)
    fastapi_app.dependency_overrides[get_document_storage] = FailingStorage
    try:
        response = await async_client.post(
            f"/api/v1/subjects/{subject['id']}/documents",
            files={"file": ("notes.pdf", PDF, "application/pdf")},
        )
    finally:
        fastapi_app.dependency_overrides.pop(get_document_storage, None)

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "DOCUMENT_STORAGE_ERROR"
    assert "private" not in response.text
    assert await db_session.scalar(select(func.count()).select_from(Document)) == 0
