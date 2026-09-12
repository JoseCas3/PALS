from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.schemas.mastery import MasteryResponse


class AttemptCreate(BaseModel):
    correct: StrictBool
    hints_used: int = Field(ge=0, le=3)
    solution_seen: StrictBool
    time_spent_seconds: int = Field(ge=0)


class AttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question_id: uuid.UUID
    correct: bool
    hints_used: int
    solution_seen: bool
    time_spent_seconds: int
    created_at: datetime


class AttemptResultResponse(BaseModel):
    attempt: AttemptResponse
    mastery: MasteryResponse
