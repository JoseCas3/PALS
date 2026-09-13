from __future__ import annotations

import copy
import json
import re
import unicodedata
import uuid

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts import AIProviderException, AIRequest, AIResponse, AIStructuredResponse
from app.ai.gateway import AIGateway
from app.ai.prompts import (
    MAX_GENERATION_USER_PROMPT_CHARS,
    MAX_TOPIC_DESCRIPTION_CHARS,
    QUESTION_GENERATION_MAX_OUTPUT_CHARS,
    QUESTION_GENERATION_MAX_OUTPUT_TOKENS,
    QUESTION_GENERATION_PROMPT_VERSION,
    QuestionGenerationPromptContext,
    build_question_generation_prompt,
)
from app.core.errors import ApplicationError
from app.models.ai_interaction import AIInteraction
from app.models.question import QuestionDifficulty
from app.repositories.ai_interactions import AIInteractionRepository
from app.repositories.question_generation import QuestionGenerationRepository
from app.schemas.question_generation import (
    GeneratedCandidatesPayload,
    GenerationDifficulty,
    QuestionGenerationCandidate,
    QuestionGenerationRequest,
    QuestionGenerationResponse,
)

ERROR_STATUSES = {
    "AI_PROVIDER_TIMEOUT": 504,
    "AI_PROVIDER_RATE_LIMITED": 503,
    "AI_PROVIDER_UNAVAILABLE": 503,
    "AI_PROVIDER_AUTHENTICATION_FAILED": 503,
    "AI_PROVIDER_INVALID_RESPONSE": 502,
    "AI_PROVIDER_ERROR": 502,
}


def normalize_question_prompt(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip()
    return re.sub(r"\s+", " ", normalized).casefold()


def build_generation_json_schema(count: int) -> dict[str, object]:
    schema = copy.deepcopy(GeneratedCandidatesPayload.model_json_schema())
    candidates = schema["properties"]["candidates"]
    candidates["minItems"] = count
    candidates["maxItems"] = count
    return schema


class QuestionGenerationService:
    def __init__(self, session: AsyncSession, gateway: AIGateway) -> None:
        self.session = session
        self.gateway = gateway
        self.generation = QuestionGenerationRepository(session)
        self.interactions = AIInteractionRepository(session)

    async def generate(
        self, topic_id: uuid.UUID, data: QuestionGenerationRequest
    ) -> QuestionGenerationResponse:
        context = await self.generation.get_context(topic_id)
        if context is None:
            raise ApplicationError(404, "RESOURCE_NOT_FOUND", "Topic not found")
        existing_prompts = await self.generation.list_existing_prompts(topic_id)
        if (
            context.topic_description is not None
            and len(context.topic_description) > MAX_TOPIC_DESCRIPTION_CHARS
        ):
            raise ApplicationError(
                422,
                "GENERATION_CONTEXT_TOO_LARGE",
                "Topic context is too large for Question generation",
            )

        prompt = build_question_generation_prompt(
            QuestionGenerationPromptContext(
                subject_name=context.subject_name,
                topic_name=context.topic_name,
                topic_description=context.topic_description,
                count=data.count,
                difficulty=data.difficulty.value,
            )
        )
        if len(prompt.user_prompt) > MAX_GENERATION_USER_PROMPT_CHARS:
            raise ApplicationError(
                422,
                "GENERATION_CONTEXT_TOO_LARGE",
                "Topic context is too large for Question generation",
            )

        interaction = await self.interactions.create_pending(
            provider=self.gateway.provider.provider_name,
            model=self.gateway.provider.model_name,
            operation="question_generation",
            subject_id=context.subject_id,
            topic_id=context.topic_id,
            question_id=None,
            help_level=None,
            prompt_version=QUESTION_GENERATION_PROMPT_VERSION,
            input_chars=len(prompt.system_prompt) + len(prompt.user_prompt),
            success=None,
            error_code=None,
        )
        await self.session.commit()

        request = AIRequest(
            operation="question_generation",
            system_prompt=prompt.system_prompt,
            user_prompt=prompt.user_prompt,
            max_output_tokens=QUESTION_GENERATION_MAX_OUTPUT_TOKENS,
            structured_response=AIStructuredResponse(
                schema_name="question_generation",
                json_schema=build_generation_json_schema(data.count),
            ),
            max_output_chars=QUESTION_GENERATION_MAX_OUTPUT_CHARS,
        )
        try:
            response = await self.gateway.generate(request)
        except AIProviderException as exc:
            self.interactions.finalize_failure(
                interaction,
                error_code=exc.code,
                latency_ms=exc.latency_ms if exc.latency_ms is not None else 0,
            )
            await self._commit_finalization()
            raise ApplicationError(
                ERROR_STATUSES[exc.code],
                exc.code,
                "AI service is temporarily unavailable",
                {"interaction_id": str(interaction.id)},
            ) from exc

        try:
            decoded = json.loads(response.content)
        except (json.JSONDecodeError, TypeError) as exc:
            await self._finalize_invalid_response(
                interaction, response, "AI_PROVIDER_INVALID_RESPONSE"
            )
            raise ApplicationError(
                502,
                "AI_PROVIDER_INVALID_RESPONSE",
                "AI service returned an unusable response",
                {"interaction_id": str(interaction.id)},
            ) from exc

        try:
            payload = GeneratedCandidatesPayload.model_validate(decoded, strict=True)
            self._validate_candidates(payload, data)
        except (ValidationError, ValueError) as exc:
            await self._finalize_invalid_response(
                interaction, response, "GENERATED_CANDIDATES_INVALID"
            )
            raise ApplicationError(
                422,
                "GENERATED_CANDIDATES_INVALID",
                "Generated candidates did not satisfy the Question contract",
                {"interaction_id": str(interaction.id)},
            ) from exc

        existing = {normalize_question_prompt(value) for value in existing_prompts}
        candidates = [
            QuestionGenerationCandidate(
                prompt=candidate.prompt,
                answer_reference=candidate.answer_reference,
                difficulty=QuestionDifficulty(candidate.difficulty),
                duplicate_existing=normalize_question_prompt(candidate.prompt) in existing,
            )
            for candidate in payload.candidates
        ]
        self.interactions.finalize_success(interaction, response)
        await self._commit_finalization()
        return QuestionGenerationResponse(
            interaction_id=interaction.id,
            topic_id=context.topic_id,
            candidates=candidates,
            provider=response.provider,
            model=response.model,
            prompt_version=QUESTION_GENERATION_PROMPT_VERSION,
            created_at=interaction.created_at,
        )

    @staticmethod
    def _validate_candidates(
        payload: GeneratedCandidatesPayload, data: QuestionGenerationRequest
    ) -> None:
        if len(payload.candidates) != data.count:
            raise ValueError("Provider returned the wrong candidate count")
        if data.difficulty is not GenerationDifficulty.MIXED and any(
            candidate.difficulty != data.difficulty.value
            for candidate in payload.candidates
        ):
            raise ValueError("Provider returned the wrong difficulty")
        normalized = [
            normalize_question_prompt(candidate.prompt) for candidate in payload.candidates
        ]
        if len(normalized) != len(set(normalized)):
            raise ValueError("Provider returned duplicate candidate prompts")

    async def _finalize_invalid_response(
        self, interaction: AIInteraction, response: AIResponse, error_code: str
    ) -> None:
        self.interactions.finalize_failure(
            interaction,
            error_code=error_code,
            latency_ms=response.latency_ms,
            response=response,
        )
        await self._commit_finalization()

    async def _commit_finalization(self) -> None:
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
