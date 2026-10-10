from fastapi import APIRouter

from .auth import auth_router
from .documents import documents_router
from .health import health_router

router = APIRouter()
router.include_router(documents_router)
router.include_router(auth_router)
router.include_router(health_router)
