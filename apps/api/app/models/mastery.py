from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Mastery(Base):
    __tablename__ = "mastery"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="ck_mastery_score_range"),
    )

    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="RESTRICT"), primary_key=True
    )
    score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="0.00"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
