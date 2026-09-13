import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gateway import AIGateway
from app.api.dependencies import get_ai_gateway, get_session
from app.schemas.question_generation import (
    QuestionGenerationRequest,
    QuestionGenerationResponse,
)
from app.services.question_generation import QuestionGenerationService

router = APIRouter(tags=["question-generation"])
Session = Annotated[AsyncSession, Depends(get_session)]
Gateway = Annotated[AIGateway, Depends(get_ai_gateway)]


@router.post(
    "/topics/{topic_id}/question-generation",
    response_model=QuestionGenerationResponse,
)
async def generate_questions(
    topic_id: uuid.UUID,
    data: QuestionGenerationRequest,
    session: Session,
    gateway: Gateway,
    response: Response,
) -> QuestionGenerationResponse:
    response.headers["Cache-Control"] = "no-store"
    return await QuestionGenerationService(session, gateway).generate(topic_id, data)
