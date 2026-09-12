import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.schemas.exam import ExamResponse, ExamUpdate
from app.schemas.exam_topic import ExamTopicPut, ExamTopicResponse
from app.services.exam_topics import ExamTopicService
from app.services.exams import ExamService

router = APIRouter(tags=["exams"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/exams/{exam_id}", response_model=ExamResponse)
async def get_exam(exam_id: uuid.UUID, session: Session) -> ExamResponse:
    exam = await ExamService(session).get(exam_id)
    return ExamResponse.model_validate(exam)


@router.patch("/exams/{exam_id}", response_model=ExamResponse)
async def update_exam(
    exam_id: uuid.UUID, data: ExamUpdate, session: Session
) -> ExamResponse:
    exam = await ExamService(session).update(exam_id, data)
    return ExamResponse.model_validate(exam)


@router.delete("/exams/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exam(exam_id: uuid.UUID, session: Session) -> Response:
    await ExamService(session).delete(exam_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/exams/{exam_id}/topics", response_model=list[ExamTopicResponse])
async def list_exam_topics(
    exam_id: uuid.UUID, session: Session
) -> list[ExamTopicResponse]:
    associations = await ExamTopicService(session).list_for_exam(exam_id)
    return [ExamTopicResponse.model_validate(item) for item in associations]


@router.put(
    "/exams/{exam_id}/topics/{topic_id}", response_model=ExamTopicResponse
)
async def put_exam_topic(
    exam_id: uuid.UUID, topic_id: uuid.UUID, data: ExamTopicPut, session: Session
) -> ExamTopicResponse:
    association = await ExamTopicService(session).put(exam_id, topic_id, data)
    return ExamTopicResponse.model_validate(association)


@router.delete(
    "/exams/{exam_id}/topics/{topic_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_exam_topic(
    exam_id: uuid.UUID, topic_id: uuid.UUID, session: Session
) -> Response:
    await ExamTopicService(session).delete(exam_id, topic_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
