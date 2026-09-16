import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gateway import AIGateway
from app.api.dependencies import (
    RetrievalServiceDependency,
    get_ai_gateway,
    get_session,
)
from app.schemas.tutor import TutorRequest, TutorResponse
from app.services.tutor import TutorService

router = APIRouter(tags=["tutor"])
Session = Annotated[AsyncSession, Depends(get_session)]
Gateway = Annotated[AIGateway, Depends(get_ai_gateway)]


@router.post("/questions/{question_id}/tutor", response_model=TutorResponse)
async def tutor_question(
    question_id: uuid.UUID,
    data: TutorRequest,
    session: Session,
    gateway: Gateway,
    retrieval: RetrievalServiceDependency,
    response: Response,
) -> TutorResponse:
    response.headers["Cache-Control"] = "no-store"
    result = await TutorService(session, gateway, retrieval).help_question(
        question_id, data.help_level, data.grounding_mode
    )
    return TutorResponse.model_validate(result, from_attributes=True)
