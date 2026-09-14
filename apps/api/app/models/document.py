from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DocumentStatus(StrEnum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="ck_documents_size_bytes_positive"),
        CheckConstraint(
            "checksum_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_documents_checksum_sha256_format",
        ),
        CheckConstraint(
            "status IN ('UPLOADED', 'PROCESSING', 'READY', 'FAILED')",
            name="ck_documents_status_allowed",
        ),
        CheckConstraint(
            "processing_version >= 1",
            name="ck_documents_processing_version_positive",
        ),
        CheckConstraint(
            "embedding_dimensions IS NULL OR embedding_dimensions > 0",
            name="ck_documents_embedding_dimensions_positive",
        ),
        UniqueConstraint(
            "subject_id", "checksum_sha256", name="uq_documents_subject_checksum"
        ),
        Index("ix_documents_subject_id_created_at_id", "subject_id", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=DocumentStatus.UPLOADED.value
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    processing_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    embedding_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedding_dimensions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
