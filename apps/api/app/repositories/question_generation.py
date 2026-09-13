from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import Question
from app.models.subject import Subject
from app.models.topic import Topic


@dataclass(frozen=True)
class QuestionGenerationContext:
    subject_id: uuid.UUID
    subject_name: str
    topic_id: uuid.UUID
    topic_name: str
    topic_description: str | None


class QuestionGenerationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_context(self, topic_id: uuid.UUID) -> QuestionGenerationContext | None:
        row = (
            await self.session.execute(
                select(
                    Subject.id,
                    Subject.name,
                    Topic.id,
                    Topic.name,
                    Topic.description,
                )
                .join(Topic, Topic.subject_id == Subject.id)
                .where(Topic.id == topic_id)
            )
        ).one_or_none()
        if row is None:
            return None
        return QuestionGenerationContext(
            subject_id=row[0],
            subject_name=row[1],
            topic_id=row[2],
            topic_name=row[3],
            topic_description=row[4],
        )

    async def list_existing_prompts(self, topic_id: uuid.UUID) -> list[str]:
        result = await self.session.scalars(
            select(Question.prompt).where(Question.topic_id == topic_id)
        )
        return list(result)
