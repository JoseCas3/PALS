import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Weight = Annotated[float, Field(gt=0, le=1)]


class ExamTopicPut(BaseModel):
    weight: Weight


class ExamTopicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    exam_id: uuid.UUID
    topic_id: uuid.UUID
    weight: float
