from fastapi import APIRouter
from supplylens.database.database import health_check

router = APIRouter()


@router.get("/health/ready")
def health() -> dict[str, str]:
    health_check_result = health_check()
    return {"status": "healthy" if health_check_result else "unhealthy"}
