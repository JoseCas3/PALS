import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.schemas.exam import ExamCreate, ExamResponse
from app.schemas.subject import SubjectCreate, SubjectResponse, SubjectUpdate
from app.schemas.topic import TopicCreate, TopicResponse
from app.services.exams import ExamService
from app.services.subjects import SubjectService
from app.services.topics import TopicService

router = APIRouter(tags=["subjects"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/subjects", response_model=list[SubjectResponse])
async def list_subjects(session: Session) -> list[SubjectResponse]:
    subjects = await SubjectService(session).list()
    return [SubjectResponse.model_validate(subject) for subject in subjects]


@router.post(
    "/subjects", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED
)
async def create_subject(data: SubjectCreate, session: Session) -> SubjectResponse:
    subject = await SubjectService(session).create(data)
    return SubjectResponse.model_validate(subject)


@router.get("/subjects/{subject_id}", response_model=SubjectResponse)
async def get_subject(subject_id: uuid.UUID, session: Session) -> SubjectResponse:
    subject = await SubjectService(session).get(subject_id)
    return SubjectResponse.model_validate(subject)


@router.patch("/subjects/{subject_id}", response_model=SubjectResponse)
async def update_subject(
    subject_id: uuid.UUID, data: SubjectUpdate, session: Session
) -> SubjectResponse:
    subject = await SubjectService(session).update(subject_id, data)
    return SubjectResponse.model_validate(subject)


@router.delete("/subjects/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(subject_id: uuid.UUID, session: Session) -> Response:
    await SubjectService(session).delete(subject_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/subjects/{subject_id}/topics", response_model=list[TopicResponse])
async def list_topics(subject_id: uuid.UUID, session: Session) -> list[TopicResponse]:
    topics = await TopicService(session).list_for_subject(subject_id)
    return [TopicResponse.model_validate(topic) for topic in topics]


@router.post(
    "/subjects/{subject_id}/topics",
    response_model=TopicResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_topic(
    subject_id: uuid.UUID, data: TopicCreate, session: Session
) -> TopicResponse:
    topic = await TopicService(session).create(subject_id, data)
    return TopicResponse.model_validate(topic)


@router.get("/subjects/{subject_id}/exams", response_model=list[ExamResponse])
async def list_exams(subject_id: uuid.UUID, session: Session) -> list[ExamResponse]:
    exams = await ExamService(session).list_for_subject(subject_id)
    return [ExamResponse.model_validate(exam) for exam in exams]


@router.post(
    "/subjects/{subject_id}/exams",
    response_model=ExamResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_exam(
    subject_id: uuid.UUID, data: ExamCreate, session: Session
) -> ExamResponse:
    exam = await ExamService(session).create(subject_id, data)
    return ExamResponse.model_validate(exam)
