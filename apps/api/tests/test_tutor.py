from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts import (
    AIProviderUnavailable,
    AIRequest,
    ProviderResponse,
)
from app.ai.gateway import AIGateway, ResolvedAIGateway
from app.ai.prompts import (
    LEVEL_INSTRUCTIONS,
    TUTOR_PROMPT_VERSION,
    TutorHelpLevel,
    TutorPromptContext,
    build_question_tutor_prompt,
)
from app.api.dependencies import get_tutor_ai_gateway
from app.main import app
from app.models import AIInteraction, Attempt, ExamTopic, Mastery, Question, Topic
from tests.test_exam_topics import create_topic
from tests.test_questions import create_question
from tests.test_subjects import create_subject


class CapturingProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def __init__(
        self,
        *,
        response: ProviderResponse | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        self.response = response or ProviderResponse(
            "Consider the power rule.",
            "fake",
            "fake-model",
            input_tokens=11,
            output_tokens=6,
            provider_request_id="fake-request",
        )
        self.session = session
        self.requests: list[AIRequest] = []
        self.no_transaction_during_call = False

    async def generate(self, request: AIRequest) -> ProviderResponse:
        self.requests.append(request)
        self.no_transaction_during_call = (
            self.session is None or not self.session.in_transaction()
        )
        return self.response


class FailingProvider(CapturingProvider):
    async def generate(self, request: AIRequest) -> ProviderResponse:
        self.requests.append(request)
        self.no_transaction_during_call = (
            self.session is None or not self.session.in_transaction()
        )
        raise AIProviderUnavailable(self.provider_name, self.model_name)


def override_gateway(provider: CapturingProvider) -> None:
    app.dependency_overrides[get_tutor_ai_gateway] = lambda: ResolvedAIGateway(
        AIGateway(provider, 1)
    )


@pytest.mark.parametrize("level", list(TutorHelpLevel))
def test_prompt_contract_is_deterministic_and_enforces_each_level(
    level: TutorHelpLevel,
) -> None:
    context = TutorPromptContext(
        subject_name="Calculus",
        topic_name="Derivatives",
        topic_description="Rates of change",
        question_prompt="What is the derivative of x squared?",
        question_difficulty="medium",
        help_level=level,
        answer_reference="The trusted answer is 2x" if level >= 5 else None,
    )
    first = build_question_tutor_prompt(context)
    second = build_question_tutor_prompt(context)
    assert first == second
    assert first.version == TUTOR_PROMPT_VERSION
    assert LEVEL_INSTRUCTIONS[level] in first.system_prompt
    assert "untrusted academic data" in first.system_prompt
    assert "Do not fabricate" in first.system_prompt
    assert "plain text" in first.system_prompt
    assert first.user_prompt.index("Subject name") < first.user_prompt.index("Topic name")
    assert first.user_prompt.index("Topic name") < first.user_prompt.index("Question difficulty")
    assert "Calculus" in first.user_prompt
    assert "Derivatives" in first.user_prompt
    assert "Rates of change" in first.user_prompt
    assert "What is the derivative" in first.user_prompt
    assert "<QUESTION_PROMPT_DATA>" in first.user_prompt
    assert f"Requested help level: {int(level)}" in first.user_prompt
    if level <= TutorHelpLevel.FIRST_STEP:
        assert "TRUSTED_ANSWER_REFERENCE" not in first.user_prompt
        assert "The trusted answer is 2x" not in first.user_prompt
    else:
        assert "<TRUSTED_ANSWER_REFERENCE>" in first.user_prompt
        assert "The trusted answer is 2x" in first.user_prompt
    if level == TutorHelpLevel.GUIDED_SOLUTION:
        assert "do not state the final answer" in first.system_prompt
    if level == TutorHelpLevel.FULL_SOLUTION:
        assert "state the final answer" in first.system_prompt


@pytest.mark.asyncio
async def test_tutor_success_logs_metadata_and_changes_no_evidence(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    subject = await create_subject(async_client)
    topic = await create_topic(async_client, subject["id"], "Derivatives")
    question = await create_question(async_client, topic["id"])
    provider = CapturingProvider(session=db_session)
    override_gateway(provider)

    before_question = await db_session.get(Question, uuid.UUID(str(question["id"])))
    assert before_question is not None
    original_question = (
        before_question.prompt,
        before_question.answer_reference,
        before_question.difficulty,
    )
    response = await async_client.post(
        f"/api/v1/questions/{question['id']}/tutor", json={"help_level": 4}
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["content"] == "Consider the power rule."
    assert response.json()["prompt_version"] == TUTOR_PROMPT_VERSION
    assert provider.no_transaction_during_call
    assert len(provider.requests) == 1
    assert provider.requests[0].max_output_tokens == 800
    assert "2x" not in provider.requests[0].user_prompt
    assert "TRUSTED_ANSWER_REFERENCE" not in provider.requests[0].user_prompt

    interaction = await db_session.get(
        AIInteraction, uuid.UUID(response.json()["interaction_id"])
    )
    assert interaction is not None
    assert interaction.success is True
    assert interaction.output_chars == len("Consider the power rule.")
    assert interaction.input_tokens == 11
    assert interaction.output_tokens == 6
    assert interaction.provider_request_id == "fake-request"
    assert interaction.latency_ms is not None
    assert not hasattr(interaction, "prompt")
    assert not hasattr(interaction, "content")
    assert await db_session.scalar(select(func.count()).select_from(Attempt)) == 0
    assert await db_session.scalar(select(func.count()).select_from(Mastery)) == 0
    assert await db_session.scalar(select(func.count()).select_from(ExamTopic)) == 0
    current_question = await db_session.get(Question, uuid.UUID(str(question["id"])))
    assert current_question is not None
    assert (
        current_question.prompt,
        current_question.answer_reference,
        current_question.difficulty,
    ) == original_question


@pytest.mark.asyncio
async def test_tutor_failure_is_logged_and_changes_no_evidence(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    subject = await create_subject(async_client)
    topic = await create_topic(async_client, subject["id"], "Limits")
    question = await create_question(async_client, topic["id"])
    provider = FailingProvider(session=db_session)
    override_gateway(provider)

    response = await async_client.post(
        f"/api/v1/questions/{question['id']}/tutor", json={"help_level": 2}
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AI_PROVIDER_UNAVAILABLE"
    interaction_id = response.json()["error"]["details"]["interaction_id"]
    interaction = await db_session.get(AIInteraction, uuid.UUID(interaction_id))
    assert interaction is not None
    assert interaction.success is False
    assert interaction.error_code == "AI_PROVIDER_UNAVAILABLE"
    assert interaction.latency_ms is not None
    assert provider.no_transaction_during_call
    assert await db_session.scalar(select(func.count()).select_from(Attempt)) == 0
    assert await db_session.scalar(select(func.count()).select_from(Mastery)) == 0
    assert await db_session.scalar(select(func.count()).select_from(ExamTopic)) == 0


@pytest.mark.asyncio
async def test_tutor_validation_missing_question_and_context_limits(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    provider = CapturingProvider()
    override_gateway(provider)
    assert (
        await async_client.post(
            f"/api/v1/questions/{uuid.uuid4()}/tutor", json={"help_level": 1}
        )
    ).status_code == 404
    for level in (0, 7, "2"):
        response = await async_client.post(
            f"/api/v1/questions/{uuid.uuid4()}/tutor", json={"help_level": level}
        )
        assert response.status_code == 422

    subject = await create_subject(async_client)
    topic = await create_topic(async_client, subject["id"], "Large")
    question = await create_question(
        async_client, topic["id"], prompt="x" * 8_001
    )
    response = await async_client.post(
        f"/api/v1/questions/{question['id']}/tutor", json={"help_level": 1}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "TUTOR_CONTEXT_TOO_LARGE"
    assert not provider.requests
    assert await db_session.scalar(select(func.count()).select_from(AIInteraction)) == 0


@pytest.mark.asyncio
async def test_final_user_prompt_hard_guard_remains_active(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    subject = await create_subject(async_client)
    topic = await create_topic(async_client, subject["id"], "Large combined context")
    question = await create_question(async_client, topic["id"])
    topic_row = await db_session.get(Topic, uuid.UUID(str(topic["id"])))
    question_row = await db_session.get(Question, uuid.UUID(str(question["id"])))
    assert topic_row is not None and question_row is not None
    topic_row.description = "d" * 4_000
    question_row.prompt = "q" * 8_000
    question_row.answer_reference = "a" * 8_000
    await db_session.flush()
    provider = CapturingProvider()
    override_gateway(provider)

    response = await async_client.post(
        f"/api/v1/questions/{question['id']}/tutor", json={"help_level": 5}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "TUTOR_CONTEXT_TOO_LARGE"
    assert provider.requests == []


@pytest.mark.asyncio
async def test_tutor_level_five_includes_answer_reference(
    async_client: AsyncClient,
) -> None:
    subject = await create_subject(async_client)
    topic = await create_topic(async_client, subject["id"], "Derivatives")
    question = await create_question(async_client, topic["id"])
    provider = CapturingProvider()
    override_gateway(provider)
    response = await async_client.post(
        f"/api/v1/questions/{question['id']}/tutor", json={"help_level": 5}
    )
    assert response.status_code == 200
    assert "<TRUSTED_ANSWER_REFERENCE>" in provider.requests[0].user_prompt
    assert "2x" in provider.requests[0].user_prompt


@pytest.mark.asyncio
async def test_tutor_interaction_does_not_freeze_question_and_fk_is_set_null(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    subject = await create_subject(async_client)
    topic = await create_topic(async_client, subject["id"], "Derivatives")
    question = await create_question(async_client, topic["id"])
    override_gateway(CapturingProvider())
    tutored = await async_client.post(
        f"/api/v1/questions/{question['id']}/tutor", json={"help_level": 1}
    )
    assert tutored.status_code == 200
    assert (
        await async_client.delete(f"/api/v1/questions/{question['id']}")
    ).status_code == 204
    interaction = await db_session.get(
        AIInteraction, uuid.UUID(tutored.json()["interaction_id"]), populate_existing=True
    )
    assert interaction is not None
    assert interaction.question_id is None
    assert interaction.topic_id == uuid.UUID(str(topic["id"]))
    assert (await async_client.delete(f"/api/v1/topics/{topic['id']}")).status_code == 204
    assert (
        await async_client.delete(f"/api/v1/subjects/{subject['id']}")
    ).status_code == 204
    await db_session.refresh(interaction)
    assert interaction.topic_id is None
    assert interaction.subject_id is None


@pytest.mark.asyncio
async def test_success_finalization_failure_rolls_back_and_leaves_pending(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    subject = await create_subject(async_client)
    topic = await create_topic(async_client, subject["id"], "Derivatives")
    question = await create_question(async_client, topic["id"])
    override_gateway(CapturingProvider())
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
            f"/api/v1/questions/{question['id']}/tutor", json={"help_level": 1}
        )
    assert rollback_called
    interaction = await db_session.scalar(
        select(AIInteraction).where(AIInteraction.question_id == uuid.UUID(str(question["id"])))
    )
    assert interaction is not None
    assert interaction.success is None


@pytest.mark.asyncio
async def test_ai_interaction_database_state_constraint(db_session: AsyncSession) -> None:
    invalid = AIInteraction(
        provider="fake",
        model="model",
        operation="question_tutor",
        help_level=1,
        prompt_version=TUTOR_PROMPT_VERSION,
        input_chars=10,
        output_chars=None,
        latency_ms=None,
        success=True,
        error_code=None,
    )
    db_session.add(invalid)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_tutor_interaction_does_not_prevent_question_deletion(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    subject = await create_subject(async_client)
    topic = await create_topic(async_client, subject["id"], "Derivatives")
    question = await create_question(async_client, topic["id"])
    override_gateway(CapturingProvider())
    tutored = await async_client.post(
        f"/api/v1/questions/{question['id']}/tutor", json={"help_level": 1}
    )
    assert tutored.status_code == 200
    assert (
        await async_client.delete(f"/api/v1/questions/{question['id']}")
    ).status_code == 204
    interaction = await db_session.get(
        AIInteraction, uuid.UUID(tutored.json()["interaction_id"])
    )
    assert interaction is not None
    assert interaction.question_id is None


@pytest.mark.asyncio
async def test_tutor_without_api_key_is_safely_unavailable(
    async_client: AsyncClient,
) -> None:
    app.dependency_overrides.pop(get_tutor_ai_gateway, None)
    subject = await create_subject(async_client)
    topic = await create_topic(async_client, subject["id"], "Unavailable")
    question = await create_question(async_client, topic["id"])
    response = await async_client.post(
        f"/api/v1/questions/{question['id']}/tutor", json={"help_level": 1}
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AI_PROVIDER_UNAVAILABLE"
    assert (await async_client.get("/health")).status_code == 200
