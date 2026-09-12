import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exam import Exam


class ExamRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_subject(self, subject_id: uuid.UUID) -> list[Exam]:
        result = await self.session.scalars(
            select(Exam)
            .where(Exam.subject_id == subject_id)
            .order_by(Exam.exam_date, Exam.id)
        )
        return list(result)

    async def get(self, exam_id: uuid.UUID) -> Exam | None:
        return await self.session.get(Exam, exam_id)

    async def create(self, **values: object) -> Exam:
        exam = Exam(**values)
        self.session.add(exam)
        await self.session.flush()
        await self.session.refresh(exam)
        return exam

    async def delete(self, exam: Exam) -> None:
        await self.session.delete(exam)
        await self.session.flush()
