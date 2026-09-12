import uuid

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attempt import Attempt
from app.models.question import Question


class QuestionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_topic(self, topic_id: uuid.UUID) -> list[Question]:
        result = await self.session.scalars(
            select(Question)
            .where(Question.topic_id == topic_id)
            .order_by(Question.created_at, Question.id)
        )
        return list(result)

    async def get(self, question_id: uuid.UUID) -> Question | None:
        return await self.session.get(Question, question_id)

    async def get_for_update(self, question_id: uuid.UUID) -> Question | None:
        result = await self.session.scalars(
            select(Question).where(Question.id == question_id).with_for_update()
        )
        return result.one_or_none()

    async def create(self, **values: object) -> Question:
        question = Question(**values)
        self.session.add(question)
        await self.session.flush()
        await self.session.refresh(question)
        return question

    async def has_attempts(self, question_id: uuid.UUID) -> bool:
        return bool(
            await self.session.scalar(
                select(exists().where(Attempt.question_id == question_id))
            )
        )

    async def delete(self, question: Question) -> None:
        await self.session.delete(question)
        await self.session.flush()
