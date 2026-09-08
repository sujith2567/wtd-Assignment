from fastapi import APIRouter
from .auth import router as auth_router
from .students import router as students_router
from .jobs import router as jobs_router
from .matching import router as matching_router
from .interviews import router as interviews_router
from .placed_students import router as placed_students_router
from .audit import router as audit_router
from .chatbot import router as chatbot_router
from .readiness import router as readiness_router
from .applications import router as applications_router
from .sections import router as sections_router
from .fairness import router as fairness_router
from .semantic_matching import router as semantic_matching_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(students_router)
api_router.include_router(jobs_router)
api_router.include_router(matching_router)
api_router.include_router(interviews_router)
api_router.include_router(placed_students_router)
api_router.include_router(audit_router)
api_router.include_router(chatbot_router)
api_router.include_router(readiness_router)
api_router.include_router(applications_router)
api_router.include_router(sections_router)
api_router.include_router(fairness_router)
api_router.include_router(semantic_matching_router)
