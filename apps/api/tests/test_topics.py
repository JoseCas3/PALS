import uuid

import pytest
from httpx import AsyncClient

from tests.test_subjects import create_subject


@pytest.mark.asyncio
async def test_topic_crud_under_subject(async_client: AsyncClient) -> None:
    subject = await create_subject(async_client)
    created = await async_client.post(
        f"/api/v1/subjects/{subject['id']}/topics",
        json={"name": "  Derivatives  ", "description": "Rates of change"},
    )
    assert created.status_code == 201
    topic = created.json()
    assert topic["name"] == "Derivatives"
    assert topic["subject_id"] == subject["id"]

    listed = await async_client.get(f"/api/v1/subjects/{subject['id']}/topics")
    assert listed.status_code == 200
    assert listed.json() == [topic]

    retrieved = await async_client.get(f"/api/v1/topics/{topic['id']}")
    assert retrieved.status_code == 200
    updated = await async_client.patch(
        f"/api/v1/topics/{topic['id']}", json={"name": "Differentiation"}
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Differentiation"

    deleted = await async_client.delete(f"/api/v1/topics/{topic['id']}")
    assert deleted.status_code == 204


@pytest.mark.asyncio
async def test_topic_parent_and_resource_errors(async_client: AsyncClient) -> None:
    missing_parent = await async_client.post(
        f"/api/v1/subjects/{uuid.uuid4()}/topics", json={"name": "Orphan"}
    )
    assert missing_parent.status_code == 404

    missing_topic = await async_client.get(f"/api/v1/topics/{uuid.uuid4()}")
    assert missing_topic.status_code == 404

    blank = await async_client.post(
        f"/api/v1/subjects/{uuid.uuid4()}/topics", json={"name": " "}
    )
    assert blank.status_code == 422


@pytest.mark.asyncio
async def test_topic_delete_is_restricted_by_questions_and_learning_evidence(
    async_client: AsyncClient,
) -> None:
    subject = await create_subject(async_client)
    with_question = await async_client.post(
        f"/api/v1/subjects/{subject['id']}/topics", json={"name": "Unattempted"}
    )
    question = await async_client.post(
        f"/api/v1/topics/{with_question.json()['id']}/questions",
        json={"prompt": "Prompt", "answer_reference": "Answer"},
    )
    blocked = await async_client.delete(
        f"/api/v1/topics/{with_question.json()['id']}"
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "TOPIC_HAS_QUESTIONS"

    with_evidence = await async_client.post(
        f"/api/v1/subjects/{subject['id']}/topics", json={"name": "Attempted"}
    )
    attempted_question = await async_client.post(
        f"/api/v1/topics/{with_evidence.json()['id']}/questions",
        json={"prompt": "Prompt", "answer_reference": "Answer"},
    )
    await async_client.post(
        f"/api/v1/questions/{attempted_question.json()['id']}/attempts",
        json={
            "correct": True,
            "hints_used": 0,
            "solution_seen": False,
            "time_spent_seconds": 1,
        },
    )
    blocked = await async_client.delete(f"/api/v1/topics/{with_evidence.json()['id']}")
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "TOPIC_HAS_LEARNING_EVIDENCE"

    assert question.status_code == 201
