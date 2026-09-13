import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast

import pytest
from httpx import AsyncClient
from sqlalchemy import Table, event, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.adapters.openai import OpenAIProvider
from app.core.clock import utc_now
from app.main import app
from app.models import AIInteraction, Attempt, Exam, ExamTopic, Mastery, Question, Subject, Topic
from app.services.planner import (
    GlobalStudyPlanItem,
    PlannerReason,
    score_study_plan_item,
    sort_global_study_plan_items,
)
from tests.conftest import test_engine

NOW = datetime(2026, 9, 12, 15, tzinfo=UTC)


def fixed_uuid(value: int) -> uuid.UUID:
    return uuid.UUID(int=value)


async def add_obligation(
    session: AsyncSession,
    *,
    subject_id: uuid.UUID,
    subject_name: str,
    exam_id: uuid.UUID,
    exam_name: str,
    exam_date: datetime,
    topic_id: uuid.UUID,
    topic_name: str,
    weight: Decimal,
    mastery: Decimal | None = None,
) -> None:
    if await session.get(Subject, subject_id) is None:
        session.add(Subject(id=subject_id, name=subject_name))
    if await session.get(Topic, topic_id) is None:
        session.add(Topic(id=topic_id, subject_id=subject_id, name=topic_name))
    if await session.get(Exam, exam_id) is None:
        session.add(
            Exam(
                id=exam_id,
                subject_id=subject_id,
                name=exam_name,
                exam_date=exam_date,
            )
        )
    await session.flush()
    session.add(ExamTopic(exam_id=exam_id, topic_id=topic_id, weight=weight))
    if mastery is not None and await session.get(Mastery, topic_id) is None:
        session.add(Mastery(topic_id=topic_id, score=mastery))
    await session.flush()


def freeze_now() -> None:
    app.dependency_overrides[utc_now] = lambda: NOW


