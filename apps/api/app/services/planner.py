from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.repositories.exams import ExamRepository
from app.repositories.planner import PlannerRepository

MASTERY_FACTOR = Decimal("0.50")
URGENCY_FACTOR = Decimal("0.30")
EXAM_WEIGHT_FACTOR = Decimal("0.20")

UNIT_MIN = Decimal("0")
UNIT_MAX = Decimal("1")
UNIT_QUANTUM = Decimal("0.0001")
MASTERY_MIN = Decimal("0.00")
MASTERY_MAX = Decimal("100.00")
HORIZON_SECONDS = Decimal(30 * 24 * 60 * 60)
MICROSECONDS_PER_SECOND = Decimal("1000000")

FactorCode = Literal["mastery_need", "urgency", "exam_weight"]


def _quantize_unit(value: Decimal) -> Decimal:
    return value.quantize(UNIT_QUANTUM, rounding=ROUND_HALF_UP)


def _require_unit(value: Decimal, label: str) -> None:
    if value < UNIT_MIN or value > UNIT_MAX:
        raise ValueError(f"{label} must be between 0 and 1")


def _as_utc(value: datetime, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(UTC)


def calculate_mastery_need(mastery_score: Decimal) -> Decimal:
    if mastery_score < MASTERY_MIN or mastery_score > MASTERY_MAX:
        raise ValueError("Persisted mastery score must be between 0 and 100")
    return _quantize_unit(UNIT_MAX - mastery_score / Decimal("100"))


def calculate_urgency(*, exam_date: datetime, generated_at: datetime) -> Decimal:
    exam_utc = _as_utc(exam_date, "exam_date")
    generated_utc = _as_utc(generated_at, "generated_at")
    remaining = exam_utc - generated_utc
    remaining_seconds = Decimal(remaining.days * 24 * 60 * 60 + remaining.seconds)
    remaining_seconds += Decimal(remaining.microseconds) / MICROSECONDS_PER_SECOND
    urgency = UNIT_MAX - remaining_seconds / HORIZON_SECONDS
    clamped = min(UNIT_MAX, max(UNIT_MIN, urgency))
    return _quantize_unit(clamped)


def calculate_priority(*, mastery_need: Decimal, urgency: Decimal, exam_weight: Decimal) -> Decimal:
    _require_unit(mastery_need, "mastery_need")
    _require_unit(urgency, "urgency")
    if exam_weight <= UNIT_MIN or exam_weight > UNIT_MAX:
        raise ValueError("Persisted ExamTopic weight must be greater than 0 and at most 1")
    normalized_mastery_need = _quantize_unit(mastery_need)
    normalized_urgency = _quantize_unit(urgency)
    normalized_weight = _quantize_unit(exam_weight)
    priority = (
        MASTERY_FACTOR * normalized_mastery_need
        + URGENCY_FACTOR * normalized_urgency
        + EXAM_WEIGHT_FACTOR * normalized_weight
    )
    return _quantize_unit(priority)


def calculate_weighted_contributions(
    *, mastery_need: Decimal, urgency: Decimal, exam_weight: Decimal
) -> tuple[Decimal, Decimal, Decimal]:
    return (
        mastery_need * MASTERY_FACTOR,
        urgency * URGENCY_FACTOR,
        exam_weight * EXAM_WEIGHT_FACTOR,
    )


@dataclass(frozen=True)
class PlannerReasonFactor:
    code: FactorCode
    value: Decimal
    formula_weight: Decimal


@dataclass(frozen=True)
class PlannerReason:
    summary: str
    factors: tuple[PlannerReasonFactor, ...]


def build_reason(*, mastery_need: Decimal, urgency: Decimal, exam_weight: Decimal) -> PlannerReason:
    contributions = calculate_weighted_contributions(
        mastery_need=mastery_need, urgency=urgency, exam_weight=exam_weight
    )
    candidates = (
        ("Mastery need is the strongest contributor to this priority.", contributions[0]),
        ("Exam urgency is the strongest contributor to this priority.", contributions[1]),
        ("Exam weight is the strongest contributor to this priority.", contributions[2]),
    )
    summary = max(candidates, key=lambda candidate: candidate[1])[0]
    return PlannerReason(
        summary=summary,
        factors=(
            PlannerReasonFactor("mastery_need", mastery_need, MASTERY_FACTOR),
            PlannerReasonFactor("urgency", urgency, URGENCY_FACTOR),
            PlannerReasonFactor("exam_weight", exam_weight, EXAM_WEIGHT_FACTOR),
        ),
    )


@dataclass(frozen=True)
class PlannerScore:
    mastery_score: Decimal
    mastery_need: Decimal
    urgency: Decimal
    exam_weight: Decimal
    persisted_exam_weight: Decimal
    priority: Decimal
    reason: PlannerReason


def score_study_plan_item(
    *,
    mastery_score: Decimal,
    exam_date: datetime,
    exam_weight: Decimal,
    generated_at: datetime,
) -> PlannerScore:
    mastery_need = calculate_mastery_need(mastery_score)
    urgency = calculate_urgency(exam_date=exam_date, generated_at=generated_at)
    normalized_exam_weight = _quantize_unit(exam_weight)
    return PlannerScore(
        mastery_score=mastery_score,
        mastery_need=mastery_need,
        urgency=urgency,
        exam_weight=normalized_exam_weight,
        persisted_exam_weight=exam_weight,
        priority=calculate_priority(
            mastery_need=mastery_need,
            urgency=urgency,
            exam_weight=exam_weight,
        ),
        reason=build_reason(
            mastery_need=mastery_need,
            urgency=urgency,
            exam_weight=normalized_exam_weight,
        ),
    )
@dataclass(frozen=True)
class StudyPlanItem:
    topic_id: uuid.UUID
    topic_name: str
    mastery_score: Decimal
    mastery_need: Decimal
    urgency: Decimal
    exam_weight: Decimal
    persisted_exam_weight: Decimal
    priority: Decimal
    reason: PlannerReason


@dataclass(frozen=True)
class StudyPlan:
    exam_id: uuid.UUID
    exam_name: str
    exam_date: datetime
    generated_at: datetime
    items: tuple[StudyPlanItem, ...]


@dataclass(frozen=True)
class GlobalStudyPlanItem:
    subject_id: uuid.UUID
    subject_name: str
    exam_id: uuid.UUID
    exam_name: str
    exam_date: datetime
    topic_id: uuid.UUID
    topic_name: str
    mastery_score: Decimal
    mastery_need: Decimal
    urgency: Decimal
    exam_weight: Decimal
    persisted_exam_weight: Decimal
    priority: Decimal
    reason: PlannerReason


@dataclass(frozen=True)
class GlobalStudyPlan:
    generated_at: datetime
    items: tuple[GlobalStudyPlanItem, ...]


def sort_study_plan_items(items: list[StudyPlanItem]) -> list[StudyPlanItem]:
    return sorted(
        items,
        key=lambda item: (
            -item.priority,
            item.mastery_score,
            -item.persisted_exam_weight,
            item.topic_id,
        ),
    )


def sort_global_study_plan_items(
    items: list[GlobalStudyPlanItem],
) -> list[GlobalStudyPlanItem]:
    return sorted(
        items,
        key=lambda item: (
            -item.priority,
            item.mastery_score,
            item.exam_date,
            -item.persisted_exam_weight,
            item.exam_id,
            item.topic_id,
        ),
    )


class PlannerService:
    def __init__(self, session: AsyncSession) -> None:
        self.exams = ExamRepository(session)
        self.planner = PlannerRepository(session)

    async def generate(self, exam_id: uuid.UUID, generated_at: datetime) -> StudyPlan:
        generated_utc = _as_utc(generated_at, "generated_at")
        exam = await self.exams.get(exam_id)
        if exam is None:
            raise ApplicationError(404, "RESOURCE_NOT_FOUND", "Exam not found")

        exam_utc = _as_utc(exam.exam_date, "exam_date")
        if exam_utc < generated_utc:
            raise ApplicationError(
                409,
                "EXAM_ALREADY_PASSED",
                "Study plans cannot be generated for a past exam",
            )

        items: list[StudyPlanItem] = []
        for topic in await self.planner.list_topic_inputs(exam_id):
            score = score_study_plan_item(
                mastery_score=topic.mastery_score,
                exam_date=exam_utc,
                exam_weight=topic.exam_weight,
                generated_at=generated_utc,
            )
            items.append(
                StudyPlanItem(
                    topic_id=topic.topic_id,
                    topic_name=topic.topic_name,
                    **score.__dict__,
                )
            )

        ordered = sort_study_plan_items(items)
        return StudyPlan(
            exam_id=exam.id,
            exam_name=exam.name,
            exam_date=exam_utc,
            generated_at=generated_utc,
            items=tuple(ordered),
        )

    async def generate_global(self, generated_at: datetime) -> GlobalStudyPlan:
        generated_utc = _as_utc(generated_at, "generated_at")
        items: list[GlobalStudyPlanItem] = []
        for planner_input in await self.planner.list_global_inputs(generated_utc):
            exam_utc = _as_utc(planner_input.exam_date, "exam_date")
            score = score_study_plan_item(
                mastery_score=(
                    planner_input.mastery_score
                    if planner_input.mastery_score is not None
                    else Decimal("0.00")
                ),
                exam_date=exam_utc,
                exam_weight=planner_input.exam_weight,
                generated_at=generated_utc,
            )
            items.append(
                GlobalStudyPlanItem(
                    subject_id=planner_input.subject_id,
                    subject_name=planner_input.subject_name,
                    exam_id=planner_input.exam_id,
                    exam_name=planner_input.exam_name,
                    exam_date=exam_utc,
                    topic_id=planner_input.topic_id,
                    topic_name=planner_input.topic_name,
                    **score.__dict__,
                )
            )
        return GlobalStudyPlan(
            generated_at=generated_utc,
            items=tuple(sort_global_study_plan_items(items)),
        )
