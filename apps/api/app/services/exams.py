import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.models.exam import Exam
from app.repositories.exams import ExamRepository
from app.repositories.subjects import SubjectRepository
from app.schemas.exam import ExamCreate, ExamUpdate


class ExamService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.subjects = SubjectRepository(session)
        self.exams = ExamRepository(session)

    async def _require_subject(self, subject_id: uuid.UUID) -> None:
        if await self.subjects.get(subject_id) is None:
            raise ApplicationError(404, "RESOURCE_NOT_FOUND", "Subject not found")

    async def list_for_subject(self, subject_id: uuid.UUID) -> list[Exam]:
        await self._require_subject(subject_id)
        return await self.exams.list_for_subject(subject_id)

    async def get(self, exam_id: uuid.UUID) -> Exam:
        exam = await self.exams.get(exam_id)
        if exam is None:
            raise ApplicationError(404, "RESOURCE_NOT_FOUND", "Exam not found")
        return exam

    async def create(self, subject_id: uuid.UUID, data: ExamCreate) -> Exam:
        await self._require_subject(subject_id)
        exam = await self.exams.create(subject_id=subject_id, **data.model_dump())
        await self.session.commit()
        return exam

    async def update(self, exam_id: uuid.UUID, data: ExamUpdate) -> Exam:
        exam = await self.get(exam_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(exam, field, value)
        await self.session.flush()
        await self.session.refresh(exam)
        await self.session.commit()
        return exam

    async def delete(self, exam_id: uuid.UUID) -> None:
        exam = await self.get(exam_id)
        await self.exams.delete(exam)
        await self.session.commit()
