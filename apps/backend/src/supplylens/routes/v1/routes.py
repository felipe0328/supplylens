from fastapi import APIRouter, HTTPException, status

from supplylens.database.database import health_check

from .documents import documents_router

router = APIRouter()
router.include_router(documents_router)


@router.get("/health/ready")
def health() -> dict[str, str]:
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
