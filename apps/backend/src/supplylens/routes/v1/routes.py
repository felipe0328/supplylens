from fastapi import APIRouter, HTTPException, status
from supplylens.database.database import health_check

router = APIRouter()


@router.get("/health/ready")
def health() -> dict[str, str]:
    health_check_result = health_check()
    if not health_check_result:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )

    return {"status": "healthy"}
