"""Expand AI interactions for Sprint 5 Question generation.

Revision ID: 20260912_04
Revises: 20260912_03
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260912_04"
down_revision: str | Sequence[str] | None = "20260912_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_ai_interactions_help_level_range", "ai_interactions", type_="check"
    )
    op.drop_constraint(
        "ck_ai_interactions_operation_allowed", "ai_interactions", type_="check"
    )
    op.alter_column(
        "ai_interactions", "help_level", existing_type=sa.SmallInteger(), nullable=True
    )
    op.create_check_constraint(
        "ck_ai_interactions_operation_help_consistent",
        "ai_interactions",
        "(operation = 'question_tutor' AND help_level IS NOT NULL "
        "AND help_level >= 1 AND help_level <= 6) OR "
        "(operation = 'question_generation' AND help_level IS NULL)",
    )


def downgrade() -> None:
    # Sprint 5 generation rows cannot satisfy Sprint 4's Tutor-only schema.
    op.execute("DELETE FROM ai_interactions WHERE operation = 'question_generation'")
    op.drop_constraint(
        "ck_ai_interactions_operation_help_consistent", "ai_interactions", type_="check"
    )
    op.alter_column(
        "ai_interactions", "help_level", existing_type=sa.SmallInteger(), nullable=False
    )
    op.create_check_constraint(
        "ck_ai_interactions_operation_allowed",
        "ai_interactions",
        "operation = 'question_tutor'",
    )
    op.create_check_constraint(
        "ck_ai_interactions_help_level_range",
        "ai_interactions",
        "help_level >= 1 AND help_level <= 6",
    )
