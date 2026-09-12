import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.schemas.mastery import MasteryResponse
from app.services.mastery import MasteryService

router = APIRouter(tags=["mastery"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/topics/{topic_id}/mastery", response_model=MasteryResponse)
async def get_mastery(topic_id: uuid.UUID, session: Session) -> MasteryResponse:
    mastery = await MasteryService(session).get(topic_id)
    return MasteryResponse.from_values(
        topic_id=mastery.topic_id,
        score=mastery.score,
        updated_at=mastery.updated_at,
    )
