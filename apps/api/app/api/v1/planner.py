import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.core.clock import utc_now
from app.schemas.planner import GlobalStudyPlanResponse, StudyPlanResponse
from app.services.planner import PlannerService

router = APIRouter(tags=["planner"])
Session = Annotated[AsyncSession, Depends(get_session)]
GeneratedAt = Annotated[datetime, Depends(utc_now)]


@router.get("/study-plan", response_model=GlobalStudyPlanResponse)
async def get_global_study_plan(
    session: Session,
    generated_at: GeneratedAt,
    response: Response,
) -> GlobalStudyPlanResponse:
    response.headers["Cache-Control"] = "no-store"
    plan = await PlannerService(session).generate_global(generated_at)
    return GlobalStudyPlanResponse.model_validate(plan)


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
