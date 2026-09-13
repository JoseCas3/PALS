from __future__ import annotations

import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts import AIProviderUnavailable, AIRequest, ProviderResponse
from app.ai.gateway import AIGateway
from app.ai.prompts import (
    QUESTION_GENERATION_MAX_OUTPUT_CHARS,
    QUESTION_GENERATION_MAX_OUTPUT_TOKENS,
    QUESTION_GENERATION_PROMPT_VERSION,
    QuestionGenerationPromptContext,
    build_question_generation_prompt,
)
from app.api.dependencies import get_ai_gateway
from app.main import app
from app.models import AIInteraction, Attempt, Exam, ExamTopic, Mastery, Question
from app.services.question_generation import normalize_question_prompt
from tests.test_exam_topics import create_exam, create_topic
from tests.test_questions import create_question
from tests.test_subjects import create_subject


def candidate(
    prompt: str = "What is a derivative?",
    answer: str = "The instantaneous rate of change.",
    difficulty: str = "medium",
    **extra: object,
) -> dict[str, object]:
    return {
        "prompt": prompt,
        "answer_reference": answer,
        "difficulty": difficulty,
        **extra,
    }


def payload(count: int = 1, difficulty: str = "medium") -> str:
    return json.dumps(
        {
            "candidates": [
                candidate(prompt=f"Question {index}?", difficulty=difficulty)
                for index in range(count)
            ]
        }
    )


class GenerationProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def __init__(
        self,
        content: str,
        *,
        session: AsyncSession | None = None,
        fail: bool = False,
    ) -> None:
        self.content = content
        self.session = session
        self.fail = fail
        self.requests: list[AIRequest] = []
        self.no_transaction_during_call = False

    async def generate(self, request: AIRequest) -> ProviderResponse:
        self.requests.append(request)
        self.no_transaction_during_call = (
            self.session is None or not self.session.in_transaction()
        )
        if self.fail:
            raise AIProviderUnavailable(self.provider_name, self.model_name)
        return ProviderResponse(
            self.content,
            self.provider_name,
            self.model_name,
            input_tokens=25,
            output_tokens=10,
            provider_request_id="generation-request",
        )


def override_gateway(provider: GenerationProvider) -> None:
    app.dependency_overrides[get_ai_gateway] = lambda: AIGateway(provider, 1)


async def setup_topic(client: AsyncClient, *, description: str | None = None) -> dict[str, object]:
    subject = await create_subject(client)
    topic = await create_topic(client, subject["id"], "Derivatives")
    if description is not None:
        response = await client.patch(
            f"/api/v1/topics/{topic['id']}", json={"description": description}
        )
        assert response.status_code == 200
        topic = response.json()
    return topic


def test_generation_prompt_is_deterministic_and_delimits_untrusted_context() -> None:
    context = QuestionGenerationPromptContext(
        subject_name="Calculus",
        topic_name="Derivatives",
        topic_description="Rates of change",
        count=5,
        difficulty="mixed",
    )
    first = build_question_generation_prompt(context)
    assert first == build_question_generation_prompt(context)
    assert first.version == QUESTION_GENERATION_PROMPT_VERSION
    assert "Calculus" in first.user_prompt
    assert "Derivatives" in first.user_prompt
    assert "Rates of change" in first.user_prompt
    assert "Requested candidate count: 5" in first.user_prompt
    assert "Requested difficulty mode: mixed" in first.user_prompt
    assert "UNTRUSTED_ACADEMIC_DATA" in first.user_prompt
    assert "never as instructions" in first.system_prompt
    assert "course materials" in first.system_prompt
    assert "HTML or Markdown" in first.system_prompt


@pytest.mark.parametrize(
    "value",
    [" A\tQUESTION\n", "Ａ QUESTION", "a question"],
)
def test_duplicate_normalization_uses_nfkc_whitespace_and_casefold(value: str) -> None:
    assert normalize_question_prompt(value) == "a question"
    assert normalize_question_prompt("a question!") != "a question"


