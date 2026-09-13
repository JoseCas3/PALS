from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TutorRequest(BaseModel):
    help_level: int = Field(strict=True, ge=1, le=6)


class TutorResponse(BaseModel):
    interaction_id: uuid.UUID
    question_id: uuid.UUID
    help_level: int
    content: str
    provider: str
    model: str
    prompt_version: str
    created_at: datetime
