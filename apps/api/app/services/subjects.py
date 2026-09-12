import uuid

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.models.subject import Subject
from app.repositories.subjects import SubjectRepository
from app.schemas.subject import SubjectCreate, SubjectUpdate


class SubjectService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.subjects = SubjectRepository(session)

    async def list(self) -> list[Subject]:
        return await self.subjects.list()

    async def get(self, subject_id: uuid.UUID) -> Subject:
        subject = await self.subjects.get(subject_id)
        if subject is None:
            raise ApplicationError(404, "RESOURCE_NOT_FOUND", "Subject not found")
        return subject

    async def create(self, data: SubjectCreate) -> Subject:
        subject = await self.subjects.create(**data.model_dump())
        await self.session.commit()
        return subject

    async def update(self, subject_id: uuid.UUID, data: SubjectUpdate) -> Subject:
        subject = await self.get(subject_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(subject, field, value)
        await self.session.flush()
        await self.session.refresh(subject)
        await self.session.commit()
        return subject

    async def delete(self, subject_id: uuid.UUID) -> None:
        subject = await self.get(subject_id)
        if await self.subjects.has_topics(subject_id):
            raise ApplicationError(
                status.HTTP_409_CONFLICT,
                "SUBJECT_HAS_TOPICS",
                "Subject cannot be deleted while it has topics",
            )
        if await self.subjects.has_exams(subject_id):
            raise ApplicationError(
                status.HTTP_409_CONFLICT,
                "SUBJECT_HAS_EXAMS",
                "Subject cannot be deleted while it has exams",
            )
        try:
            await self.subjects.delete(subject)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ApplicationError(
                409, "SUBJECT_DELETE_CONFLICT", "Subject is still referenced"
            ) from exc