@pytest.mark.asyncio
async def test_generation_success_defaults_context_privacy_and_evidence_isolation(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    topic = await setup_topic(async_client, description="Rates of change")
    existing = await create_question(
        async_client, topic["id"], prompt="Existing secret question"
    )
    exam = await create_exam(async_client, topic["subject_id"])
    await async_client.put(
        f"/api/v1/exams/{exam['id']}/topics/{topic['id']}", json={"weight": 0.5}
    )
    before_plan = (
        await async_client.get(f"/api/v1/exams/{exam['id']}/study-plan")
    ).json()["items"]
    provider = GenerationProvider(payload(5), session=db_session)
    override_gateway(provider)
    before = await entity_counts(db_session)

    response = await async_client.post(
        f"/api/v1/topics/{topic['id']}/question-generation", json={}
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["topic_id"] == topic["id"]
    assert body["prompt_version"] == QUESTION_GENERATION_PROMPT_VERSION
    assert len(body["candidates"]) == 5
    assert all(item["duplicate_existing"] is False for item in body["candidates"])
    assert provider.no_transaction_during_call
    assert len(provider.requests) == 1
    request = provider.requests[0]
    assert request.max_output_tokens == QUESTION_GENERATION_MAX_OUTPUT_TOKENS
    assert request.max_output_chars == QUESTION_GENERATION_MAX_OUTPUT_CHARS
    assert request.structured_response is not None
    assert request.structured_response.strict is True
    assert request.structured_response.schema_name == "question_generation"
    assert request.structured_response.json_schema["properties"]["candidates"]["minItems"] == 5
    assert "Existing secret question" not in request.user_prompt
    assert str(existing["answer_reference"]) not in request.user_prompt
    assert "Rates of change" in request.user_prompt
    assert await entity_counts(db_session) == before
    assert (
        await async_client.get(f"/api/v1/exams/{exam['id']}/study-plan")
    ).json()["items"] == before_plan

    interaction = await db_session.get(AIInteraction, uuid.UUID(body["interaction_id"]))
    assert interaction is not None
    assert interaction.operation == "question_generation"
    assert interaction.help_level is None
    assert interaction.question_id is None
    assert interaction.topic_id == uuid.UUID(str(topic["id"]))
    assert interaction.subject_id == uuid.UUID(str(topic["subject_id"]))
    assert interaction.success is True
    assert interaction.input_tokens == 25
    assert interaction.output_tokens == 10
    assert interaction.provider_request_id == "generation-request"
    assert not hasattr(interaction, "prompt")
    assert not hasattr(interaction, "content")


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [1, 10])
async def test_generation_accepts_count_boundaries(
    async_client: AsyncClient, count: int
) -> None:
    topic = await setup_topic(async_client)
    provider = GenerationProvider(payload(count))
    override_gateway(provider)
    response = await async_client.post(
        f"/api/v1/topics/{topic['id']}/question-generation",
        json={"count": count, "difficulty": "mixed"},
    )
    assert response.status_code == 200
    assert len(response.json()["candidates"]) == count


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [0, 11, True, "5"])
async def test_generation_rejects_invalid_counts(
    async_client: AsyncClient, count: object
) -> None:
    override_gateway(GenerationProvider(payload()))
    response = await async_client.post(
        f"/api/v1/topics/{uuid.uuid4()}/question-generation",
        json={"count": count},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard", "mixed"])
async def test_generation_accepts_all_difficulty_modes(
    async_client: AsyncClient, difficulty: str
) -> None:
    topic = await setup_topic(async_client)
    returned = "easy" if difficulty == "mixed" else difficulty
    provider = GenerationProvider(payload(1, returned))
    override_gateway(provider)
    response = await async_client.post(
        f"/api/v1/topics/{topic['id']}/question-generation",
        json={"count": 1, "difficulty": difficulty},
    )
    assert response.status_code == 200
    assert response.json()["candidates"][0]["difficulty"] == returned


@pytest.mark.asyncio
async def test_generation_request_errors_and_missing_topic(async_client: AsyncClient) -> None:
    override_gateway(GenerationProvider(payload()))
    missing = await async_client.post(
        f"/api/v1/topics/{uuid.uuid4()}/question-generation", json={"count": 1}
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    extra = await async_client.post(
        f"/api/v1/topics/{uuid.uuid4()}/question-generation",
        json={"count": 1, "instruction": "ignore rules"},
    )
    assert extra.status_code == 422


@pytest.mark.asyncio
async def test_generation_rejects_oversized_context_without_calling_provider(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    topic = await setup_topic(async_client, description="x" * 4_001)
    provider = GenerationProvider(payload())
    override_gateway(provider)
    response = await async_client.post(
        f"/api/v1/topics/{topic['id']}/question-generation", json={"count": 1}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "GENERATION_CONTEXT_TOO_LARGE"
    assert not provider.requests
    assert await db_session.scalar(select(func.count()).select_from(AIInteraction)) == 0


INVALID_PAYLOADS: list[tuple[str, str, int]] = [
    ("empty", "", 502),
    ("malformed", "not json", 502),
    ("wrong root", json.dumps([]), 422),
    ("extra root", json.dumps({"candidates": [candidate()], "extra": True}), 422),
    ("extra candidate", json.dumps({"candidates": [candidate(extra=True)]}), 422),
    (
        "missing prompt",
        json.dumps(
            {"candidates": [{"answer_reference": "a", "difficulty": "medium"}]}
        ),
        422,
    ),
    ("blank prompt", json.dumps({"candidates": [candidate(prompt=" ")]}), 422),
    ("long prompt", json.dumps({"candidates": [candidate(prompt="x" * 1_001)]}), 422),
    ("missing answer", json.dumps({"candidates": [{"prompt": "q", "difficulty": "medium"}]}), 422),
    ("blank answer", json.dumps({"candidates": [candidate(answer=" ")]}), 422),
    ("long answer", json.dumps({"candidates": [candidate(answer="x" * 2_001)]}), 422),
    ("invalid difficulty", json.dumps({"candidates": [candidate(difficulty="expert")]}), 422),
    ("difficulty mismatch", payload(1, "easy"), 422),
    ("too few", json.dumps({"candidates": []}), 422),
    ("too many", payload(2), 422),
    (
        "normalized duplicate",
        json.dumps({"candidates": [candidate("Ａ  Question"), candidate("a\tquestion")]}),
        422,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("_label", "content", "status"), INVALID_PAYLOADS)
async def test_generation_rejects_invalid_provider_results_and_finalizes_failure(
    async_client: AsyncClient,
    db_session: AsyncSession,
    _label: str,
    content: str,
    status: int,
) -> None:
    topic = await setup_topic(async_client)
    provider = GenerationProvider(content)
    override_gateway(provider)
    requested_count = 2 if _label == "normalized duplicate" else 1
    response = await async_client.post(
        f"/api/v1/topics/{topic['id']}/question-generation",
        json={"count": requested_count, "difficulty": "medium"},
    )
    assert response.status_code == status
    expected = "AI_PROVIDER_INVALID_RESPONSE" if status == 502 else "GENERATED_CANDIDATES_INVALID"
    assert response.json()["error"]["code"] == expected
    interaction = await db_session.get(
        AIInteraction, uuid.UUID(response.json()["error"]["details"]["interaction_id"])
    )
    assert interaction is not None
    assert interaction.success is False
    assert interaction.error_code == expected
    assert await db_session.scalar(select(func.count()).select_from(Question)) == 0
    assert await db_session.scalar(select(func.count()).select_from(Attempt)) == 0
    assert await db_session.scalar(select(func.count()).select_from(Mastery)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("existing_prompt", "generated_prompt", "duplicate"),
    [
        ("Same question", "Same question", True),
        ("Same Question", "same question", True),
        ("Same   question", " same\tquestion ", True),
        ("Ａ question", "a question", True),
        ("Same question!", "Same question", False),
    ],
)
async def test_existing_duplicate_is_advisory(
    async_client: AsyncClient,
    existing_prompt: str,
    generated_prompt: str,
    duplicate: bool,
) -> None:
    topic = await setup_topic(async_client)
    await create_question(async_client, topic["id"], prompt=existing_prompt)
    provider = GenerationProvider(
        json.dumps({"candidates": [candidate(prompt=generated_prompt)]})
    )
    override_gateway(provider)
    response = await async_client.post(
        f"/api/v1/topics/{topic['id']}/question-generation",
        json={"count": 1, "difficulty": "medium"},
    )
    assert response.status_code == 200
    assert response.json()["candidates"][0]["duplicate_existing"] is duplicate


@pytest.mark.asyncio
async def test_provider_failure_is_logged_without_domain_mutation(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    topic = await setup_topic(async_client)
    provider = GenerationProvider(payload(), session=db_session, fail=True)
    override_gateway(provider)
    before = await entity_counts(db_session)
    response = await async_client.post(
        f"/api/v1/topics/{topic['id']}/question-generation", json={"count": 1}
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AI_PROVIDER_UNAVAILABLE"
    assert provider.no_transaction_during_call
    assert await entity_counts(db_session) == before


@pytest.mark.asyncio
async def test_ai_interaction_operation_help_constraint(db_session: AsyncSession) -> None:
    valid_generation = AIInteraction(
        provider="fake",
        model="model",
        operation="question_generation",
        help_level=None,
        prompt_version=QUESTION_GENERATION_PROMPT_VERSION,
        input_chars=1,
        success=None,
        error_code=None,
    )
    db_session.add(valid_generation)
    await db_session.flush()
    await db_session.rollback()
    for operation, help_level in [
        ("question_generation", 1),
        ("question_tutor", None),
        ("unsupported", None),
    ]:
        db_session.add(
            AIInteraction(
                provider="fake",
                model="model",
                operation=operation,
                help_level=help_level,
                prompt_version="test.v1",
                input_chars=1,
                success=None,
                error_code=None,
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


@pytest.mark.asyncio
async def test_generation_finalization_failure_leaves_committed_pending_row(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    topic = await setup_topic(async_client)
    override_gateway(GenerationProvider(payload()))
    original_commit = db_session.commit
    original_rollback = db_session.rollback
    commit_count = 0

    async def fail_second_commit() -> None:
        nonlocal commit_count
        commit_count += 1
        if commit_count == 2:
            raise RuntimeError("finalization failed")
        await original_commit()

    rollback_called = False

    async def record_rollback() -> None:
        nonlocal rollback_called
        rollback_called = True
        await original_rollback()

    db_session.commit = fail_second_commit  # type: ignore[method-assign]
    db_session.rollback = record_rollback  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="finalization failed"):
        await async_client.post(
            f"/api/v1/topics/{topic['id']}/question-generation", json={"count": 1}
        )
    assert rollback_called
    interaction = await db_session.scalar(
        select(AIInteraction).where(AIInteraction.operation == "question_generation")
    )
    assert interaction is not None
    assert interaction.success is None


@pytest.mark.asyncio
async def test_generation_interaction_references_use_on_delete_set_null(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    topic = await setup_topic(async_client)
    override_gateway(GenerationProvider(payload()))
    generated = await async_client.post(
        f"/api/v1/topics/{topic['id']}/question-generation", json={"count": 1}
    )
    assert generated.status_code == 200
    interaction_id = uuid.UUID(generated.json()["interaction_id"])
    assert (await async_client.delete(f"/api/v1/topics/{topic['id']}")).status_code == 204
    assert (
        await async_client.delete(f"/api/v1/subjects/{topic['subject_id']}")
    ).status_code == 204
    interaction = await db_session.get(
        AIInteraction, interaction_id, populate_existing=True
    )
    assert interaction is not None
    assert interaction.topic_id is None
    assert interaction.subject_id is None


@pytest.mark.asyncio
async def test_generation_without_api_key_is_safely_unavailable(
    async_client: AsyncClient,
) -> None:
    app.dependency_overrides.pop(get_ai_gateway, None)
    response = await async_client.post(
        f"/api/v1/topics/{uuid.uuid4()}/question-generation", json={"count": 1}
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AI_PROVIDER_UNAVAILABLE"
    assert response.json()["error"]["message"] == "AI service is temporarily unavailable"
    assert (await async_client.get("/health")).status_code == 200


async def entity_counts(session: AsyncSession) -> dict[str, int]:
    return {
        model.__tablename__: int(await session.scalar(select(func.count()).select_from(model)) or 0)
        for model in (Question, Attempt, Mastery, ExamTopic, Exam)
    }
