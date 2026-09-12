from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TopicCreate(BaseModel):
    name: str = Field(max_length=255)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be blank")
        return value


class TopicUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
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

    @model_validator(mode="after")
    def require_change(self) -> TopicUpdate:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self


class TopicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
