import uuid

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exam import Exam
from app.models.subject import Subject
from app.models.topic import Topic


class SubjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[Subject]:
        statement = select(Subject).order_by(Subject.created_at, Subject.id)
        result = await self.session.scalars(statement)
        return list(result)

    async def get(self, subject_id: uuid.UUID) -> Subject | None:
        return await self.session.get(Subject, subject_id)

    async def create(self, *, name: str, description: str | None) -> Subject:
        subject = Subject(name=name, description=description)
        self.session.add(subject)
        await self.session.flush()
        await self.session.refresh(subject)
        return subject

    async def has_topics(self, subject_id: uuid.UUID) -> bool:
        return bool(
            await self.session.scalar(select(exists().where(Topic.subject_id == subject_id)))
        )

    async def has_exams(self, subject_id: uuid.UUID) -> bool:
        return bool(
            await self.session.scalar(select(exists().where(Exam.subject_id == subject_id)))
        )

    async def delete(self, subject: Subject) -> None:
        await self.session.delete(subject)
        await self.session.flush()
