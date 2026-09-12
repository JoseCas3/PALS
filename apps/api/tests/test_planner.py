import uuid
from datetime import UTC, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import cast

import pytest
from httpx import AsyncClient
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_now
from app.main import app
from app.models import Attempt, Exam, ExamTopic, Mastery, Question
from app.services.planner import (
    EXAM_WEIGHT_FACTOR,
    MASTERY_FACTOR,
    URGENCY_FACTOR,
    PlannerReason,
    StudyPlanItem,
    build_reason,
    calculate_mastery_need,
    calculate_priority,
    calculate_urgency,
    calculate_weighted_contributions,
    sort_study_plan_items,
)
from tests.conftest import test_engine
from tests.test_exam_topics import create_topic
from tests.test_questions import create_question
from tests.test_subjects import create_subject

NOW = datetime(2026, 9, 11, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        ("0", "1.0000"),
        ("25", "0.7500"),
        ("50", "0.5000"),
        ("100", "0.0000"),
    ],
)
def test_mastery_need_boundaries(score: str, expected: str) -> None:
    assert calculate_mastery_need(Decimal(score)) == Decimal(expected)


@pytest.mark.parametrize("score", [Decimal("-0.01"), Decimal("100.01")])
def test_mastery_need_rejects_invalid_persisted_score(score: Decimal) -> None:
    with pytest.raises(ValueError, match="Persisted mastery score"):
        calculate_mastery_need(score)


@pytest.mark.parametrize(
    ("remaining", "expected"),
    [
        (timedelta(days=31), "0.0000"),
        (timedelta(days=30), "0.0000"),
        (timedelta(days=30) - timedelta(hours=1), "0.0014"),
        (timedelta(days=15), "0.5000"),
        (timedelta(days=7), "0.7667"),
        (timedelta(days=1), "0.9667"),
        (timedelta(0), "1.0000"),
        (-timedelta(microseconds=1), "1.0000"),
    ],
)
def test_urgency_boundaries(remaining: timedelta, expected: str) -> None:
    assert calculate_urgency(exam_date=NOW + remaining, generated_at=NOW) == Decimal(expected)


def test_urgency_uses_equivalent_timezone_instants() -> None:
    local_zone = timezone(timedelta(hours=-6))
    local_now = NOW.astimezone(local_zone)
    local_exam = (NOW + timedelta(days=15)).astimezone(local_zone)
    assert calculate_urgency(exam_date=local_exam, generated_at=local_now) == Decimal("0.5000")


@pytest.mark.parametrize(
    ("exam_date", "generated_at"),
    [(NOW.replace(tzinfo=None), NOW), (NOW, NOW.replace(tzinfo=None))],
)
def test_urgency_requires_aware_datetimes(exam_date: datetime, generated_at: datetime) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        calculate_urgency(exam_date=exam_date, generated_at=generated_at)


def test_priority_uses_exact_decimal_coefficients_and_rounding() -> None:
    assert (MASTERY_FACTOR, URGENCY_FACTOR, EXAM_WEIGHT_FACTOR) == (
        Decimal("0.50"),
        Decimal("0.30"),
        Decimal("0.20"),
    )
    assert calculate_priority(
        mastery_need=Decimal("0.6500"),
        urgency=Decimal("0.8000"),
        exam_weight=Decimal("0.4000"),
    ) == Decimal("0.6450")
    assert calculate_priority(
        mastery_need=Decimal("0.33335"),
        urgency=Decimal("0.0000"),
        exam_weight=Decimal("0.0001"),
    ) == Decimal("0.1667")


def test_fully_mastered_topic_can_have_nonzero_priority() -> None:
    assert calculate_priority(
        mastery_need=calculate_mastery_need(Decimal("100.00")),
        urgency=Decimal("0.8000"),
        exam_weight=Decimal("1.0000"),
    ) == Decimal("0.4400")


@pytest.mark.parametrize("weight", [Decimal("0"), Decimal("-0.1"), Decimal("1.1")])
def test_priority_rejects_invalid_persisted_weight(weight: Decimal) -> None:
    with pytest.raises(ValueError, match="Persisted ExamTopic weight"):
        calculate_priority(mastery_need=Decimal("0.5"), urgency=Decimal("0.5"), exam_weight=weight)


def test_weighted_contributions_are_exact() -> None:
    assert calculate_weighted_contributions(
        mastery_need=Decimal("0.8"),
        urgency=Decimal("0.8"),
        exam_weight=Decimal("0.5"),
    ) == (Decimal("0.400"), Decimal("0.240"), Decimal("0.100"))


