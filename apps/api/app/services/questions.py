import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.models.question import Question
from app.repositories.questions import QuestionRepository
from app.repositories.topics import TopicRepository
from app.schemas.question import QuestionCreate, QuestionUpdate


class QuestionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.topics = TopicRepository(session)
        self.questions = QuestionRepository(session)

    async def _require_topic(self, topic_id: uuid.UUID) -> None:
        if await self.topics.get(topic_id) is None:
            raise ApplicationError(404, "RESOURCE_NOT_FOUND", "Topic not found")

    async def list_for_topic(self, topic_id: uuid.UUID) -> list[Question]:
        await self._require_topic(topic_id)
        return await self.questions.list_for_topic(topic_id)

    async def get(self, question_id: uuid.UUID) -> Question:
        question = await self.questions.get(question_id)
        if question is None:
            raise ApplicationError(404, "RESOURCE_NOT_FOUND", "Question not found")
        return question

    async def create(self, topic_id: uuid.UUID, data: QuestionCreate) -> Question:
        await self._require_topic(topic_id)
        values = data.model_dump(mode="json")
        question = await self.questions.create(topic_id=topic_id, **values)
        await self.session.commit()
        return question

    async def update(self, question_id: uuid.UUID, data: QuestionUpdate) -> Question:
        question = await self.questions.get_for_update(question_id)
        if question is None:
            raise ApplicationError(404, "RESOURCE_NOT_FOUND", "Question not found")
        if await self.questions.has_attempts(question_id):
            raise ApplicationError(
                409,
                "QUESTION_HAS_ATTEMPTS",
                "Question cannot be changed after an attempt has been recorded",
            )
        for field, value in data.model_dump(exclude_unset=True, mode="json").items():
            setattr(question, field, value)
        await self.session.flush()
        await self.session.refresh(question)
        await self.session.commit()
        return question

    async def delete(self, question_id: uuid.UUID) -> None:
        question = await self.questions.get_for_update(question_id)
        if question is None:
            raise ApplicationError(404, "RESOURCE_NOT_FOUND", "Question not found")
        if await self.questions.has_attempts(question_id):
            raise ApplicationError(
                409,
                "QUESTION_HAS_ATTEMPTS",
                "Question cannot be deleted after an attempt has been recorded",
            )
        try:
            await self.questions.delete(question)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ApplicationError(
                409, "QUESTION_DELETE_CONFLICT", "Question is still referenced"
            ) from exc
