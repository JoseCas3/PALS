import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.core.clock import utc_now
from app.schemas.planner import StudyPlanResponse
from app.services.planner import PlannerService

router = APIRouter(tags=["planner"])
Session = Annotated[AsyncSession, Depends(get_session)]
GeneratedAt = Annotated[datetime, Depends(utc_now)]


@router.get("/exams/{exam_id}/study-plan", response_model=StudyPlanResponse)
async def get_study_plan(
    exam_id: uuid.UUID,
    session: Session,
    generated_at: GeneratedAt,
    response: Response,
) -> StudyPlanResponse:
    response.headers["Cache-Control"] = "no-store"
    plan = await PlannerService(session).generate(exam_id, generated_at)
    return StudyPlanResponse.model_validate(plan)
