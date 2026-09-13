from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

from app.models.question import QuestionDifficulty


class GenerationDifficulty(StrEnum):
    MIXED = "mixed"
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int = Field(default=5, strict=True, ge=1, le=10)
    difficulty: GenerationDifficulty = GenerationDifficulty.MIXED


class GeneratedCandidatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: StrictStr = Field(max_length=1_000)
    answer_reference: StrictStr = Field(max_length=2_000)
    difficulty: Literal["easy", "medium", "hard"]

    @field_validator("prompt", "answer_reference")
    @classmethod
    def trim_nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Generated candidate fields must not be blank")
        return value


class GeneratedCandidatesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[GeneratedCandidatePayload]


class QuestionGenerationCandidate(BaseModel):
    prompt: str
    answer_reference: str
    difficulty: QuestionDifficulty
    duplicate_existing: bool


class QuestionGenerationResponse(BaseModel):
    interaction_id: uuid.UUID
    topic_id: uuid.UUID
    candidates: list[QuestionGenerationCandidate]
    provider: str
    model: str
    prompt_version: str
    created_at: datetime