@pytest.mark.asyncio
async def test_global_plan_empty_states_past_filter_and_exact_now_boundary(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    freeze_now()
    empty = await async_client.get("/api/v1/study-plan")
    assert empty.status_code == 200
    assert empty.headers["cache-control"] == "no-store"
    assert empty.json() == {"generated_at": "2026-09-12T15:00:00Z", "items": []}

    subject = Subject(id=fixed_uuid(1), name="Calculus")
    db_session.add(subject)
    await db_session.flush()
    db_session.add_all(
        [
            Exam(
                id=fixed_uuid(10),
                subject_id=subject.id,
                name="Empty future",
                exam_date=NOW + timedelta(days=1),
            ),
            Exam(
                id=fixed_uuid(11),
                subject_id=subject.id,
                name="Past",
                exam_date=NOW - timedelta(microseconds=1),
            ),
        ]
    )
    await db_session.flush()
    topic = Topic(id=fixed_uuid(20), subject_id=subject.id, name="Limits")
    db_session.add(topic)
    await db_session.flush()
    db_session.add(ExamTopic(exam_id=fixed_uuid(11), topic_id=topic.id, weight=Decimal("1")))
    await db_session.flush()

    still_empty = await async_client.get("/api/v1/study-plan")
    assert still_empty.json()["items"] == []

    exact_exam = Exam(
        id=fixed_uuid(12), subject_id=subject.id, name="Now", exam_date=NOW
    )
    db_session.add(exact_exam)
    await db_session.flush()
    db_session.add(ExamTopic(exam_id=exact_exam.id, topic_id=topic.id, weight=Decimal("0.5")))
    await db_session.flush()

    exact = await async_client.get("/api/v1/study-plan")
    assert [item["exam_name"] for item in exact.json()["items"]] == ["Now"]
    assert exact.json()["items"][0]["urgency"] == "1.0000"


@pytest.mark.asyncio
async def test_global_plan_cross_exam_ranking_duplicate_topic_and_mastery_contracts(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    freeze_now()
    first_subject = fixed_uuid(100)
    second_subject = fixed_uuid(200)
    shared_topic = fixed_uuid(300)

    # Low mastery and a distant Exam beats high mastery and a near Exam.
    await add_obligation(
        db_session,
        subject_id=first_subject,
        subject_name="Calculus",
        exam_id=fixed_uuid(1000),
        exam_name="Distant",
        exam_date=NOW + timedelta(days=60),
        topic_id=shared_topic,
        topic_name="Derivatives",
        weight=Decimal("0.5"),
    )
    # The same Topic is a separate obligation in another Exam.
    await add_obligation(
        db_session,
        subject_id=first_subject,
        subject_name="Calculus",
        exam_id=fixed_uuid(1001),
        exam_name="Near",
        exam_date=NOW + timedelta(days=1),
        topic_id=shared_topic,
        topic_name="Derivatives",
        weight=Decimal("0.5"),
    )
    high_mastery_topic = fixed_uuid(301)
    await add_obligation(
        db_session,
        subject_id=first_subject,
        subject_name="Calculus",
        exam_id=fixed_uuid(1002),
        exam_name="Near mastered",
        exam_date=NOW + timedelta(days=1),
        topic_id=high_mastery_topic,
        topic_name="Integrals",
        weight=Decimal("0.5"),
        mastery=Decimal("80.00"),
    )
    fully_mastered_topic = fixed_uuid(302)
    await add_obligation(
        db_session,
        subject_id=second_subject,
        subject_name="Physics",
        exam_id=fixed_uuid(2000),
        exam_name="Final",
        exam_date=NOW + timedelta(days=15),
        topic_id=fully_mastered_topic,
        topic_name="Motion",
        weight=Decimal("1"),
        mastery=Decimal("100.00"),
    )

    response = await async_client.get("/api/v1/study-plan")
    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["exam_name"] == "Near"
    assert items[1]["exam_name"] == "Distant"
    assert items[0]["topic_id"] == items[1]["topic_id"] == str(shared_topic)
    assert items[2]["exam_name"] == "Near mastered"
    mastered = next(item for item in items if item["topic_id"] == str(fully_mastered_topic))
    assert mastered["subject_name"] == "Physics"
    assert mastered["mastery_score"] == "100.00"
    assert mastered["mastery_need"] == "0.0000"
    assert await db_session.get(Mastery, shared_topic) is None


@pytest.mark.asyncio
async def test_global_plan_weight_ranking_and_formula_parity(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    freeze_now()
    subject_id = fixed_uuid(400)
    exam_id = fixed_uuid(4000)
    low_topic = fixed_uuid(401)
    high_topic = fixed_uuid(402)
    for topic_id, name, weight in (
        (low_topic, "Low weight", Decimal("0.12345")),
        (high_topic, "High weight", Decimal("0.12346")),
    ):
        await add_obligation(
            db_session,
            subject_id=subject_id,
            subject_name="Chemistry",
            exam_id=exam_id,
            exam_name="Midterm",
            exam_date=NOW + timedelta(days=15),
            topic_id=topic_id,
            topic_name=name,
            weight=weight,
            mastery=Decimal("40.00"),
        )

    global_response = await async_client.get("/api/v1/study-plan")
    exam_response = await async_client.get(f"/api/v1/exams/{exam_id}/study-plan")
    assert [item["topic_name"] for item in global_response.json()["items"]] == [
        "High weight",
        "Low weight",
    ]
    global_item = next(
        item for item in global_response.json()["items"] if item["topic_id"] == str(low_topic)
    )
    exam_item = next(
        item for item in exam_response.json()["items"] if item["topic_id"] == str(low_topic)
    )
    for field in (
        "mastery_score",
        "mastery_need",
        "urgency",
        "exam_weight",
        "priority",
        "reason",
    ):
        assert global_item[field] == exam_item[field]


def global_item(
    *, exam_id: int, topic_id: int, date: datetime = NOW, weight: str = "0.5"
) -> GlobalStudyPlanItem:
    score = score_study_plan_item(
        mastery_score=Decimal("40.00"),
        exam_date=date,
        exam_weight=Decimal(weight),
        generated_at=NOW,
    )
    return GlobalStudyPlanItem(
        subject_id=fixed_uuid(exam_id + 10_000),
        subject_name="Subject",
        exam_id=fixed_uuid(exam_id),
        exam_name="Exam",
        exam_date=date,
        topic_id=fixed_uuid(topic_id),
        topic_name="Topic",
        **score.__dict__,
    )


def test_global_sort_is_stable_and_ignores_names_reasons_and_input_order() -> None:
    first = global_item(exam_id=1, topic_id=2)
    second = global_item(exam_id=1, topic_id=3)
    later_exam = global_item(exam_id=2, topic_id=1, date=NOW + timedelta(days=1))
    renamed = replace(
        first,
        subject_name="Z",
        exam_name="Z",
        topic_name="Z",
        reason=PlannerReason(summary="Z", factors=()),
    )
    expected_ids = [(first.exam_id, first.topic_id), (second.exam_id, second.topic_id)]
    assert [
        (item.exam_id, item.topic_id)
        for item in sort_global_study_plan_items([second, renamed])
    ] == expected_ids
    forward = sort_global_study_plan_items([later_exam, second, first])
    reverse = sort_global_study_plan_items([first, second, later_exam])
    assert forward == reverse


async def database_snapshot(session: AsyncSession) -> dict[str, list[tuple[object, ...]]]:
    models = (Subject, Topic, Exam, ExamTopic, Question, Attempt, Mastery, AIInteraction)
    snapshot: dict[str, list[tuple[object, ...]]] = {}
    for model in models:
        table = cast(Table, model.__table__)
        primary_key = list(table.primary_key.columns)
        result = await session.execute(select(*table.columns).order_by(*primary_key))
        snapshot[table.name] = [tuple(row) for row in result.all()]
    return snapshot


@pytest.mark.asyncio
async def test_global_plan_is_one_select_read_only_and_ai_independent(
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    freeze_now()
    subject_id = fixed_uuid(500)
    topic_id = fixed_uuid(501)
    exam_id = fixed_uuid(5000)
    await add_obligation(
        db_session,
        subject_id=subject_id,
        subject_name="Biology",
        exam_id=exam_id,
        exam_name="Final",
        exam_date=NOW + timedelta(days=10),
        topic_id=topic_id,
        topic_name="Cells",
        weight=Decimal("0.75"),
    )
    practiced_topic_id = fixed_uuid(504)
    await add_obligation(
        db_session,
        subject_id=subject_id,
        subject_name="Biology",
        exam_id=exam_id,
        exam_name="Final",
        exam_date=NOW + timedelta(days=10),
        topic_id=practiced_topic_id,
        topic_name="Genetics",
        weight=Decimal("0.5"),
        mastery=Decimal("50.00"),
    )
    question = Question(
        id=fixed_uuid(502),
        topic_id=topic_id,
        prompt="Prompt",
        answer_reference="Answer",
        difficulty="medium",
    )
    practiced_question = Question(
        id=fixed_uuid(505),
        topic_id=practiced_topic_id,
        prompt="Practiced prompt",
        answer_reference="Practiced answer",
        difficulty="hard",
    )
    db_session.add_all([question, practiced_question])
    await db_session.flush()
    db_session.add_all(
        [
            Attempt(
                id=fixed_uuid(506),
                question_id=practiced_question.id,
                correct=True,
                hints_used=0,
                solution_seen=False,
                time_spent_seconds=30,
            ),
            AIInteraction(
                id=fixed_uuid(503),
                provider="test",
                model="test",
                operation="question_generation",
                subject_id=subject_id,
                topic_id=topic_id,
                question_id=None,
                help_level=None,
                prompt_version="test.v1",
                input_chars=1,
                success=None,
                error_code=None,
            ),
        ]
    )
    await db_session.flush()
    before = await database_snapshot(db_session)
    monkeypatch.setattr(
        OpenAIProvider,
        "create",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("AI provider constructed")),
    )

    statements: list[str] = []

    def capture_statement(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: object,
    ) -> None:
        statements.append(statement.lstrip().upper())

    event.listen(test_engine.sync_engine, "before_cursor_execute", capture_statement)
    try:
        response = await async_client.get("/api/v1/study-plan")
    finally:
        event.remove(test_engine.sync_engine, "before_cursor_execute", capture_statement)

    assert response.status_code == 200
    assert sum(statement.startswith("SELECT") for statement in statements) == 1
    assert not any(
        statement.startswith(("INSERT", "UPDATE", "DELETE")) or "FOR UPDATE" in statement
        for statement in statements
    )
    assert await database_snapshot(db_session) == before
    assert await db_session.get(Mastery, topic_id) is None
