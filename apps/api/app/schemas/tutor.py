from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator


class GroundingMode(StrEnum):
    NONE = "NONE"
    REQUIRED = "REQUIRED"


class TutorOutcome(StrEnum):
    ANSWER = "ANSWER"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class TutorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    help_level: int = Field(strict=True, ge=1, le=6)
    grounding_mode: GroundingMode = GroundingMode.NONE


class GroundedTutorGeneration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: StrictStr = Field(max_length=10_000)
    citations: list[StrictStr]

    @field_validator("answer")
    @classmethod
    def trim_answer(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Grounded answer must not be blank")
        return value


class GroundedCitationResponse(BaseModel):
    alias: str
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_filename: str
    page_start: int
    page_end: int


class TutorResponse(BaseModel):
    interaction_id: uuid.UUID | None
    question_id: uuid.UUID
    help_level: int
    grounding_mode: GroundingMode
    outcome: TutorOutcome
    content: str | None
    answer: str | None
    citations: list[GroundedCitationResponse]
    provider: str | None
    model: str | None
    prompt_version: str
    created_at: datetime | None
