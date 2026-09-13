from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AIInteraction(Base):
    __tablename__ = "ai_interactions"
    __table_args__ = (
        CheckConstraint(
            "help_level >= 1 AND help_level <= 6",
            name="ck_ai_interactions_help_level_range",
        ),
        CheckConstraint("input_chars >= 0", name="ck_ai_interactions_input_chars_nonnegative"),
        CheckConstraint(
            "output_chars IS NULL OR output_chars >= 0",
            name="ck_ai_interactions_output_chars_nonnegative",
        ),
        CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_ai_interactions_input_tokens_nonnegative",
        ),
        CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_ai_interactions_output_tokens_nonnegative",
        ),
        CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="ck_ai_interactions_latency_ms_nonnegative",
        ),
        CheckConstraint(
            "operation = 'question_tutor'",
            name="ck_ai_interactions_operation_allowed",
        ),
        CheckConstraint(
            "(success IS NULL AND error_code IS NULL AND latency_ms IS NULL "
            "AND output_chars IS NULL) OR "
            "(success IS TRUE AND error_code IS NULL AND latency_ms IS NOT NULL "
            "AND output_chars IS NOT NULL) OR "
            "(success IS FALSE AND error_code IS NOT NULL AND latency_ms IS NOT NULL)",
            name="ck_ai_interactions_state_consistent",
        ),
        Index("ix_ai_interactions_subject_id", "subject_id"),
        Index("ix_ai_interactions_topic_id", "topic_id"),
        Index("ix_ai_interactions_question_id", "question_id"),
        Index("ix_ai_interactions_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    operation: Mapped[str] = mapped_column(String(50), nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True
    )
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"), nullable=True
    )
    question_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("questions.id", ondelete="SET NULL"), nullable=True
    )
    help_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    input_chars: Mapped[int] = mapped_column(Integer, nullable=False)
    output_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
