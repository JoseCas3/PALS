import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.models.attempt import Attempt
from app.models.mastery import Mastery
from app.repositories.attempts import AttemptRepository
from app.repositories.mastery import MasteryRepository
from app.repositories.questions import QuestionRepository
from app.schemas.attempt import AttemptCreate
from app.services.mastery import apply_delta, calculate_delta


class AttemptService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.questions = QuestionRepository(session)
        self.attempts = AttemptRepository(session)
        self.mastery = MasteryRepository(session)

    async def list_for_question(self, question_id: uuid.UUID) -> list[Attempt]:
        if await self.questions.get(question_id) is None:
            raise ApplicationError(404, "RESOURCE_NOT_FOUND", "Question not found")
        return await self.attempts.list_for_question(question_id)

    async def record(
        self, question_id: uuid.UUID, data: AttemptCreate
    ) -> tuple[Attempt, Mastery]:
        # Question is always locked before Mastery to keep lock ordering consistent.
        question = await self.questions.get_for_update(question_id)
        if question is None:
            raise ApplicationError(404, "RESOURCE_NOT_FOUND", "Question not found")

        await self.mastery.ensure_exists(question.topic_id)
        mastery = await self.mastery.get_for_update(question.topic_id)
        if mastery is None:
            raise RuntimeError("Mastery insert did not produce a row")

        delta = calculate_delta(
            correct=data.correct,
            difficulty=question.difficulty,
            hints_used=data.hints_used,
            solution_seen=data.solution_seen,
        )
        attempt = self.attempts.add(question_id=question_id, **data.model_dump())
        mastery.score = apply_delta(mastery.score, delta)
        mastery.updated_at = datetime.now(UTC)

        await self.session.flush()
        await self.session.refresh(attempt)
        await self.session.refresh(mastery)
        await self.session.commit()
        return attempt, mastery
