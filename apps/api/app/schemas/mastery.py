from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


def serialize_score(score: Decimal) -> str:
    return format(score, ".2f")


class MasteryResponse(BaseModel):
    topic_id: uuid.UUID
    score: str
    updated_at: datetime | None

    @classmethod
    def from_values(
        cls, *, topic_id: uuid.UUID, score: Decimal, updated_at: datetime | None
    ) -> MasteryResponse:
        return cls(topic_id=topic_id, score=serialize_score(score), updated_at=updated_at)
