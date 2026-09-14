import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentStatus


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject_id: uuid.UUID
    original_filename: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    status: DocumentStatus
    error_code: str | None
    processing_version: int
    embedding_provider: str | None
    embedding_model: str | None
    embedding_dimensions: int | None
    created_at: datetime
    updated_at: datetime
