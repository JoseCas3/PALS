import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exam_topic import ExamTopic


class ExamTopicRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_exam(self, exam_id: uuid.UUID) -> list[ExamTopic]:
        result = await self.session.scalars(
            select(ExamTopic)
            .where(ExamTopic.exam_id == exam_id)
            .order_by(ExamTopic.topic_id)
        )
        return list(result)

    async def get(self, exam_id: uuid.UUID, topic_id: uuid.UUID) -> ExamTopic | None:
        return await self.session.get(ExamTopic, (exam_id, topic_id))

    async def upsert(
        self, *, exam_id: uuid.UUID, topic_id: uuid.UUID, weight: float
    ) -> ExamTopic:
        decimal_weight = Decimal(str(weight))
        statement = (
            insert(ExamTopic)
            .values(exam_id=exam_id, topic_id=topic_id, weight=decimal_weight)
            .on_conflict_do_update(
                index_elements=[ExamTopic.exam_id, ExamTopic.topic_id],
                set_={"weight": decimal_weight},
            )
        )
        await self.session.execute(statement)
        await self.session.flush()
        association = await self.get(exam_id, topic_id)
        if association is None:
            raise RuntimeError("Exam-topic upsert did not return an association")
        await self.session.refresh(association)
        return association

    async def delete(self, association: ExamTopic) -> None:
        await self.session.delete(association)
        await self.session.flush()
