from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from supplylens.domain.users import UserRole, UserStatus


class User(BaseModel):
    id: UUID = Field(description="The ID of the user.")
    email: EmailStr = Field(description="The email address of the user.")
    role: UserRole = Field(description="The role of the user.")
    status: UserStatus = Field(description="The status of the user.")
    accepted_by: User | None = Field(description="The user that accepted the user.")
    pending_expires_at: datetime | None = Field(
        description="The timestamp when the user's pending status expires."
    )
    created_at: datetime = Field(description="The timestamp of the user's creation.")
    updated_at: datetime = Field(description="The timestamp of the user's last update.")
    deleted_at: datetime | None = Field(
        description="The timestamp of the user's deletion."
    )


class RegisterRequest(BaseModel):
    email: EmailStr = Field(
        description=(
            "Email address for the new account. Stored in normalized lowercase form."
        ),
    )
    password: str = Field(
        description=(
            "Password for the new account. Must be 8 to 128 characters and include "
            "an uppercase letter, a lowercase letter, and a digit."
        ),
    )


class RegisterResponse(BaseModel):
    user: User = Field(description="The user that was registered.")
