import uuid

import pytest
from httpx import AsyncClient

from tests.test_subjects import create_subject


@pytest.mark.asyncio
async def test_exam_crud_normalizes_date_and_allows_history(async_client: AsyncClient) -> None:
    subject = await create_subject(async_client)
    created = await async_client.post(
        f"/api/v1/subjects/{subject['id']}/exams",
        json={
            "name": "  Midterm  ",
            "exam_date": "2020-02-03T09:30:00-06:00",
            "description": "Historical test",
        },
    )
    assert created.status_code == 201
    exam = created.json()
    assert exam["name"] == "Midterm"
    assert exam["exam_date"] == "2020-02-03T15:30:00Z"

    listed = await async_client.get(f"/api/v1/subjects/{subject['id']}/exams")
    assert listed.status_code == 200
    assert listed.json() == [exam]

    updated = await async_client.patch(
        f"/api/v1/exams/{exam['id']}", json={"description": None}
    )
    assert updated.status_code == 200
    assert updated.json()["description"] is None
    retrieved = await async_client.get(f"/api/v1/exams/{exam['id']}")
    assert retrieved.status_code == 200

    deleted = await async_client.delete(f"/api/v1/exams/{exam['id']}")
    assert deleted.status_code == 204


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exam_date", ["not-a-date", "2026-01-01T10:00:00", None]
)
async def test_exam_rejects_invalid_or_naive_dates(
    async_client: AsyncClient, exam_date: str | None
) -> None:
    subject = await create_subject(async_client)
    response = await async_client.post(
        f"/api/v1/subjects/{subject['id']}/exams",
        json={"name": "Final", "exam_date": exam_date},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_exam_missing_parent_and_resource(async_client: AsyncClient) -> None:
    missing_parent = await async_client.post(
        f"/api/v1/subjects/{uuid.uuid4()}/exams",
        json={"name": "Final", "exam_date": "2026-01-01T10:00:00Z"},
    )
    assert missing_parent.status_code == 404
    missing_exam = await async_client.get(f"/api/v1/exams/{uuid.uuid4()}")
    assert missing_exam.status_code == 404
