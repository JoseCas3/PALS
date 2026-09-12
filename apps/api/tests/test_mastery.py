import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Attempt, Mastery, Question, Subject, Topic
from app.schemas.attempt import AttemptCreate
from app.services.attempts import AttemptService
from app.services.mastery import MasteryService, apply_delta, calculate_delta
from tests.conftest import test_engine
from tests.test_exam_topics import create_topic
from tests.test_questions import create_question
from tests.test_subjects import create_subject


@pytest.mark.parametrize(
    ("correct", "difficulty", "hints", "solution", "expected"),
    [
        (True, "easy", 0, False, Decimal("6.00")),
        (True, "medium", 0, False, Decimal("8.00")),
        (True, "hard", 0, False, Decimal("10.00")),
        (True, "easy", 1, False, Decimal("4.80")),
        (True, "medium", 2, False, Decimal("4.80")),
        (True, "hard", 3, False, Decimal("4.00")),
        (False, "easy", 0, False, Decimal("-3.75")),
        (False, "medium", 1, False, Decimal("-4.00")),
        (False, "medium", 2, False, Decimal("-3.00")),
        (False, "hard", 3, False, Decimal("-2.50")),
        (True, "medium", 3, True, Decimal("0.80")),
        (False, "hard", 2, True, Decimal("-0.63")),
    ],
)
def test_exact_mastery_delta(
    correct: bool,
    difficulty: str,
    hints: int,
    solution: bool,
    expected: Decimal,
) -> None:
    assert calculate_delta(
        correct=correct,
        difficulty=difficulty,
        hints_used=hints,
        solution_seen=solution,
    ) == expected


def test_mastery_clamps_and_quantizes() -> None:
    assert apply_delta(Decimal("98.00"), Decimal("10.00")) == Decimal("100.00")
    assert apply_delta(Decimal("1.00"), Decimal("-6.25")) == Decimal("0.00")


@pytest.mark.asyncio
async def test_virtual_mastery_does_not_create_row(async_client: AsyncClient) -> None:
    subject = await create_subject(async_client)
    topic = await create_topic(async_client, subject["id"], "Limits")
    response = await async_client.get(f"/api/v1/topics/{topic['id']}/mastery")
    assert response.status_code == 200
    assert response.json() == {
        "topic_id": topic["id"],
        "score": "0.00",
        "updated_at": None,
    }


@pytest.mark.asyncio
async def test_sequential_attempts_create_and_update_mastery(async_client: AsyncClient) -> None:
    subject = await create_subject(async_client)
    topic = await create_topic(async_client, subject["id"], "Limits")
    question = await create_question(async_client, topic["id"], difficulty="hard")
    url = f"/api/v1/questions/{question['id']}/attempts"
    first = await async_client.post(
        url,
        json={
            "correct": True,
            "hints_used": 0,
            "solution_seen": False,
            "time_spent_seconds": 1,
        },
    )
    assert first.json()["mastery"]["score"] == "10.00"
    second = await async_client.post(
        url,
        json={
            "correct": False,
            "hints_used": 2,
            "solution_seen": True,
            "time_spent_seconds": 2,
        },
    )
    assert second.json()["mastery"]["score"] == "9.37"
    mastery = await async_client.get(f"/api/v1/topics/{topic['id']}/mastery")
    assert mastery.json()["score"] == "9.37"