@pytest.mark.parametrize(
    ("mastery_need", "urgency", "exam_weight", "summary"),
    [
        ("0.8", "0.5", "0.5", "Mastery need is the strongest contributor"),
        ("0.1", "1", "1", "Exam urgency is the strongest contributor"),
        ("0.1", "0.1", "1", "Exam weight is the strongest contributor"),
        ("0.24", "0.4", "0.6", "Mastery need is the strongest contributor"),
        ("0.1", "0.4", "0.6", "Exam urgency is the strongest contributor"),
    ],
)
def test_reason_winner_and_tie_precedence(
    mastery_need: str, urgency: str, exam_weight: str, summary: str
) -> None:
    reason = build_reason(
        mastery_need=Decimal(mastery_need),
        urgency=Decimal(urgency),
        exam_weight=Decimal(exam_weight),
    )
    assert reason.summary.startswith(summary)
    assert [factor.code for factor in reason.factors] == [
        "mastery_need",
        "urgency",
        "exam_weight",
    ]


def make_item(
    topic_id: str, *, priority: str, mastery: str, weight: str, summary: str = "reason"
) -> StudyPlanItem:
    return StudyPlanItem(
        topic_id=uuid.UUID(topic_id),
        topic_name=topic_id,
        mastery_score=Decimal(mastery),
        mastery_need=Decimal("0.5000"),
        urgency=Decimal("0.5000"),
        exam_weight=Decimal(weight).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        persisted_exam_weight=Decimal(weight),
        priority=Decimal(priority),
        reason=PlannerReason(summary=summary, factors=()),
    )


def test_ranking_uses_all_tie_breakers_and_ignores_reason() -> None:
    highest = make_item(
        "00000000-0000-0000-0000-000000000005", priority="0.9", mastery="90", weight="0.1"
    )
    lower_mastery = make_item(
        "00000000-0000-0000-0000-000000000004", priority="0.8", mastery="20", weight="0.2"
    )
    higher_weight = make_item(
        "00000000-0000-0000-0000-000000000003", priority="0.8", mastery="30", weight="0.9"
    )
    lower_uuid = make_item(
        "00000000-0000-0000-0000-000000000001",
        priority="0.8",
        mastery="30",
        weight="0.5",
        summary="z",
    )
    higher_uuid = make_item(
        "00000000-0000-0000-0000-000000000002",
        priority="0.8",
        mastery="30",
        weight="0.5",
        summary="a",
    )
    ordered = sort_study_plan_items(
        [higher_uuid, higher_weight, lower_mastery, highest, lower_uuid]
    )
    assert [item.topic_id for item in ordered] == [
        highest.topic_id,
        lower_mastery.topic_id,
        higher_weight.topic_id,
        lower_uuid.topic_id,
        higher_uuid.topic_id,
    ]


def test_ranking_uses_exact_persisted_weight_beyond_four_decimal_places() -> None:
    lower_exact_weight = make_item(
        "00000000-0000-0000-0000-000000000001",
        priority="0.8",
        mastery="30",
        weight="0.12345",
    )
    higher_exact_weight = make_item(
        "00000000-0000-0000-0000-000000000002",
        priority="0.8",
        mastery="30",
        weight="0.12346",
    )

    assert lower_exact_weight.exam_weight == higher_exact_weight.exam_weight == Decimal("0.1235")
    assert sort_study_plan_items([lower_exact_weight, higher_exact_weight]) == [
        higher_exact_weight,
        lower_exact_weight,
    ]


async def create_exam_at(
    client: AsyncClient, subject_id: object, when: datetime
) -> dict[str, object]:
    response = await client.post(
        f"/api/v1/subjects/{subject_id}/exams",
        json={"name": "Final", "exam_date": when.isoformat()},
    )
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


def freeze_now() -> None:
    app.dependency_overrides[utc_now] = lambda: NOW


