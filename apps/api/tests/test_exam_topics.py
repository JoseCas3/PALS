import uuid
from typing import cast

import pytest
from httpx import AsyncClient

from tests.test_subjects import create_subject


async def create_topic(client: AsyncClient, subject_id: object, name: str) -> dict[str, object]:
    response = await client.post(
        f"/api/v1/subjects/{subject_id}/topics", json={"name": name}
    )
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


async def create_exam(client: AsyncClient, subject_id: object) -> dict[str, object]:
    response = await client.post(
        f"/api/v1/subjects/{subject_id}/exams",
        json={"name": "Final", "exam_date": "2026-12-01T09:00:00Z"},
    )
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


@pytest.mark.asyncio
async def test_exam_topic_put_is_idempotent_and_updates_weight(
    async_client: AsyncClient,
) -> None:
    subject = await create_subject(async_client)
    topic = await create_topic(async_client, subject["id"], "Limits")
    exam = await create_exam(async_client, subject["id"])
    url = f"/api/v1/exams/{exam['id']}/topics/{topic['id']}"

    created = await async_client.put(url, json={"weight": 0.25})
    assert created.status_code == 200
    updated = await async_client.put(url, json={"weight": 0.75})
    assert updated.status_code == 200
    assert updated.json()["weight"] == 0.75

    listed = await async_client.get(f"/api/v1/exams/{exam['id']}/topics")
    assert listed.status_code == 200
    assert listed.json() == [updated.json()]

    removed = await async_client.delete(url)
    assert removed.status_code == 204
    assert (await async_client.get(f"/api/v1/topics/{topic['id']}")).status_code == 200
    assert (await async_client.delete(url)).status_code == 404


@pytest.mark.asyncio
async def test_exam_topic_rejects_cross_subject_and_invalid_weight(
    async_client: AsyncClient,
) -> None:
    first = await create_subject(async_client, "First")
    second = await create_subject(async_client, "Second")
    exam = await create_exam(async_client, first["id"])
    topic = await create_topic(async_client, second["id"], "Other")
    url = f"/api/v1/exams/{exam['id']}/topics/{topic['id']}"

    conflict = await async_client.put(url, json={"weight": 0.5})
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "CROSS_SUBJECT_EXAM_TOPIC"

    for invalid_weight in (0, -0.1, 1.1):
        invalid = await async_client.put(url, json={"weight": invalid_weight})
        assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_exam_topic_missing_resources(async_client: AsyncClient) -> None:
    subject = await create_subject(async_client)
    exam = await create_exam(async_client, subject["id"])
    topic = await create_topic(async_client, subject["id"], "Limits")

    missing_exam = await async_client.put(
        f"/api/v1/exams/{uuid.uuid4()}/topics/{topic['id']}", json={"weight": 0.5}
    )
    assert missing_exam.status_code == 404
    missing_topic = await async_client.put(
        f"/api/v1/exams/{exam['id']}/topics/{uuid.uuid4()}", json={"weight": 0.5}
    )
    assert missing_topic.status_code == 404


@pytest.mark.asyncio
async def test_topic_delete_is_restricted_and_exam_delete_cascades_only_link(
    async_client: AsyncClient,
) -> None:
    subject = await create_subject(async_client)
    exam = await create_exam(async_client, subject["id"])
    topic = await create_topic(async_client, subject["id"], "Limits")
    link = f"/api/v1/exams/{exam['id']}/topics/{topic['id']}"
    assert (await async_client.put(link, json={"weight": 1})).status_code == 200

    blocked = await async_client.delete(f"/api/v1/topics/{topic['id']}")
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "TOPIC_HAS_EXAMS"

    assert (await async_client.delete(f"/api/v1/exams/{exam['id']}")).status_code == 204
    assert (await async_client.get(f"/api/v1/topics/{topic['id']}")).status_code == 200
