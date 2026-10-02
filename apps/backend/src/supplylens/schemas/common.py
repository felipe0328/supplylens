from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    detail: str = Field(description="A safe, human-readable error message.")


class HealthResponse(BaseModel):
    status: str = Field(description="Health state reported by this check.")
