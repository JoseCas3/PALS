from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_serializer


class PlannerReasonFactorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: Literal["mastery_need", "urgency", "exam_weight"]
    value: Decimal
    formula_weight: Decimal

    @field_serializer("value", "formula_weight")
    def serialize_unit_decimal(self, value: Decimal) -> str:
        return format(value, ".4f")


class PlannerReasonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    summary: str
    factors: list[PlannerReasonFactorResponse]


class StudyPlanItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    topic_id: uuid.UUID
    topic_name: str
    mastery_score: Decimal
    mastery_need: Decimal
    urgency: Decimal
    exam_weight: Decimal
    priority: Decimal
    reason: PlannerReasonResponse

    @field_serializer("mastery_score")
    def serialize_mastery_score(self, value: Decimal) -> str:
        return format(value, ".2f")

    @field_serializer("mastery_need", "urgency", "exam_weight", "priority")
    def serialize_unit_decimal(self, value: Decimal) -> str:
        return format(value, ".4f")


class StudyPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    exam_id: uuid.UUID
    exam_name: str
    exam_date: datetime
    generated_at: datetime
    items: list[StudyPlanItemResponse]


class GlobalStudyPlanItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    priority: Decimal
    reason: PlannerReasonResponse

    @field_serializer("mastery_score")
    def serialize_mastery_score(self, value: Decimal) -> str:
        return format(value, ".2f")

    @field_serializer("mastery_need", "urgency", "exam_weight", "priority")
    def serialize_unit_decimal(self, value: Decimal) -> str:
        return format(value, ".4f")


class GlobalStudyPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    generated_at: datetime
    items: list[GlobalStudyPlanItemResponse]
