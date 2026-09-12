import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mastery import Mastery


class MasteryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, topic_id: uuid.UUID) -> Mastery | None:
        return await self.session.get(Mastery, topic_id)

    async def ensure_exists(self, topic_id: uuid.UUID) -> None:
        statement = (
            insert(Mastery)
            .values(topic_id=topic_id, score=Decimal("0.00"))
            .on_conflict_do_nothing(index_elements=[Mastery.topic_id])
        )
        await self.session.execute(statement)

    async def get_for_update(self, topic_id: uuid.UUID) -> Mastery | None:
        result = await self.session.scalars(
            select(Mastery).where(Mastery.topic_id == topic_id).with_for_update()
        )
        return result.one_or_none()
