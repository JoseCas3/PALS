import logging
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import DBAPIError

from app.services.attempts import AttemptService
from tests.test_exam_topics import create_topic
from tests.test_questions import create_question
from tests.test_subjects import create_subject

ATTEMPT = {
    "correct": True,
    "hints_used": 1,
    "solution_seen": False,
    "time_spent_seconds": 45,
}


@pytest.mark.asyncio
async def test_attempt_creation_returns_attempt_and_mastery_and_lists_history(
    async_client: AsyncClient,
) -> None:
    subject = await create_subject(async_client)
    topic = await create_topic(async_client, subject["id"], "Limits")
    question = await create_question(async_client, topic["id"])

    first = await async_client.post(
        f"/api/v1/questions/{question['id']}/attempts", json=ATTEMPT
    )
    assert first.status_code == 201
    assert first.json()["attempt"]["hints_used"] == 1
    assert first.json()["mastery"]["score"] == "6.40"

    second = await async_client.post(
        f"/api/v1/questions/{question['id']}/attempts",
        json={**ATTEMPT, "correct": False, "solution_seen": True, "hints_used": 2},
    )
    assert second.status_code == 201
    assert second.json()["attempt"]["hints_used"] == 2
    assert second.json()["attempt"]["solution_seen"] is True
    assert second.json()["mastery"]["score"] == "5.90"

    history = await async_client.get(f"/api/v1/questions/{question['id']}/attempts")
    assert history.status_code == 200
    expected_ids = sorted(
        [first.json()["attempt"]["id"], second.json()["attempt"]["id"]], reverse=True
    )
    assert [item["id"] for item in history.json()] == expected_ids


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {**ATTEMPT, "hints_used": -1},
        {**ATTEMPT, "hints_used": 4},
        {**ATTEMPT, "time_spent_seconds": -1},
        {key: value for key, value in ATTEMPT.items() if key != "correct"},
        {key: value for key, value in ATTEMPT.items() if key != "solution_seen"},
        {key: value for key, value in ATTEMPT.items() if key != "hints_used"},
        {key: value for key, value in ATTEMPT.items() if key != "time_spent_seconds"},
    ],
)
async def test_attempt_validation(
    async_client: AsyncClient, payload: dict[str, object]
) -> None:
    subject = await create_subject(async_client)
    topic = await create_topic(async_client, subject["id"], "Limits")
    question = await create_question(async_client, topic["id"])
    response = await async_client.post(
        f"/api/v1/questions/{question['id']}/attempts", json=payload
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_attempt_missing_question(async_client: AsyncClient) -> None:
    response = await async_client.post(
        f"/api/v1/questions/{uuid.uuid4()}/attempts", json=ATTEMPT
    )
    assert response.status_code == 404
    assert (
        await async_client.get(f"/api/v1/questions/{uuid.uuid4()}/attempts")
    ).status_code == 404


@pytest.mark.asyncio
async def test_attempt_rejects_postgresql_integer_overflow(async_client: AsyncClient) -> None:
    subject = await create_subject(async_client)
    topic = await create_topic(async_client, subject["id"], "Limits")
    question = await create_question(async_client, topic["id"])

    response = await async_client.post(
        f"/api/v1/questions/{question['id']}/attempts",
        json={**ATTEMPT, "time_spent_seconds": 2_147_483_648},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_unexpected_database_failure_is_safe_for_clients_and_logs(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    private_prompt = "PRIVATE_QUESTION_PROMPT"
    private_reference = "PRIVATE_ANSWER_REFERENCE"

    async def fail_record(*_: object, **__: object) -> object:
        raise DBAPIError(
            "INSERT INTO questions (prompt, answer_reference) VALUES ($1, $2)",
            (private_prompt, private_reference),
            RuntimeError("database rejected private academic text"),
            False,
        )

    monkeypatch.setattr(AttemptService, "record", fail_record)
    caplog.set_level(logging.ERROR, logger="app.core.errors")

    response = await async_client.post(
        f"/api/v1/questions/{uuid.uuid4()}/attempts", json=ATTEMPT
    )

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "DATABASE_ERROR",
            "message": "A database operation failed",
            "details": None,
        }
    }
    assert private_prompt not in response.text
    assert private_reference not in response.text
    assert private_prompt not in caplog.text
    assert private_reference not in caplog.text
