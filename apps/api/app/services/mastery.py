from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.models.question import QuestionDifficulty
from app.repositories.mastery import MasteryRepository
from app.repositories.topics import TopicRepository

CORRECT_BASE = Decimal("8")
INCORRECT_BASE = Decimal("-5")
DIFFICULTY_MULTIPLIERS = {
    QuestionDifficulty.EASY.value: Decimal("0.75"),
    QuestionDifficulty.MEDIUM.value: Decimal("1.00"),
    QuestionDifficulty.HARD.value: Decimal("1.25"),
}
HELP_MULTIPLIERS = {
    0: Decimal("1.00"),
    1: Decimal("0.80"),
    2: Decimal("0.60"),
    3: Decimal("0.40"),
}
SOLUTION_MULTIPLIER = Decimal("0.10")
SCORE_QUANTUM = Decimal("0.01")
MIN_SCORE = Decimal("0.00")
MAX_SCORE = Decimal("100.00")


def calculate_delta(
    *, correct: bool, difficulty: str, hints_used: int, solution_seen: bool
) -> Decimal:
    base = CORRECT_BASE if correct else INCORRECT_BASE
    help_multiplier = (
        SOLUTION_MULTIPLIER if solution_seen else HELP_MULTIPLIERS[hints_used]
    )
    return (base * DIFFICULTY_MULTIPLIERS[difficulty] * help_multiplier).quantize(
        SCORE_QUANTUM, rounding=ROUND_HALF_UP
    )


def apply_delta(previous_score: Decimal, delta: Decimal) -> Decimal:
    score = min(MAX_SCORE, max(MIN_SCORE, previous_score + delta))
    return score.quantize(SCORE_QUANTUM, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class MasteryState:
    topic_id: uuid.UUID
    score: Decimal
    updated_at: datetime | None


class MasteryService:
    def __init__(self, session: AsyncSession) -> None:
        self.topics = TopicRepository(session)
        self.mastery = MasteryRepository(session)

    async def get(self, topic_id: uuid.UUID) -> MasteryState:
        if await self.topics.get(topic_id) is None:
            raise ApplicationError(404, "RESOURCE_NOT_FOUND", "Topic not found")
        mastery = await self.mastery.get(topic_id)
        if mastery is None:
            return MasteryState(topic_id=topic_id, score=MIN_SCORE, updated_at=None)
        return MasteryState(
            topic_id=mastery.topic_id,
            score=mastery.score,
            updated_at=mastery.updated_at,
        )
