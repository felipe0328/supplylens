from fastapi import APIRouter, HTTPException, status
from supplylens.database.database import health_check

router = APIRouter()


@router.get("/health/ready")
def health() -> dict[str, str]:
    try:
        health_check()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database configuration error: {exc}",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unavailable: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database health check failed: {exc}",
        ) from exc

    return {"status": "healthy"}
