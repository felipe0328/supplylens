from fastapi import APIRouter

router = APIRouter()

@router.get("/health/ready")
def health() -> dict[str, str]:
    return {"status": "ok"}