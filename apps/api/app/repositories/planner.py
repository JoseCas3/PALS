import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exam import Exam
from app.models.exam_topic import ExamTopic
from app.models.mastery import Mastery
from app.models.subject import Subject
from app.models.topic import Topic


@dataclass(frozen=True)
class PlannerTopicInput:
    topic_id: uuid.UUID
    topic_name: str
    exam_weight: Decimal
    mastery_score: Decimal


@dataclass(frozen=True)
class GlobalPlannerInput:
    subject_id: uuid.UUID
    subject_name: str
    exam_id: uuid.UUID
    exam_name: str
    exam_date: datetime
    topic_id: uuid.UUID
    topic_name: str
    exam_weight: Decimal
    mastery_score: Decimal | None


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

    async def list_global_inputs(self, generated_at: datetime) -> list[GlobalPlannerInput]:
        result = await self.session.execute(
            select(
                Subject.id,
                Subject.name,
                Exam.id,
                Exam.name,
                Exam.exam_date,
                Topic.id,
                Topic.name,
                ExamTopic.weight,
                Mastery.score,
            )
            .select_from(Exam)
            .join(Subject, Subject.id == Exam.subject_id)
            .join(ExamTopic, ExamTopic.exam_id == Exam.id)
            .join(Topic, Topic.id == ExamTopic.topic_id)
            .outerjoin(Mastery, Mastery.topic_id == Topic.id)
            .where(Exam.exam_date >= generated_at)
        )
        return [
            GlobalPlannerInput(
                subject_id=subject_id,
                subject_name=subject_name,
                exam_id=exam_id,
                exam_name=exam_name,
                exam_date=exam_date,
                topic_id=topic_id,
                topic_name=topic_name,
                exam_weight=exam_weight,
                mastery_score=mastery_score,
            )
            for (
                subject_id,
                subject_name,
                exam_id,
                exam_name,
                exam_date,
                topic_id,
                topic_name,
                exam_weight,
                mastery_score,
            ) in result.all()
        ]
