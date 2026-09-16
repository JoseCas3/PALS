from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts import AIProviderException, AIRequest, AIResponse, AIStructuredResponse
from app.ai.gateway import AIGateway
from app.ai.prompts import (
    GROUNDED_TUTOR_PROMPT_VERSION,
    MAX_ANSWER_REFERENCE_CHARS,
    MAX_QUESTION_PROMPT_CHARS,
    MAX_TOPIC_DESCRIPTION_CHARS,
    MAX_USER_PROMPT_CHARS,
    TUTOR_MAX_OUTPUT_TOKENS,
    GroundedPromptSource,
    TutorHelpLevel,
    TutorPromptContext,
    build_grounded_question_tutor_prompt,
    build_question_tutor_prompt,
)
from app.core.errors import ApplicationError
from app.embeddings.contracts import (
    EmbeddingDimensionMismatchError,
    EmbeddingError,
    EmbeddingUnavailableError,
)
from app.grounding.tutor import (
    CitationValidator,
    GroundedCitation,
    GroundingValidationError,
    build_grounded_context,
)
from app.models.ai_interaction import AIInteraction
from app.repositories.ai_interactions import AIInteractionRepository
from app.repositories.tutor import QuestionTutorContext, TutorRepository
from app.retrieval.service import RetrievalService
from app.schemas.tutor import (
    GroundedTutorGeneration,
    GroundingMode,
    TutorOutcome,
)

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
    interaction_id: uuid.UUID | None
    question_id: uuid.UUID
    help_level: int
    grounding_mode: GroundingMode
    outcome: TutorOutcome
    content: str | None
    answer: str | None
    citations: tuple[GroundedCitation, ...]
    provider: str | None
    model: str | None
    prompt_version: str
    created_at: datetime | None


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
    def __init__(
        self,
        session: AsyncSession,
        gateway: AIGateway,
        retrieval: RetrievalService | None = None,
    ) -> None:
        self.session = session
        self.gateway = gateway
        self.tutor = TutorRepository(session)
        self.interactions = AIInteractionRepository(session)
        self.retrieval = retrieval
        self.citations = CitationValidator()

    async def help_question(
        self,
        question_id: uuid.UUID,
        level: int,
        grounding_mode: GroundingMode = GroundingMode.NONE,
    ) -> TutorResult:
        context = await self.tutor.get_question_context(question_id)
        if context is None:
            raise ApplicationError(404, "RESOURCE_NOT_FOUND", "Question not found")
        help_level = TutorHelpLevel(level)
        _validate_context(context, help_level)
        prompt_context = TutorPromptContext(
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
        grounded_context = None
        if grounding_mode is GroundingMode.REQUIRED:
            if self.retrieval is None:
                raise RuntimeError("Grounded Tutor requires RetrievalService")
            try:
                retrieval = await self.retrieval.retrieve(
                    context.subject_id,
                    f"{context.topic_name}: {context.question_prompt}",
                )
            except EmbeddingUnavailableError as exc:
                raise ApplicationError(
                    503,
                    exc.code,
                    "Embedding service is temporarily unavailable",
                ) from exc
            except EmbeddingDimensionMismatchError as exc:
                raise ApplicationError(
                    500, exc.code, "Embedding dimensions are invalid"
                ) from exc
            except EmbeddingError as exc:
                raise ApplicationError(
                    502, exc.code, "Embedding generation failed"
                ) from exc
            if not retrieval.sufficient:
                return TutorResult(
                    interaction_id=None,
                    question_id=context.question_id,
                    help_level=int(help_level),
                    grounding_mode=grounding_mode,
                    outcome=TutorOutcome.INSUFFICIENT_EVIDENCE,
                    content=None,
                    answer=None,
                    citations=(),
                    provider=None,
                    model=None,
                    prompt_version=GROUNDED_TUTOR_PROMPT_VERSION,
                    created_at=None,
                )
            grounded_context = build_grounded_context(retrieval.chunks)
            prompt = build_grounded_question_tutor_prompt(
                prompt_context,
                tuple(
                    GroundedPromptSource(
                        alias=source.alias,
                        document_filename=source.chunk.document_filename,
                        page_start=source.chunk.page_start,
                        page_end=source.chunk.page_end,
                        text=source.chunk.text,
                    )
                    for source in grounded_context.sources
                ),
            )
        else:
            prompt = build_question_tutor_prompt(prompt_context)
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
            prompt_version=prompt.version,
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
            structured_response=(
                AIStructuredResponse(
                    schema_name="grounded_question_tutor",
                    json_schema=GroundedTutorGeneration.model_json_schema(),
                )
                if grounding_mode is GroundingMode.REQUIRED
                else None
            ),
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

        answer = response.content
        citations: tuple[GroundedCitation, ...] = ()
        if grounded_context is not None:
            try:
                payload = GroundedTutorGeneration.model_validate(
                    json.loads(response.content), strict=True
                )
                citations = self.citations.validate(
                    grounded_context.allowed_sources, payload.citations
                )
                answer = payload.answer
            except (
                json.JSONDecodeError,
                TypeError,
                ValidationError,
                GroundingValidationError,
            ) as exc:
                await self._finalize_invalid_grounding(interaction, response)
                raise ApplicationError(
                    502,
                    "GROUNDING_INVALID_RESPONSE",
                    "Tutor service returned an invalid grounded response",
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
            grounding_mode=grounding_mode,
            outcome=TutorOutcome.ANSWER,
            content=answer,
            answer=answer,
            citations=citations,
            provider=response.provider,
            model=response.model,
            prompt_version=prompt.version,
            created_at=interaction.created_at,
        )

    async def _finalize_invalid_grounding(
        self, interaction: AIInteraction, response: AIResponse
    ) -> None:
        self.interactions.finalize_failure(
            interaction,
            error_code="GROUNDING_INVALID_RESPONSE",
            latency_ms=response.latency_ms,
            response=response,
        )
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
