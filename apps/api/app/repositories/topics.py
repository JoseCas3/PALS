import uuid

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attempt import Attempt
from app.models.exam_topic import ExamTopic
from app.models.mastery import Mastery
from app.models.question import Question
from app.models.topic import Topic


class TopicRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_subject(self, subject_id: uuid.UUID) -> list[Topic]:
        result = await self.session.scalars(
            select(Topic)
            .where(Topic.subject_id == subject_id)
            .order_by(Topic.created_at, Topic.id)
        )
        return list(result)

    async def get(self, topic_id: uuid.UUID) -> Topic | None:
        return await self.session.get(Topic, topic_id)

    async def create(
        self, *, subject_id: uuid.UUID, name: str, description: str | None
    ) -> Topic:
        topic = Topic(subject_id=subject_id, name=name, description=description)
        self.session.add(topic)
        await self.session.flush()
        await self.session.refresh(topic)
        return topic

    async def is_attached_to_exam(self, topic_id: uuid.UUID) -> bool:
        return bool(
            await self.session.scalar(select(exists().where(ExamTopic.topic_id == topic_id)))
        )

    async def has_questions(self, topic_id: uuid.UUID) -> bool:
        return bool(
            await self.session.scalar(select(exists().where(Question.topic_id == topic_id)))
        )

    async def has_learning_evidence(self, topic_id: uuid.UUID) -> bool:
        has_mastery = await self.session.scalar(
            select(exists().where(Mastery.topic_id == topic_id))
        )
        if has_mastery:
            return True
        return bool(
            await self.session.scalar(
                select(
                    exists().where(
                        Attempt.question_id == Question.id,
                        Question.topic_id == topic_id,
                    )
                )
            )
        )

    async def delete(self, topic: Topic) -> None:
        await self.session.delete(topic)
        await self.session.flush()
