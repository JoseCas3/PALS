import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exam_topic import ExamTopic
from app.models.mastery import Mastery
from app.models.topic import Topic


@dataclass(frozen=True)
class PlannerTopicInput:
    topic_id: uuid.UUID
    topic_name: str
    exam_weight: Decimal
    mastery_score: Decimal


class PlannerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_topic_inputs(self, exam_id: uuid.UUID) -> list[PlannerTopicInput]:
        result = await self.session.execute(
            select(Topic.id, Topic.name, ExamTopic.weight, Mastery.score)
            .join(Topic, Topic.id == ExamTopic.topic_id)
            .outerjoin(Mastery, Mastery.topic_id == Topic.id)
            .where(ExamTopic.exam_id == exam_id)
        )
        return [
            PlannerTopicInput(
                topic_id=topic_id,
                topic_name=topic_name,
                exam_weight=exam_weight,
                mastery_score=mastery_score if mastery_score is not None else Decimal("0.00"),
            )
            for topic_id, topic_name, exam_weight, mastery_score in result.all()
        ]
