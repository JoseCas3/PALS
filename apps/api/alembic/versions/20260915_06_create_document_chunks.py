"""Create the pgvector-backed R3 document chunk substrate.

Revision ID: 20260915_06
Revises: 20260913_05
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import VECTOR

from alembic import op

revision: str = "20260915_06"
down_revision: str | Sequence[str] | None = "20260913_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", VECTOR(1536), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("chunk_index >= 0", name="ck_document_chunks_index_nonnegative"),
        sa.CheckConstraint("page_start >= 1", name="ck_document_chunks_page_start_positive"),
        sa.CheckConstraint("page_end >= page_start", name="ck_document_chunks_page_order"),
        sa.CheckConstraint("token_count > 0", name="ck_document_chunks_token_count_positive"),
        sa.CheckConstraint(
            "length(btrim(text)) > 0", name="ck_document_chunks_text_nonempty"
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id", "chunk_index", name="uq_document_chunks_document_index"
        ),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    # Deliberately preserve the shared vector extension and any unrelated vector data.
