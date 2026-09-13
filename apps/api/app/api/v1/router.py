from fastapi import APIRouter

from app.api.v1.exams import router as exams_router
from app.api.v1.mastery import router as mastery_router
from app.api.v1.planner import router as planner_router
from app.api.v1.questions import router as questions_router
from app.api.v1.subjects import router as subjects_router
from app.api.v1.topics import router as topics_router
from app.api.v1.tutor import router as tutor_router

router = APIRouter(prefix="/api/v1")
router.include_router(subjects_router)
router.include_router(topics_router)
router.include_router(exams_router)
router.include_router(questions_router)
router.include_router(mastery_router)
router.include_router(planner_router)
router.include_router(tutor_router)
