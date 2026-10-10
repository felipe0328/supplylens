from fastapi import APIRouter, HTTPException, status

from supplylens.database.database import health_check
from supplylens.schemas.common import ErrorResponse, HealthResponse

health_router = APIRouter(tags=["Health"])


@health_router.get(
    "/health/ready",
    response_model=HealthResponse,
    summary="Check database readiness",
    description=(
        "Checks PostgreSQL connectivity. A missing database configuration or an "
        "unavailable database returns 503."
    ),
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ErrorResponse,
            "description": (
                "Database configuration is missing or PostgreSQL is unavailable."
            ),
        }
    },
)
def readiness() -> dict[str, str]:
    try:
        health_check()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database configuration error",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc

    return {"status": "healthy"}
