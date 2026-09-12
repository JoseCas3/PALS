import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.schemas.topic import TopicResponse, TopicUpdate
from app.services.topics import TopicService

router = APIRouter(tags=["topics"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/topics/{topic_id}", response_model=TopicResponse)
async def get_topic(topic_id: uuid.UUID, session: Session) -> TopicResponse:
    topic = await TopicService(session).get(topic_id)
    return TopicResponse.model_validate(topic)


@router.patch("/topics/{topic_id}", response_model=TopicResponse)
async def update_topic(
    topic_id: uuid.UUID, data: TopicUpdate, session: Session
) -> TopicResponse:
    topic = await TopicService(session).update(topic_id, data)
    return TopicResponse.model_validate(topic)


@router.delete("/topics/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(topic_id: uuid.UUID, session: Session) -> Response:
    await TopicService(session).delete(topic_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
