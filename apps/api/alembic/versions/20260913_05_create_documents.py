"""Create R1 document domain.

Revision ID: 20260913_05
Revises: 20260912_04
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260913_05"
down_revision: str | Sequence[str] | None = "20260912_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="UPLOADED", nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("processing_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("embedding_provider", sa.String(length=50), nullable=True),
        sa.Column("embedding_model", sa.String(length=100), nullable=True),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("size_bytes > 0", name="ck_documents_size_bytes_positive"),
        sa.CheckConstraint(
            "checksum_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_documents_checksum_sha256_format",
        ),
        sa.CheckConstraint(
            "status IN ('UPLOADED', 'PROCESSING', 'READY', 'FAILED')",
            name="ck_documents_status_allowed",
        ),
        sa.CheckConstraint(
            "processing_version >= 1",
            name="ck_documents_processing_version_positive",
        ),
        sa.CheckConstraint(
            "embedding_dimensions IS NULL OR embedding_dimensions > 0",
            name="ck_documents_embedding_dimensions_positive",
        ),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_documents_storage_key"),
        sa.UniqueConstraint("subject_id", "checksum_sha256", name="uq_documents_subject_checksum"),
    )
    op.create_index(
        "ix_documents_subject_id_created_at_id",
        "documents",
        ["subject_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_documents_subject_id_created_at_id", table_name="documents")
    op.drop_table("documents")
