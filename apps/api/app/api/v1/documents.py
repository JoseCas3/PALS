import uuid
from typing import Annotated

from fastapi import APIRouter, File, Response, UploadFile, status

from app.api.dependencies import (
    DocumentExtractorDependency,
    DocumentMaxSizeDependency,
    DocumentStorageDependency,
    Session,
)
from app.core.config import get_settings
from app.ingestion.chunking import DocumentChunker
from app.ingestion.normalization import TextNormalizer
from app.ingestion.service import IngestionService
from app.schemas.document import DocumentResponse
from app.services.documents import DocumentService

router = APIRouter(tags=["documents"])


@router.post("/documents/{document_id}/process", response_model=DocumentResponse)
async def process_document(
    document_id: uuid.UUID,
    session: Session,
    storage: DocumentStorageDependency,
    extractor: DocumentExtractorDependency,
) -> DocumentResponse:
    settings = get_settings()
    document = await IngestionService(
        session,
        storage,
        extractor,
        TextNormalizer(),
        DocumentChunker(
            settings.rag_chunk_target_tokens,
            settings.rag_chunk_overlap_tokens,
        ),
    ).process(document_id)
    return DocumentResponse.model_validate(document)


@router.post(
    "/subjects/{subject_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    subject_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    session: Session,
    storage: DocumentStorageDependency,
    max_size_bytes: DocumentMaxSizeDependency,
) -> DocumentResponse:
    content = await file.read(max_size_bytes + 1)
    document = await DocumentService(session, storage).upload(
        subject_id,
        original_filename=file.filename,
        mime_type=file.content_type,
        content=content,
        max_size_bytes=max_size_bytes,
    )
    return DocumentResponse.model_validate(document)


@router.get("/subjects/{subject_id}/documents", response_model=list[DocumentResponse])
async def list_documents(
    subject_id: uuid.UUID,
    session: Session,
    storage: DocumentStorageDependency,
) -> list[DocumentResponse]:
    documents = await DocumentService(session, storage).list_for_subject(subject_id)
    return [DocumentResponse.model_validate(document) for document in documents]


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    session: Session,
    storage: DocumentStorageDependency,
) -> DocumentResponse:
    document = await DocumentService(session, storage).get(document_id)
    return DocumentResponse.model_validate(document)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    session: Session,
    storage: DocumentStorageDependency,
) -> Response:
    await DocumentService(session, storage).delete(document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