@asynccontextmanager
async def committed_practice_data(
    question_count: int = 1,
) -> AsyncIterator[tuple[uuid.UUID, list[uuid.UUID]]]:
    subject_id = uuid.uuid4()
    topic_id = uuid.uuid4()
    question_ids = [uuid.uuid4() for _ in range(question_count)]
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        session.add(Subject(id=subject_id, name=f"Concurrency {subject_id}"))
        await session.flush()
        session.add(Topic(id=topic_id, subject_id=subject_id, name="Locks"))
        await session.flush()
        session.add_all(
            Question(
                id=question_id,
                topic_id=topic_id,
                prompt=f"Question {question_id}",
                answer_reference="Answer",
                difficulty="medium",
            )
            for question_id in question_ids
        )
        await session.commit()
    try:
        yield topic_id, question_ids
    finally:
        async with AsyncSession(test_engine) as session:
            await session.execute(delete(Attempt).where(Attempt.question_id.in_(question_ids)))
            await session.execute(delete(Mastery).where(Mastery.topic_id == topic_id))
            await session.execute(delete(Question).where(Question.id.in_(question_ids)))
            await session.execute(delete(Topic).where(Topic.id == topic_id))
            await session.execute(delete(Subject).where(Subject.id == subject_id))
            await session.commit()


async def record_with_new_session(question_id: uuid.UUID) -> str:
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        _, mastery = await AttemptService(session).record(
            question_id,
            AttemptCreate(
                correct=True,
                hints_used=0,
                solution_seen=False,
                time_spent_seconds=1,
            ),
        )
        return format(mastery.score, ".2f")


@pytest.mark.asyncio
async def test_virtual_mastery_read_does_not_persist_a_row() -> None:
    async with committed_practice_data() as (topic_id, _):
        async with AsyncSession(test_engine) as session:
            state = await MasteryService(session).get(topic_id)
            assert state.score == Decimal("0.00")
            assert state.updated_at is None
            assert await session.get(Mastery, topic_id) is None


@pytest.mark.asyncio
async def test_database_restricts_deleting_a_question_with_evidence() -> None:
    async with committed_practice_data() as (_, question_ids):
        await record_with_new_session(question_ids[0])
        async with AsyncSession(test_engine) as session:
            with pytest.raises(IntegrityError):
                await session.execute(delete(Question).where(Question.id == question_ids[0]))
                await session.commit()
            await session.rollback()


@pytest.mark.asyncio
async def test_simultaneous_first_attempts_do_not_lose_updates() -> None:
    async with committed_practice_data(question_count=2) as (topic_id, question_ids):
        await asyncio.gather(*(record_with_new_session(item) for item in question_ids))
        async with AsyncSession(test_engine) as session:
            assert await session.scalar(
                select(Mastery.score).where(Mastery.topic_id == topic_id)
            ) == Decimal("16.00")
            assert await session.scalar(
                select(func.count()).select_from(Attempt).where(
                    Attempt.question_id.in_(question_ids)
                )
            ) == 2


@pytest.mark.asyncio
async def test_simultaneous_existing_mastery_updates_do_not_lose_updates() -> None:
    async with committed_practice_data(question_count=3) as (topic_id, question_ids):
        await record_with_new_session(question_ids[0])
        await asyncio.gather(*(record_with_new_session(item) for item in question_ids[1:]))
        async with AsyncSession(test_engine) as session:
            assert await session.scalar(
                select(Mastery.score).where(Mastery.topic_id == topic_id)
            ) == Decimal("24.00")


@pytest.mark.asyncio
async def test_failure_after_flush_rolls_back_attempt_and_mastery() -> None:
    async with committed_practice_data() as (topic_id, question_ids):
        async with AsyncSession(test_engine, expire_on_commit=False) as session:
            service = AttemptService(session)
            original_flush = session.flush

            async def flush_then_fail(*objects: object) -> None:
                await original_flush(objects or None)
                raise RuntimeError("forced failure after database flush")

            session.flush = flush_then_fail  # type: ignore[assignment]
            with pytest.raises(RuntimeError, match="forced failure"):
                await service.record(
                    question_ids[0],
                    AttemptCreate(
                        correct=True,
                        hints_used=0,
                        solution_seen=False,
                        time_spent_seconds=1,
                    ),
                )
            await session.rollback()

        async with AsyncSession(test_engine) as verification:
            assert await verification.get(Mastery, topic_id) is None
            assert await verification.scalar(
                select(func.count()).select_from(Attempt).where(
                    Attempt.question_id == question_ids[0]
                )
            ) == 0
