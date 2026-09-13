"""Create Sprint 4 AI interaction observability.

Revision ID: 20260912_03
Revises: 20260911_02
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260912_03"
down_revision: str | Sequence[str] | None = "20260911_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_interactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("operation", sa.String(length=50), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=True),
        sa.Column("topic_id", sa.Uuid(), nullable=True),
        sa.Column("question_id", sa.Uuid(), nullable=True),
        sa.Column("help_level", sa.SmallInteger(), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=False),
        sa.Column("input_chars", sa.Integer(), nullable=False),
        sa.Column("output_chars", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("provider_request_id", sa.String(length=255), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "help_level >= 1 AND help_level <= 6",
            name="ck_ai_interactions_help_level_range",
        ),
        sa.CheckConstraint(
            "input_chars >= 0", name="ck_ai_interactions_input_chars_nonnegative"
        ),
        sa.CheckConstraint(
            "output_chars IS NULL OR output_chars >= 0",
            name="ck_ai_interactions_output_chars_nonnegative",
        ),
        sa.CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_ai_interactions_input_tokens_nonnegative",
        ),
        sa.CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_ai_interactions_output_tokens_nonnegative",
        ),
        sa.CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="ck_ai_interactions_latency_ms_nonnegative",
        ),
        sa.CheckConstraint(
            "operation = 'question_tutor'",
            name="ck_ai_interactions_operation_allowed",
        ),
        sa.CheckConstraint(
            "(success IS NULL AND error_code IS NULL AND latency_ms IS NULL "
            "AND output_chars IS NULL) OR "
            "(success IS TRUE AND error_code IS NULL AND latency_ms IS NOT NULL "
            "AND output_chars IS NOT NULL) OR "
            "(success IS FALSE AND error_code IS NOT NULL AND latency_ms IS NOT NULL)",
            name="ck_ai_interactions_state_consistent",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name="fk_ai_interactions_subject_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topics.id"],
            name="fk_ai_interactions_topic_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name="fk_ai_interactions_question_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_interactions"),
    )
    op.create_index("ix_ai_interactions_subject_id", "ai_interactions", ["subject_id"])
    op.create_index("ix_ai_interactions_topic_id", "ai_interactions", ["topic_id"])
    op.create_index("ix_ai_interactions_question_id", "ai_interactions", ["question_id"])
    op.create_index("ix_ai_interactions_created_at", "ai_interactions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_interactions_created_at", table_name="ai_interactions")
    op.drop_index("ix_ai_interactions_question_id", table_name="ai_interactions")
    op.drop_index("ix_ai_interactions_topic_id", table_name="ai_interactions")
    op.drop_index("ix_ai_interactions_subject_id", table_name="ai_interactions")
    op.drop_table("ai_interactions")
