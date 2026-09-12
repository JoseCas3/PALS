"""Create Sprint 1 domain core.

Revision ID: 20260911_01
Revises:
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260911_01"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "subjects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_subjects_name_not_blank"),
        sa.PrimaryKeyConstraint("id", name="pk_subjects"),
    )
    op.create_table(
        "topics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_topics_name_not_blank"),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["subjects.id"], name="fk_topics_subject_id", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_topics"),
    )
    op.create_index("ix_topics_subject_id", "topics", ["subject_id"])
    op.create_table(
        "exams",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("exam_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_exams_name_not_blank"),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["subjects.id"], name="fk_exams_subject_id", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_exams"),
    )
    op.create_index(
        "ix_exams_subject_id_exam_date", "exams", ["subject_id", "exam_date"]
    )
    op.create_table(
        "exam_topics",
        sa.Column("exam_id", sa.Uuid(), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column("weight", sa.Numeric(), nullable=False),
        sa.CheckConstraint("weight > 0 AND weight <= 1", name="ck_exam_topics_weight_range"),
        sa.ForeignKeyConstraint(
            ["exam_id"], ["exams.id"], name="fk_exam_topics_exam_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"], ["topics.id"], name="fk_exam_topics_topic_id", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("exam_id", "topic_id", name="pk_exam_topics"),
    )
    op.create_index("ix_exam_topics_topic_id", "exam_topics", ["topic_id"])


def downgrade() -> None:
    op.drop_index("ix_exam_topics_topic_id", table_name="exam_topics")
    op.drop_table("exam_topics")
    op.drop_index("ix_exams_subject_id_exam_date", table_name="exams")
    op.drop_table("exams")
    op.drop_index("ix_topics_subject_id", table_name="topics")
    op.drop_table("topics")
    op.drop_table("subjects")
