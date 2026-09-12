"""Create Sprint 2 practice evidence and mastery.

Revision ID: 20260911_02
Revises: 20260911_01
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260911_02"
down_revision: str | Sequence[str] | None = "20260911_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("answer_reference", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.String(length=10), server_default="medium", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "length(btrim(answer_reference)) > 0",
            name="ck_questions_answer_reference_not_blank",
        ),
        sa.CheckConstraint(
            "difficulty IN ('easy', 'medium', 'hard')",
            name="ck_questions_difficulty_allowed",
        ),
        sa.CheckConstraint(
            "length(btrim(prompt)) > 0", name="ck_questions_prompt_not_blank"
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"], ["topics.id"], name="fk_questions_topic_id", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_questions"),
    )
    op.create_index(
        "ix_questions_topic_id_created_at_id",
        "questions",
        ["topic_id", "created_at", "id"],
    )
    op.create_table(
        "mastery",
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Numeric(precision=5, scale=2), server_default="0.00", nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_mastery_score_range"),
        sa.ForeignKeyConstraint(
            ["topic_id"], ["topics.id"], name="fk_mastery_topic_id", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("topic_id", name="pk_mastery"),
    )
    op.create_table(
        "attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=False),
        sa.Column("hints_used", sa.Integer(), nullable=False),
        sa.Column("solution_seen", sa.Boolean(), nullable=False),
        sa.Column("time_spent_seconds", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "hints_used >= 0 AND hints_used <= 3", name="ck_attempts_hints_used_range"
        ),
        sa.CheckConstraint(
            "time_spent_seconds >= 0", name="ck_attempts_time_spent_seconds_nonnegative"
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name="fk_attempts_question_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_attempts"),
    )
    op.create_index(
        "ix_attempts_question_id_created_at_id",
        "attempts",
        ["question_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_attempts_question_id_created_at_id", table_name="attempts")
    op.drop_table("attempts")
    op.drop_table("mastery")
    op.drop_index("ix_questions_topic_id_created_at_id", table_name="questions")
    op.drop_table("questions")