@pytest.mark.asyncio
async def test_study_plan_response_ranking_shape_and_read_only_integrity(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    freeze_now()
    subject = await create_subject(async_client)
    zero_topic = await create_topic(async_client, subject["id"], "Zero mastery")
    practiced_topic = await create_topic(async_client, subject["id"], "Practiced")
    exam = await create_exam_at(async_client, subject["id"], NOW + timedelta(days=15))
    await async_client.put(
        f"/api/v1/exams/{exam['id']}/topics/{zero_topic['id']}", json={"weight": 0.5}
    )
    await async_client.put(
        f"/api/v1/exams/{exam['id']}/topics/{practiced_topic['id']}", json={"weight": 1}
    )
    question = await create_question(async_client, practiced_topic["id"], difficulty="hard")
    await async_client.post(
        f"/api/v1/questions/{question['id']}/attempts",
        json={
            "correct": True,
            "hints_used": 0,
            "solution_seen": False,
            "time_spent_seconds": 30,
        },
    )

    before = {
        "mastery": await db_session.scalar(select(func.count()).select_from(Mastery)),
        "attempts": await db_session.scalar(select(func.count()).select_from(Attempt)),
        "questions": await db_session.scalar(select(func.count()).select_from(Question)),
        "links": await db_session.scalar(select(func.count()).select_from(ExamTopic)),
        "exams": await db_session.scalar(select(func.count()).select_from(Exam)),
    }

    response = await async_client.get(f"/api/v1/exams/{exam['id']}/study-plan")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    payload = response.json()
    assert payload["exam_id"] == exam["id"]
    assert payload["exam_name"] == "Final"
    assert payload["generated_at"] == "2026-09-11T12:00:00Z"
    assert [item["topic_name"] for item in payload["items"]] == [
        "Practiced",
        "Zero mastery",
    ]
    assert payload["items"][0] == {
        "topic_id": practiced_topic["id"],
        "topic_name": "Practiced",
        "mastery_score": "10.00",
        "mastery_need": "0.9000",
        "urgency": "0.5000",
        "exam_weight": "1.0000",
        "priority": "0.8000",
        "reason": {
            "summary": "Mastery need is the strongest contributor to this priority.",
            "factors": [
                {"code": "mastery_need", "value": "0.9000", "formula_weight": "0.5000"},
                {"code": "urgency", "value": "0.5000", "formula_weight": "0.3000"},
                {"code": "exam_weight", "value": "1.0000", "formula_weight": "0.2000"},
            ],
        },
    }
    assert payload["items"][1]["mastery_score"] == "0.00"
    assert payload["items"][1]["mastery_need"] == "1.0000"

    after = {
        "mastery": await db_session.scalar(select(func.count()).select_from(Mastery)),
        "attempts": await db_session.scalar(select(func.count()).select_from(Attempt)),
        "questions": await db_session.scalar(select(func.count()).select_from(Question)),
        "links": await db_session.scalar(select(func.count()).select_from(ExamTopic)),
        "exams": await db_session.scalar(select(func.count()).select_from(Exam)),
    }
    assert await db_session.get(Mastery, uuid.UUID(str(zero_topic["id"]))) is None
    assert after == before


@pytest.mark.asyncio
async def test_study_plan_normalizes_top_level_weight_half_up_and_ranks_by_exact_weight(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    freeze_now()
    subject = await create_subject(async_client)
    topics = [
        await create_topic(async_client, subject["id"], "Below half"),
        await create_topic(async_client, subject["id"], "Half"),
        await create_topic(async_client, subject["id"], "Above half"),
    ]
    exam = await create_exam_at(async_client, subject["id"], NOW + timedelta(days=15))
    weights = (Decimal("0.12344"), Decimal("0.12345"), Decimal("0.12346"))
    for topic, weight in zip(topics, weights, strict=True):
        response = await async_client.put(
            f"/api/v1/exams/{exam['id']}/topics/{topic['id']}", json={"weight": 0.1}
        )
        assert response.status_code == 200
        link = await db_session.get(
            ExamTopic,
            (uuid.UUID(str(exam["id"])), uuid.UUID(str(topic["id"]))),
        )
        assert link is not None
        link.weight = weight
    await db_session.flush()

    response = await async_client.get(f"/api/v1/exams/{exam['id']}/study-plan")

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["topic_name"] for item in items] == ["Above half", "Half", "Below half"]
    assert {item["topic_name"]: item["exam_weight"] for item in items} == {
        "Below half": "0.1234",
        "Half": "0.1235",
        "Above half": "0.1235",
    }


@pytest.mark.asyncio
async def test_study_plan_errors_exact_time_and_empty_exam(async_client: AsyncClient) -> None:
    freeze_now()
    subject = await create_subject(async_client)
    exact = await create_exam_at(async_client, subject["id"], NOW)
    exact_response = await async_client.get(f"/api/v1/exams/{exact['id']}/study-plan")
    assert exact_response.status_code == 200
    assert exact_response.json()["items"] == []

    past = await create_exam_at(async_client, subject["id"], NOW - timedelta(microseconds=1))
    past_response = await async_client.get(f"/api/v1/exams/{past['id']}/study-plan")
    assert past_response.status_code == 409
    assert past_response.json() == {
        "error": {
            "code": "EXAM_ALREADY_PASSED",
            "message": "Study plans cannot be generated for a past exam",
            "details": None,
        }
    }
    assert (await async_client.get(f"/api/v1/exams/{uuid.uuid4()}/study-plan")).status_code == 404
    invalid = await async_client.get("/api/v1/exams/not-a-uuid/study-plan")
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_planner_query_count_is_constant(async_client: AsyncClient) -> None:
    freeze_now()
    subject = await create_subject(async_client)
    exam = await create_exam_at(async_client, subject["id"], NOW + timedelta(days=10))
    counts: list[int] = []

    def count_selects(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: object,
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            counts.append(1)

    event.listen(test_engine.sync_engine, "before_cursor_execute", count_selects)
    try:
        await async_client.get(f"/api/v1/exams/{exam['id']}/study-plan")
        empty_count = len(counts)
        counts.clear()
        for index in range(3):
            topic = await create_topic(async_client, subject["id"], f"Topic {index}")
            await async_client.put(
                f"/api/v1/exams/{exam['id']}/topics/{topic['id']}", json={"weight": 0.5}
            )
        counts.clear()
        await async_client.get(f"/api/v1/exams/{exam['id']}/study-plan")
        populated_count = len(counts)
    finally:
        event.remove(test_engine.sync_engine, "before_cursor_execute", count_selects)
    assert empty_count == populated_count == 2
