import uuid
from typing import cast

import pytest
from httpx import AsyncClient


async def create_subject(client: AsyncClient, name: str = "Calculus") -> dict[str, object]:
    response = await client.post(
        "/api/v1/subjects", json={"name": name, "description": "Limits and derivatives"}
    )
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


@pytest.mark.asyncio
async def test_subject_crud_and_name_trimming(async_client: AsyncClient) -> None:
    subject = await create_subject(async_client, "  Calculus  ")
    assert subject["name"] == "Calculus"

    listed = await async_client.get("/api/v1/subjects")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [subject["id"]]

    retrieved = await async_client.get(f"/api/v1/subjects/{subject['id']}")
    assert retrieved.status_code == 200

    updated = await async_client.patch(
        f"/api/v1/subjects/{subject['id']}",
        json={"name": "Advanced Calculus", "description": None},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Advanced Calculus"
    assert updated.json()["description"] is None

    deleted = await async_client.delete(f"/api/v1/subjects/{subject['id']}")
    assert deleted.status_code == 204
    assert deleted.content == b""


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{"name": "   "}, {"name": None}, {}])
async def test_subject_validation_uses_error_envelope(
    async_client: AsyncClient, payload: dict[str, object]
) -> None:
    response = await async_client.post("/api/v1/subjects", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_missing_and_invalid_subject_ids(async_client: AsyncClient) -> None:
    missing = await async_client.get(f"/api/v1/subjects/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json() == {
        "error": {"code": "RESOURCE_NOT_FOUND", "message": "Subject not found", "details": None}
    }

    invalid = await async_client.get("/api/v1/subjects/not-a-uuid")
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_subject_delete_is_restricted_by_topics_and_exams(
    async_client: AsyncClient,
) -> None:
    with_topic = await create_subject(async_client, "Physics")
    topic = await async_client.post(
        f"/api/v1/subjects/{with_topic['id']}/topics", json={"name": "Motion"}
    )
    assert topic.status_code == 201
    conflict = await async_client.delete(f"/api/v1/subjects/{with_topic['id']}")
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "SUBJECT_HAS_TOPICS"

    with_exam = await create_subject(async_client, "History")
    exam = await async_client.post(
        f"/api/v1/subjects/{with_exam['id']}/exams",
        json={"name": "Final", "exam_date": "2025-01-01T09:00:00-06:00"},
    )
    assert exam.status_code == 201
    conflict = await async_client.delete(f"/api/v1/subjects/{with_exam['id']}")
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "SUBJECT_HAS_EXAMS"
