import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.models.topic import Topic
from app.repositories.subjects import SubjectRepository
from app.repositories.topics import TopicRepository
from app.schemas.topic import TopicCreate, TopicUpdate


class TopicService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.subjects = SubjectRepository(session)
        self.topics = TopicRepository(session)

    async def _require_subject(self, subject_id: uuid.UUID) -> None:
        if await self.subjects.get(subject_id) is None:
            raise ApplicationError(404, "RESOURCE_NOT_FOUND", "Subject not found")

    async def list_for_subject(self, subject_id: uuid.UUID) -> list[Topic]:
        await self._require_subject(subject_id)
        return await self.topics.list_for_subject(subject_id)

    async def get(self, topic_id: uuid.UUID) -> Topic:
        topic = await self.topics.get(topic_id)
        if topic is None:
            raise ApplicationError(404, "RESOURCE_NOT_FOUND", "Topic not found")
        return topic

    async def create(self, subject_id: uuid.UUID, data: TopicCreate) -> Topic:
        await self._require_subject(subject_id)
        topic = await self.topics.create(subject_id=subject_id, **data.model_dump())
        await self.session.commit()
        return topic

    async def update(self, topic_id: uuid.UUID, data: TopicUpdate) -> Topic:
        topic = await self.get(topic_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(topic, field, value)
        await self.session.flush()
        await self.session.refresh(topic)
        await self.session.commit()
        return topic

    async def delete(self, topic_id: uuid.UUID) -> None:
        topic = await self.get(topic_id)
        if await self.topics.is_attached_to_exam(topic_id):
            raise ApplicationError(
                409,
                "TOPIC_HAS_EXAMS",
                "Topic cannot be deleted while it is assigned to an exam",
            )
        if await self.topics.has_learning_evidence(topic_id):
            raise ApplicationError(
                409,
                "TOPIC_HAS_LEARNING_EVIDENCE",
                "Topic cannot be deleted while it has learning evidence",
            )
        if await self.topics.has_questions(topic_id):
            raise ApplicationError(
                409,
                "TOPIC_HAS_QUESTIONS",
                "Topic cannot be deleted while it has questions",
            )
        try:
            await self.topics.delete(topic)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ApplicationError(
                409, "TOPIC_DELETE_CONFLICT", "Topic is still referenced"
            ) from exc
