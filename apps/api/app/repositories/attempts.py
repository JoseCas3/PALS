import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attempt import Attempt


class AttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_question(self, question_id: uuid.UUID) -> list[Attempt]:
        result = await self.session.scalars(
            select(Attempt)
            .where(Attempt.question_id == question_id)
            .order_by(Attempt.created_at.desc(), Attempt.id.desc())
        )
        return list(result)

    def add(self, **values: object) -> Attempt:
        attempt = Attempt(**values)
        self.session.add(attempt)
        return attempt
