from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ExamTopic(Base):
    __tablename__ = "exam_topics"
    __table_args__ = (
        CheckConstraint("weight > 0 AND weight <= 1", name="ck_exam_topics_weight_range"),
        Index("ix_exam_topics_topic_id", "topic_id"),
    )

    exam_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exams.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="RESTRICT"), primary_key=True
    )
    weight: Mapped[Decimal] = mapped_column(Numeric(), nullable=False)
