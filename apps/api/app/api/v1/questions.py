import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.schemas.attempt import AttemptCreate, AttemptResponse, AttemptResultResponse
from app.schemas.mastery import MasteryResponse
from app.schemas.question import QuestionCreate, QuestionResponse, QuestionUpdate
from app.services.attempts import AttemptService
from app.services.questions import QuestionService

router = APIRouter(tags=["questions"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/topics/{topic_id}/questions", response_model=list[QuestionResponse])
async def list_questions(topic_id: uuid.UUID, session: Session) -> list[QuestionResponse]:
    questions = await QuestionService(session).list_for_topic(topic_id)
    return [QuestionResponse.model_validate(question) for question in questions]


@router.post(
    "/topics/{topic_id}/questions",
    response_model=QuestionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_question(
    topic_id: uuid.UUID, data: QuestionCreate, session: Session
) -> QuestionResponse:
    question = await QuestionService(session).create(topic_id, data)
    return QuestionResponse.model_validate(question)


@router.get("/questions/{question_id}", response_model=QuestionResponse)
async def get_question(question_id: uuid.UUID, session: Session) -> QuestionResponse:
    question = await QuestionService(session).get(question_id)
    return QuestionResponse.model_validate(question)


@router.patch("/questions/{question_id}", response_model=QuestionResponse)
async def update_question(
    question_id: uuid.UUID, data: QuestionUpdate, session: Session
) -> QuestionResponse:
    question = await QuestionService(session).update(question_id, data)
    return QuestionResponse.model_validate(question)


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(question_id: uuid.UUID, session: Session) -> Response:
    await QuestionService(session).delete(question_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/questions/{question_id}/attempts",
    response_model=AttemptResultResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_attempt(
    question_id: uuid.UUID, data: AttemptCreate, session: Session
) -> AttemptResultResponse:
    attempt, mastery = await AttemptService(session).record(question_id, data)
    return AttemptResultResponse(
        attempt=AttemptResponse.model_validate(attempt),
        mastery=MasteryResponse.from_values(
            topic_id=mastery.topic_id,
            score=mastery.score,
            updated_at=mastery.updated_at,
        ),
    )


@router.get(
    "/questions/{question_id}/attempts", response_model=list[AttemptResponse]
)
async def list_attempts(
    question_id: uuid.UUID, session: Session
) -> list[AttemptResponse]:
    attempts = await AttemptService(session).list_for_question(question_id)
    return [AttemptResponse.model_validate(attempt) for attempt in attempts]
