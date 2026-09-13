from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import Question
from app.models.subject import Subject
from app.models.topic import Topic


@dataclass(frozen=True)
class QuestionTutorContext:
    subject_id: uuid.UUID
    subject_name: str
    topic_id: uuid.UUID
    topic_name: str
    topic_description: str | None
    question_id: uuid.UUID
    question_prompt: str
    answer_reference: str
    question_difficulty: str


class TutorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_question_context(
        self, question_id: uuid.UUID
    ) -> QuestionTutorContext | None:
        row = (
            await self.session.execute(
                select(
                    Subject.id,
                    Subject.name,
                    Topic.id,
                    Topic.name,
                    Topic.description,
                    Question.id,
                    Question.prompt,
                    Question.answer_reference,
                    Question.difficulty,
                )
                .join(Topic, Topic.subject_id == Subject.id)
                .join(Question, Question.topic_id == Topic.id)
                .where(Question.id == question_id)
            )
        ).one_or_none()
        if row is None:
            return None
        return QuestionTutorContext(
            subject_id=row[0],
            subject_name=row[1],
            topic_id=row[2],
            topic_name=row[3],
            topic_description=row[4],
            question_id=row[5],
            question_prompt=row[6],
            answer_reference=row[7],
            question_difficulty=row[8],
        )
