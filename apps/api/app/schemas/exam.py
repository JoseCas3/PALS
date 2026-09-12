from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class ExamCreate(BaseModel):
    name: str = Field(max_length=255)
    exam_date: AwareDatetime
    description: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be blank")
        return value

    @field_validator("exam_date")
    @classmethod
    def normalize_exam_date(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class ExamUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    exam_date: AwareDatetime | None = None
    description: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Name must not be null")
        value = value.strip()
        if not value:
            raise ValueError("Name must not be blank")
        return value

    @field_validator("exam_date")
    @classmethod
    def normalize_exam_date(cls, value: datetime | None) -> datetime:
        if value is None:
            raise ValueError("Exam date must not be null")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def require_change(self) -> ExamUpdate:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self


class ExamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject_id: uuid.UUID
    name: str
    exam_date: datetime
    description: str | None
    created_at: datetime
    updated_at: datetime
