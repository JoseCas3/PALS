from fastapi import APIRouter

from app.api.v1.exams import router as exams_router
from app.api.v1.subjects import router as subjects_router
from app.api.v1.topics import router as topics_router

router = APIRouter(prefix="/api/v1")
router.include_router(subjects_router)
router.include_router(topics_router)
router.include_router(exams_router)
