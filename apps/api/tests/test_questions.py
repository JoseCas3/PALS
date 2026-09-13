import uuid
from typing import cast

import pytest
from httpx import AsyncClient

from tests.test_exam_topics import create_topic
from tests.test_subjects import create_subject


async def create_question(
    client: AsyncClient,
    topic_id: object,
    *,
    prompt: str = "What is the derivative of x squared?",
    difficulty: str = "medium",
) -> dict[str, object]:
    response = await client.post(
        f"/api/v1/topics/{topic_id}/questions",
        json={
            "prompt": prompt,
            "answer_reference": "2x",
            "difficulty": difficulty,
        },
    )
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


@pytest.mark.asyncio
async def test_question_crud_and_deterministic_listing(async_client: AsyncClient) -> None:
    subject = await create_subject(async_client)
    topic = await create_topic(async_client, subject["id"], "Derivatives")
    first = await create_question(async_client, topic["id"], prompt="  First question  ")
    second = await create_question(
        async_client, topic["id"], prompt="Second question", difficulty="hard"
    )
    assert first["prompt"] == "First question"
    assert first["difficulty"] == "medium"

    listed = await async_client.get(f"/api/v1/topics/{topic['id']}/questions")
    assert listed.status_code == 200
    expected_ids = sorted([str(first["id"]), str(second["id"])])
    assert [item["id"] for item in listed.json()] == expected_ids

    retrieved = await async_client.get(f"/api/v1/questions/{first['id']}")
    assert retrieved.status_code == 200
    updated = await async_client.patch(
        f"/api/v1/questions/{first['id']}",
        json={"prompt": "Updated", "answer_reference": "Updated answer", "difficulty": "easy"},
    )
    assert updated.status_code == 200
    assert updated.json()["difficulty"] == "easy"

    deleted = await async_client.delete(f"/api/v1/questions/{first['id']}")
    assert deleted.status_code == 204


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"prompt": " ", "answer_reference": "answer", "difficulty": "easy"},
        {"prompt": "prompt", "answer_reference": " ", "difficulty": "easy"},
        {"prompt": "prompt", "answer_reference": "answer", "difficulty": "expert"},
        {"prompt": "prompt", "answer_reference": "answer", "difficulty": None},
    ],
)
async def test_question_validation(
    async_client: AsyncClient, payload: dict[str, object]
) -> None:
    subject = await create_subject(async_client)
    topic = await create_topic(async_client, subject["id"], "Limits")
    response = await async_client.post(
        f"/api/v1/topics/{topic['id']}/questions", json=payload
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["prompt", "answer_reference"])
async def test_question_rejects_nul_before_persistence(
    async_client: AsyncClient, field: str
) -> None:
    subject = await create_subject(async_client)
    topic = await create_topic(async_client, subject["id"], "Limits")
    payload = {
        "prompt": "Private prompt",
        "answer_reference": "Private reference",
        "difficulty": "medium",
    }
    payload[field] += "\x00hidden"

    response = await async_client.post(
        f"/api/v1/topics/{topic['id']}/questions", json=payload
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    listed = await async_client.get(f"/api/v1/topics/{topic['id']}/questions")
    assert listed.json() == []


@pytest.mark.asyncio
async def test_question_missing_resources(async_client: AsyncClient) -> None:
    missing_topic = await async_client.post(
        f"/api/v1/topics/{uuid.uuid4()}/questions",
        json={"prompt": "Question", "answer_reference": "Answer"},
    )
    assert missing_topic.status_code == 404
    assert (await async_client.get(f"/api/v1/questions/{uuid.uuid4()}")).status_code == 404


@pytest.mark.asyncio
async def test_question_becomes_immutable_after_attempt(async_client: AsyncClient) -> None:
    subject = await create_subject(async_client)
    topic = await create_topic(async_client, subject["id"], "Limits")
    question = await create_question(async_client, topic["id"])
    attempt = await async_client.post(
        f"/api/v1/questions/{question['id']}/attempts",
        json={
            "correct": True,
            "hints_used": 0,
            "solution_seen": False,
            "time_spent_seconds": 10,
        },
    )
    assert attempt.status_code == 201

    patched = await async_client.patch(
        f"/api/v1/questions/{question['id']}", json={"prompt": "Changed"}
    )
    assert patched.status_code == 409
    assert patched.json()["error"]["code"] == "QUESTION_HAS_ATTEMPTS"
    deleted = await async_client.delete(f"/api/v1/questions/{question['id']}")
    assert deleted.status_code == 409
    assert deleted.json()["error"]["code"] == "QUESTION_HAS_ATTEMPTS"
