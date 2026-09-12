from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Attempt(Base):
    __tablename__ = "attempts"
    __table_args__ = (
        CheckConstraint(
            "hints_used >= 0 AND hints_used <= 3", name="ck_attempts_hints_used_range"
        ),
        CheckConstraint(
            "time_spent_seconds >= 0", name="ck_attempts_time_spent_seconds_nonnegative"
        ),
        Index(
            "ix_attempts_question_id_created_at_id", "question_id", "created_at", "id"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False
    )
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    hints_used: Mapped[int] = mapped_column(Integer, nullable=False)
    solution_seen: Mapped[bool] = mapped_column(Boolean, nullable=False)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
