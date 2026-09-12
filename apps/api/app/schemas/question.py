from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.models.question import QuestionDifficulty


def _nonblank(value: str, label: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{label} must not be blank")
    return value


class QuestionCreate(BaseModel):
    prompt: str
    answer_reference: str
    difficulty: QuestionDifficulty = QuestionDifficulty.MEDIUM

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        return _nonblank(value, "Prompt")

    @field_validator("answer_reference")
    @classmethod
    def validate_answer_reference(cls, value: str) -> str:
        return _nonblank(value, "Answer reference")


class QuestionUpdate(BaseModel):
    prompt: str | None = None
    answer_reference: str | None = None
    difficulty: QuestionDifficulty | None = None

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Prompt must not be null")
        return _nonblank(value, "Prompt")

    @field_validator("answer_reference")
    @classmethod
    def validate_answer_reference(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Answer reference must not be null")
        return _nonblank(value, "Answer reference")

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(
        cls, value: QuestionDifficulty | None
    ) -> QuestionDifficulty:
        if value is None:
            raise ValueError("Difficulty must not be null")
        return value

    @model_validator(mode="after")
    def require_change(self) -> QuestionUpdate:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self


class QuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    topic_id: uuid.UUID
    prompt: str
    answer_reference: str
    difficulty: QuestionDifficulty
    created_at: datetime
    updated_at: datetime
