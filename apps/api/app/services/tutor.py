from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts import AIProviderException, AIRequest
from app.ai.gateway import AIGateway
from app.ai.prompts import (
    MAX_ANSWER_REFERENCE_CHARS,
    MAX_QUESTION_PROMPT_CHARS,
    MAX_TOPIC_DESCRIPTION_CHARS,
    MAX_USER_PROMPT_CHARS,
    TUTOR_MAX_OUTPUT_TOKENS,
    TUTOR_PROMPT_VERSION,
    TutorHelpLevel,
    TutorPromptContext,
    build_question_tutor_prompt,
)
from app.core.errors import ApplicationError
from app.repositories.ai_interactions import AIInteractionRepository
from app.repositories.tutor import QuestionTutorContext, TutorRepository

ERROR_STATUSES = {
    "AI_PROVIDER_TIMEOUT": 504,
    "AI_PROVIDER_RATE_LIMITED": 503,
    "AI_PROVIDER_UNAVAILABLE": 503,
    "AI_PROVIDER_AUTHENTICATION_FAILED": 503,
    "AI_PROVIDER_INVALID_RESPONSE": 502,
    "AI_PROVIDER_ERROR": 502,
}


@dataclass(frozen=True)
class TutorResult:
    interaction_id: uuid.UUID
    question_id: uuid.UUID
    help_level: int
    content: str
    provider: str
    model: str
    prompt_version: str
    created_at: datetime


def _validate_context(context: QuestionTutorContext, help_level: TutorHelpLevel) -> None:
    too_large = (
        len(context.question_prompt) > MAX_QUESTION_PROMPT_CHARS
        or (
            context.topic_description is not None
            and len(context.topic_description) > MAX_TOPIC_DESCRIPTION_CHARS
        )
        or (
            help_level >= TutorHelpLevel.GUIDED_SOLUTION
            and len(context.answer_reference) > MAX_ANSWER_REFERENCE_CHARS
        )
    )
    if too_large:
        raise ApplicationError(
            422,
            "TUTOR_CONTEXT_TOO_LARGE",
            "Question context is too large for Tutor assistance",
        )


class TutorService:
    def __init__(self, session: AsyncSession, gateway: AIGateway) -> None:
        self.session = session
        self.gateway = gateway
        self.tutor = TutorRepository(session)
        self.interactions = AIInteractionRepository(session)

    async def help_question(self, question_id: uuid.UUID, level: int) -> TutorResult:
        context = await self.tutor.get_question_context(question_id)
        if context is None:
            raise ApplicationError(404, "RESOURCE_NOT_FOUND", "Question not found")
        help_level = TutorHelpLevel(level)
        _validate_context(context, help_level)
        prompt = build_question_tutor_prompt(
            TutorPromptContext(
                subject_name=context.subject_name,
                topic_name=context.topic_name,
                topic_description=context.topic_description,
                question_prompt=context.question_prompt,
                question_difficulty=context.question_difficulty,
                help_level=help_level,
                answer_reference=(
                    context.answer_reference
                    if help_level >= TutorHelpLevel.GUIDED_SOLUTION
                    else None
                ),
            )
        )
        if len(prompt.user_prompt) > MAX_USER_PROMPT_CHARS:
            raise ApplicationError(
                422,
                "TUTOR_CONTEXT_TOO_LARGE",
                "Question context is too large for Tutor assistance",
            )

        interaction = await self.interactions.create_pending(
            provider=self.gateway.provider.provider_name,
            model=self.gateway.provider.model_name,
            operation="question_tutor",
            subject_id=context.subject_id,
            topic_id=context.topic_id,
            question_id=context.question_id,
            help_level=int(help_level),
            prompt_version=TUTOR_PROMPT_VERSION,
            input_chars=len(prompt.system_prompt) + len(prompt.user_prompt),
            success=None,
            error_code=None,
        )
        await self.session.commit()

        request = AIRequest(
            operation="question_tutor",
            system_prompt=prompt.system_prompt,
            user_prompt=prompt.user_prompt,
            max_output_tokens=TUTOR_MAX_OUTPUT_TOKENS,
        )
        try:
            response = await self.gateway.generate(request)
        except AIProviderException as exc:
            latency_ms = exc.latency_ms if exc.latency_ms is not None else 0
            self.interactions.finalize_failure(
                interaction, error_code=exc.code, latency_ms=latency_ms
            )
            try:
                await self.session.commit()
            except Exception:
                await self.session.rollback()
                raise
            raise ApplicationError(
                ERROR_STATUSES[exc.code],
                exc.code,
                "Tutor service is temporarily unavailable",
                {"interaction_id": str(interaction.id)},
            ) from exc

        self.interactions.finalize_success(interaction, response)
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return TutorResult(
            interaction_id=interaction.id,
            question_id=context.question_id,
            help_level=int(help_level),
            content=response.content,
            provider=response.provider,
            model=response.model,
            prompt_version=TUTOR_PROMPT_VERSION,
            created_at=interaction.created_at,
        )
