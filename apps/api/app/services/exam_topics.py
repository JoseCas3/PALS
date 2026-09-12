import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.models.exam import Exam
from app.models.exam_topic import ExamTopic
from app.models.topic import Topic
from app.repositories.exam_topics import ExamTopicRepository
from app.repositories.exams import ExamRepository
from app.repositories.topics import TopicRepository
from app.schemas.exam_topic import ExamTopicPut


class ExamTopicService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.exams = ExamRepository(session)
        self.topics = TopicRepository(session)
        self.exam_topics = ExamTopicRepository(session)

    async def _get_exam(self, exam_id: uuid.UUID) -> Exam:
        exam = await self.exams.get(exam_id)
        if exam is None:
            raise ApplicationError(404, "RESOURCE_NOT_FOUND", "Exam not found")
        return exam

    async def _get_topic(self, topic_id: uuid.UUID) -> Topic:
        topic = await self.topics.get(topic_id)
        if topic is None:
            raise ApplicationError(404, "RESOURCE_NOT_FOUND", "Topic not found")
        return topic

    async def list_for_exam(self, exam_id: uuid.UUID) -> list[ExamTopic]:
        await self._get_exam(exam_id)
        return await self.exam_topics.list_for_exam(exam_id)

    async def put(
        self, exam_id: uuid.UUID, topic_id: uuid.UUID, data: ExamTopicPut
    ) -> ExamTopic:
        exam = await self._get_exam(exam_id)
        topic = await self._get_topic(topic_id)
        if exam.subject_id != topic.subject_id:
            raise ApplicationError(
                409,
                "CROSS_SUBJECT_EXAM_TOPIC",
                "Exam and topic must belong to the same subject",
            )
        association = await self.exam_topics.upsert(
            exam_id=exam_id, topic_id=topic_id, weight=data.weight
        )
        await self.session.commit()
        return association

    async def delete(self, exam_id: uuid.UUID, topic_id: uuid.UUID) -> None:
        await self._get_exam(exam_id)
        await self._get_topic(topic_id)
        association = await self.exam_topics.get(exam_id, topic_id)
        if association is None:
            raise ApplicationError(404, "RESOURCE_NOT_FOUND", "Exam-topic association not found")
        await self.exam_topics.delete(association)
        await self.session.commit()
